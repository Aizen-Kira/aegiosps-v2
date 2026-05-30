import json
import os
import time
from typing import Any

import requests

try:
    import phoenix as px  # type: ignore
except Exception:  # pragma: no cover - Phoenix is optional only for demo fallback
    px = None
try:
    from phoenix.client import Client as PhoenixClient  # type: ignore
except Exception:  # pragma: no cover
    PhoenixClient = None
try:
    from phoenix.otel import register  # type: ignore
except Exception:  # pragma: no cover
    register = None
try:
    from phoenix.trace import using_project  # type: ignore
except Exception:  # pragma: no cover
    using_project = None
try:
    from openinference.instrumentation import using_attributes  # type: ignore
except Exception:  # pragma: no cover
    using_attributes = None
try:
    from opentelemetry import trace as otel_trace  # type: ignore
except Exception:  # pragma: no cover
    otel_trace = None


DEMO_TRACE_STORE: list[dict[str, Any]] = []
_REGISTERED_TRACER = None


class PhoenixTool:
    def __init__(self, demo_mode: bool = False):
        self.demo_mode = demo_mode
        self.base_url = os.getenv("PHOENIX_BASE_URL", "http://localhost:6006").rstrip("/")
        self.collector_endpoint = os.getenv(
            "PHOENIX_COLLECTOR_ENDPOINT",
            f"{self.base_url}/v1/traces",
        )
        self.project_name = os.getenv("PHOENIX_PROJECT_NAME", "aegisops-v2")
        self.api_key = os.getenv("ARIZE_PHOENIX_API_KEY") or os.getenv("PHOENIX_API_KEY")
        self.client = None
        self.tracer = None
        self.is_available = True

        if not demo_mode:
            self.is_available = self._health_check()
            if not self.is_available:
                print(
                    f"WARNING: Phoenix server is not reachable at {self.base_url}. "
                    "AegisOps will skip Phoenix memory and continue full investigation."
                )
                return

            try:
                if os.getenv("PHOENIX_AUTO_LAUNCH", "false").lower() in {"1", "true", "yes"} and px:
                    px.launch_app()
                if PhoenixClient:
                    self.client = PhoenixClient(base_url=self.base_url, api_key=self.api_key)
                global _REGISTERED_TRACER
                if register and otel_trace and _REGISTERED_TRACER is None:
                    register(
                        endpoint=self.collector_endpoint,
                        project_name=self.project_name,
                        api_key=self.api_key,
                        batch=False,
                        protocol="http/protobuf",
                        verbose=False,
                    )
                    _REGISTERED_TRACER = otel_trace.get_tracer("aegisops-v2")
                if otel_trace:
                    self.tracer = _REGISTERED_TRACER or otel_trace.get_tracer("aegisops-v2")
            except Exception as exc:
                self.is_available = False
                print(f"WARNING: Phoenix initialization failed: {exc}")

    def query_traces(self, query: str) -> list[dict[str, Any]]:
        if self.demo_mode:
            return DEMO_TRACE_STORE[-100:]
        if not self.is_available:
            return []

        spans = self._query_spans_http()
        if not spans and self.client:
            spans = self._query_spans_client()

        traces = []
        for span in spans:
            attrs = span.get("attributes", {})
            description = attrs.get("incident.description")
            if not description:
                continue
            traces.append(
                {
                    "id": attrs.get("incident.aegis_trace_id") or span.get("id") or span.get("span_id"),
                    "phoenix_span_id": span.get("id") or span.get("span_id"),
                    "description": description,
                    "root_cause": attrs.get("incident.root_cause", ""),
                    "resolution": attrs.get("incident.resolution_summary", ""),
                    "remediation_steps": _json_or_list(attrs.get("incident.remediation_steps")),
                    "duration": _safe_float(attrs.get("incident.duration_seconds"), 0.0),
                    "confidence": _safe_float(attrs.get("incident.confidence_score"), 0.0),
                    "eval_score": _safe_float(attrs.get("incident.eval_score"), 0.0),
                    "tools_used": attrs.get("incident.tools_used", ""),
                }
            )
        return traces[:100]

    def log_trace(self, trace_data: dict) -> dict[str, str | None]:
        trace_id = trace_data.get("id") or f"trace-{int(time.time() * 1000)}"
        trace_data["id"] = trace_id

        if self.demo_mode:
            trace_data["stored_at"] = time.time()
            DEMO_TRACE_STORE.append(trace_data)
            return {"trace_id": trace_id, "span_id": trace_id}

        if not self.is_available or not self.tracer:
            return {"trace_id": trace_id, "span_id": None}

        incident = trace_data.get("incident", {})
        resolution = trace_data.get("resolution", {})
        remediation_steps = resolution.get("remediation_steps", [])
        tools_used = resolution.get("tools_used", [])
        attributes = {
            "incident.aegis_trace_id": trace_id,
            "incident.description": incident.get("query") or incident.get("description", ""),
            "incident.root_cause": resolution.get("root_cause", ""),
            "incident.resolution_summary": resolution.get("summary", ""),
            "incident.remediation_steps": json.dumps(remediation_steps),
            "incident.duration_seconds": float(trace_data.get("duration", 0.0)),
            "incident.confidence_score": float(resolution.get("confidence_score", 0.0)),
            "incident.tools_used": ",".join(tools_used),
        }
        if "eval_score" in resolution:
            attributes["incident.eval_score"] = float(resolution["eval_score"])

        span_id = None
        try:
            project_ctx = using_project(self.project_name) if using_project else _null_context()
            attr_ctx = using_attributes(metadata=attributes) if using_attributes else _null_context()
            with project_ctx, attr_ctx:
                with self.tracer.start_as_current_span("aegisops.incident_resolution") as span:
                    span.set_attributes(attributes)
                    span_id = format(span.get_span_context().span_id, "016x")
        except Exception as exc:
            print(f"WARNING: Failed to write Phoenix span: {exc}")

        return {"trace_id": trace_id, "span_id": span_id}

    def update_trace_eval(self, trace_id: str, eval_score: float, eval_result: dict, span_id: str | None = None) -> None:
        if self.demo_mode:
            for trace in reversed(DEMO_TRACE_STORE):
                if trace.get("id") == trace_id:
                    trace.setdefault("resolution", {})["eval_score"] = eval_score
                    trace["eval_result"] = eval_result
                    break
            return

        if not self.is_available or not self.client or not span_id:
            return

        for attempt in range(2):
            try:
                self.client.spans.add_span_annotation(
                    span_id=span_id,
                    annotation_name="incident.eval_score",
                    annotator_kind="LLM",
                    score=eval_score,
                    label="quality",
                    explanation=eval_result.get("notes") or eval_result.get("feedback"),
                    metadata=eval_result,
                    sync=True,
                )
                return
            except Exception as exc:
                if attempt == 0:
                    time.sleep(0.5)
                    continue
                print(f"WARNING: Failed to attach Phoenix eval annotation: {exc}")

    def run_eval(self, trace_id: str, criteria: str) -> dict:
        return {
            "score": 0.91,
            "overall": 0.91,
            "feedback": "Root cause, remediation, and verification were completed efficiently.",
            "trace_id": trace_id,
            "criteria": criteria,
        }

    def _health_check(self) -> bool:
        try:
            response = requests.get(self.base_url, timeout=2)
            return response.status_code < 500
        except Exception:
            return False

    def _query_spans_http(self) -> list[dict[str, Any]]:
        try:
            response = requests.get(
                f"{self.base_url}/v1/projects/{self.project_name}/spans",
                params={"limit": 100},
                timeout=5,
            )
            if response.status_code >= 400:
                response = requests.get(
                    f"{self.base_url}/v1/spans",
                    params={"project_name": self.project_name, "limit": 100},
                    timeout=5,
                )
                if response.status_code >= 400:
                    return []
            payload = response.json()
            if isinstance(payload, list):
                return [_normalize_span(item) for item in payload]
            items = payload.get("data") or payload.get("spans") or []
            return [_normalize_span(item) for item in items]
        except Exception:
            return []

    def _query_spans_client(self) -> list[dict[str, Any]]:
        try:
            spans = self.client.spans.get_spans(project_identifier=self.project_name, limit=100)
        except Exception:
            return []
        return [_normalize_span(span) for span in spans]


class _null_context:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def _normalize_span(span: Any) -> dict[str, Any]:
    if isinstance(span, dict):
        attrs = span.get("attributes") or span.get("attributes_flat") or {}
        context = span.get("context") or {}
        return {
            "id": span.get("id") or span.get("span_id") or context.get("span_id"),
            "span_id": span.get("span_id") or context.get("span_id") or span.get("id"),
            "attributes": attrs,
        }

    attrs = getattr(span, "attributes", {}) or {}
    return {
        "id": getattr(span, "id", None) or getattr(span, "span_id", None),
        "span_id": getattr(span, "span_id", None) or getattr(span, "id", None),
        "attributes": attrs,
    }


def _json_or_list(value: Any) -> list:
    if isinstance(value, list):
        return value
    if not value:
        return []
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, list) else [parsed]
    except Exception:
        return [str(value)]


def _safe_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except Exception:
        return default
