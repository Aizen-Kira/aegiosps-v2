import json
import os
import sqlite3
import uuid
from pathlib import Path
from typing import Any

import numpy as np

from .tools.phoenix import PhoenixTool


DB_PATH = Path(__file__).resolve().parents[1] / "aegisops_memory.sqlite3"


class MemoryManager:
    def __init__(self, demo_mode: bool = False):
        self.phoenix = PhoenixTool(demo_mode=demo_mode)
        self.demo_mode = demo_mode
        self.db_path = DB_PATH
        # optional local sentence-transformers model (loaded lazily)
        self._embed_model = None
        self._try_load_local_model()
        self._init_db()

    def query_similar_incidents(self, description: str, top_k: int = 3) -> list[dict[str, Any]]:
        if not self.demo_mode and not self.phoenix.is_available:
            return []

        phoenix_traces = self.phoenix.query_traces(description)
        phoenix_by_id = {str(trace.get("id")): trace for trace in phoenix_traces if trace.get("id")}

        # Generate embedding for the query (local model preferred, then cloud, then demo)
        query_embedding = np.array(self._embed(description, task_type="RETRIEVAL_QUERY"))

        candidates = []
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT trace_id, phoenix_span_id, description, embedding_json, root_cause,
                       remediation_steps_json, duration_seconds, eval_score, confidence_score,
                       tools_used
                FROM trace_memory
                """
            ).fetchall()

        # Vectorize stored embeddings for fast batch similarity computation
        stored_embeddings = []
        metadata = []
        for row in rows:
            trace_id, span_id, stored_description, embedding_json, root_cause, steps_json, duration, eval_score, confidence, tools = row
            if not self.demo_mode and str(trace_id) not in phoenix_by_id:
                continue
            try:
                emb = json.loads(embedding_json)
            except Exception:
                # Malformed embedding; skip this memory row.
                continue
            emb_array = np.array(emb, dtype=float)
            if emb_array.ndim != 1 or emb_array.shape[0] != query_embedding.shape[0]:
                # Older demo rows may have a different vector length. Ignore them
                # instead of aborting the incident stream.
                continue
            stored_embeddings.append(emb_array)
            metadata.append((trace_id, span_id, stored_description, root_cause, steps_json, duration, float(eval_score or 0.0), float(confidence or 0.0), tools))

        if not stored_embeddings:
            return []

        emb_matrix = np.vstack(stored_embeddings)
        # compute cosine similarities in a vectorized way
        q_norm = np.linalg.norm(query_embedding)
        emb_norms = np.linalg.norm(emb_matrix, axis=1)
        dots = emb_matrix.dot(query_embedding)
        denom = emb_norms * q_norm
        similarities = np.where(denom == 0, 0.0, dots / denom)

        # Threshold and collect candidates
        threshold = float(os.getenv("SIMILARITY_THRESHOLD", 0.65))
        for idx, sim in enumerate(similarities):
            if sim <= threshold:
                continue
            trace_id, span_id, stored_description, root_cause, steps_json, duration, eval_score, confidence, tools = metadata[idx]
            phoenix_trace = phoenix_by_id.get(str(trace_id), {})
            candidates.append(
                {
                    "id": trace_id,
                    "phoenix_span_id": span_id,
                    "description": stored_description,
                    "root_cause": root_cause,
                    "resolution": phoenix_trace.get("resolution", ""),
                    "remediation_steps": json.loads(steps_json or "[]"),
                    "duration": float(duration or 0.0),
                    "similarity": float(sim),
                    "eval_score": float(eval_score or 0.0),
                    # placeholder for combined_score; will compute with historical averages below
                    "combined_score": 0.0,
                    "confidence": 0.0,
                    "confidence_score": float(confidence or 0.0),
                    "tools_used": tools.split(",") if tools else [],
                }
            )

        # Compute historical success score per root_cause from eval_history and finalize ranking
        try:
            root_causes = list({c.get("root_cause") for c in candidates if c.get("root_cause")})
            historical_map: dict[str, float] = {}
            if root_causes:
                placeholders = ",".join("?" for _ in root_causes)
                q = f"SELECT root_cause, AVG(overall) as avg_overall FROM eval_history WHERE root_cause IN ({placeholders}) GROUP BY root_cause"
                with sqlite3.connect(self.db_path) as conn:
                    rows = conn.execute(q, tuple(root_causes)).fetchall()
                for rc, avg in rows:
                    try:
                        historical_map[rc] = float(avg)
                    except Exception:
                        historical_map[rc] = 0.0

            for c in candidates:
                hist = historical_map.get(c.get("root_cause"), c.get("eval_score", 0.0))
                # final formula: 0.7 * similarity + 0.3 * historical_success
                final_score = float(c.get("similarity", 0.0)) * 0.7 + float(hist) * 0.3
                c["historical_success_score"] = float(hist)
                c["combined_score"] = float(final_score)
                c["confidence"] = min(0.99, float(final_score))
        except Exception:
            # best-effort: fall back to similarity * eval_score
            for c in candidates:
                sim = float(c.get("similarity", 0.0))
                eval_s = float(c.get("eval_score", 0.0))
                combined = sim * eval_s
                c["combined_score"] = combined
                c["confidence"] = min(0.99, combined)

        # sort by combined score (new final_score formula) and return top_k
        return sorted(candidates, key=lambda item: item["combined_score"], reverse=True)[: top_k]

    def store_incident_trace(self, incident: dict, resolution: dict, duration: float) -> str:
        trace_id = f"trace-{uuid.uuid4().hex[:12]}"
        description = incident.get("query") or incident.get("description", "")
        embedding = self._embed(description, task_type="RETRIEVAL_DOCUMENT")
        trace_data = {
            "id": trace_id,
            "incident": incident,
            "resolution": resolution,
            "duration": duration,
            "step": "LEARN",
        }
        phoenix_ids = self.phoenix.log_trace(trace_data)
        phoenix_span_id = phoenix_ids.get("span_id") if isinstance(phoenix_ids, dict) else None

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO trace_memory (
                    trace_id, phoenix_span_id, description, embedding_json, root_cause,
                    remediation_steps_json, duration_seconds, eval_score, confidence_score,
                    tools_used
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    trace_id,
                    phoenix_span_id,
                    description,
                    json.dumps(embedding),
                    resolution.get("root_cause", ""),
                    json.dumps(resolution.get("remediation_steps", [])),
                    duration,
                    float(resolution.get("eval_score", 0.91 if self.demo_mode else 0.0)),
                    float(resolution.get("confidence_score", 0.0)),
                    ",".join(resolution.get("tools_used", [])),
                ),
            )
        return trace_id

    def update_trace_eval(self, trace_id: str, eval_result: dict) -> None:
        eval_score = float(eval_result.get("overall") or eval_result.get("score") or 0.0)
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT phoenix_span_id FROM trace_memory WHERE trace_id = ?",
                (trace_id,),
            ).fetchone()
            conn.execute(
                "UPDATE trace_memory SET eval_score = ? WHERE trace_id = ?",
                (eval_score, trace_id),
            )
        span_id = row[0] if row else None
        self.phoenix.update_trace_eval(trace_id, eval_score, eval_result, span_id=span_id)
        # Persist evaluation details in eval_history for learning and ranking
        try:
            with sqlite3.connect(self.db_path) as conn:
                # fetch root_cause + remediation steps from stored trace (if available)
                r = conn.execute(
                    "SELECT root_cause, remediation_steps_json FROM trace_memory WHERE trace_id = ?",
                    (trace_id,),
                ).fetchone()
                root_cause = r[0] if r else None
                remediation_json = r[1] if r else None
                conn.execute(
                    "INSERT INTO eval_history (trace_id, root_cause, remediation_steps_json, overall, details_json) VALUES (?, ?, ?, ?, ?)",
                    (trace_id, root_cause, remediation_json, eval_score, json.dumps(eval_result)),
                )
        except Exception as exc:  # pragma: no cover - defensive
            print(f"WARNING: Failed to persist eval_history: {exc}")

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS trace_memory (
                    trace_id TEXT PRIMARY KEY,
                    phoenix_span_id TEXT,
                    description TEXT NOT NULL,
                    embedding_json TEXT NOT NULL,
                    root_cause TEXT,
                    remediation_steps_json TEXT,
                    duration_seconds REAL,
                    eval_score REAL DEFAULT 0,
                    confidence_score REAL DEFAULT 0,
                    tools_used TEXT
                )
                """
            )
            # store historical evaluator judgments for learning and ranking
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS eval_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trace_id TEXT,
                    root_cause TEXT,
                    remediation_steps_json TEXT,
                    overall REAL,
                    details_json TEXT,
                    created_at REAL DEFAULT (strftime('%s','now'))
                )
                """
            )

    def _embed(self, text: str, task_type: str) -> list[float]:
        """
        Produce an embedding for `text`.
        Preferred order:
         1. local `sentence-transformers` model if available
         2. Gemini cloud embeddings if `GEMINI_API_KEY` is set
         3. deterministic demo fallback
        """
        # Prefer Gemini embeddings when an API key is configured for reproducible cloud embeddings.
        if not self.demo_mode and os.getenv("GEMINI_API_KEY"):
            try:
                import google.generativeai as genai

                genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
                result = genai.embed_content(
                    model="models/text-embedding-004",
                    content=text,
                    task_type=task_type,
                )
                return list(result["embedding"])
            except Exception as exc:
                print(f"WARNING: Gemini embedding failed, using demo fallback: {exc}")

        # 2) local model (optional)
        if self._embed_model is not None:
            try:
                vec = self._embed_model.encode([text], show_progress_bar=False, convert_to_numpy=True)[0]
                return vec.tolist()
            except Exception as exc:
                print(f"WARNING: local sentence-transformers embed failed, falling back: {exc}")

        # 3) demo deterministic embedding
        return _demo_embedding(text, task_type)

    def _try_load_local_model(self) -> None:
        """Attempt to load a local sentence-transformers model if available.

        This is optional; if the import or model load fails we silently continue and
        rely on cloud or demo fallbacks.
        """
        if self.demo_mode:
            return

        try:
            from sentence_transformers import SentenceTransformer

            model_name = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
            try:
                self._embed_model = SentenceTransformer(model_name)
            except Exception as e:
                # Model download or runtime missing dependencies; warn and continue.
                print(f"WARNING: Could not load SentenceTransformer('{model_name}'): {e}")
                self._embed_model = None
        except Exception:
            # sentence-transformers not installed; no local model available.
            self._embed_model = None


def cosine_similarity(a, b) -> float:
    a, b = np.array(a), np.array(b)
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


def _demo_embedding(text: str, task_type: str) -> list[float]:
    normalized = text.lower()
    if any(term in normalized for term in ["revenue", "dashboard", "wrong data"]):
        return _unit_vector(0)
    if any(term in normalized for term in ["sales", "pipeline", "stale"]):
        vec = np.zeros(16)
        vec[0] = 0.82
        vec[1] = 0.5723635208501674
        return vec.tolist()

    vec = np.zeros(16)
    for token in normalized.split():
        vec[sum(ord(ch) for ch in token) % len(vec)] += 1
    norm = np.linalg.norm(vec)
    return (vec / norm).tolist() if norm else vec.tolist()


def _unit_vector(index: int, size: int = 16) -> list[float]:
    vec = np.zeros(size)
    vec[index] = 1.0
    return vec.tolist()
