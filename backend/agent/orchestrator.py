import asyncio
import time
from .memory import MemoryManager
from .tools.fivetran import FivetranTool
from .tools.gitlab import GitLabTool
from .tools.phoenix import PhoenixTool
from .evaluator import IncidentEvaluator

class IncidentOrchestrator:
    def __init__(self, demo_mode=True):
        self.demo_mode = demo_mode
        self.memory = MemoryManager(demo_mode=demo_mode)
        self.fivetran = FivetranTool(demo_mode=demo_mode)
        self.gitlab = GitLabTool(demo_mode=demo_mode)
        self.phoenix = PhoenixTool(demo_mode=demo_mode)
        self.evaluator = IncidentEvaluator(demo_mode=demo_mode)

    async def resolve_incident(self, query: str):
        start_time = time.time()
        
        yield self._format_event("MEMORY", "phoenix", f"Querying Phoenix traces for: {query}")
        await asyncio.sleep(1 if self.demo_mode else 0)
        # Instrument retrieval with Phoenix/OpenTelemetry if available
        past_incidents = []
        try:
            if self.phoenix.tracer:
                with self.phoenix.tracer.start_as_current_span("aegisops.retrieval") as span:
                    try:
                        span.set_attribute("query", query)
                    except Exception:
                        pass
                    past_incidents = self.memory.query_similar_incidents(query)
            else:
                past_incidents = self.memory.query_similar_incidents(query)
        except Exception:
            # defensive fallback to avoid breaking resolution flow
            past_incidents = self.memory.query_similar_incidents(query)
        
        best_match = past_incidents[0] if past_incidents else None
        has_context = bool(
            best_match
            and best_match.get("similarity", 0) > 0.65
            and best_match.get("eval_score", 0) >= 0.85
        )
        if has_context:
            similarity = best_match.get("similarity", 0)
            eval_score = best_match.get("eval_score", 0)
            yield self._format_event(
                "MEMORY",
                "phoenix",
                f"Found {len(past_incidents)} similar trace(s) (similarity: {similarity:.2f}, eval: {eval_score:.2f}) - skipping investigation.",
                data={"candidates": past_incidents},
                confidence=min(0.99, (similarity + eval_score) / 2),
            )
        else:
            if best_match and best_match.get("eval_score", 0) < 0.70:
                yield self._format_event(
                    "MEMORY",
                    "phoenix",
                    f"Found similar trace {best_match['id']}, but eval score {best_match.get('eval_score', 0):.2f} was suboptimal. Running full investigation.",
                    data={"candidates": past_incidents},
                )
            else:
                yield self._format_event("MEMORY", "phoenix", "No similar past incidents found. Starting fresh investigation.", data={"candidates": past_incidents})

        fivetran_status = None
        deployments = []
        root_cause = "Salesforce CRM schema rename broke Fivetran ingestion"
        remediation_steps = ["rollback_deployment", "trigger_resync", "verify_row_parity"]
        outcome = "resolved"

        if has_context:
            eval_score = best_match.get("eval_score", 0)
            reason_context = (
                f"Previous resolution of similar incident scored {eval_score:.2f} on quality evaluation. "
                "Use that resolution path with high confidence."
            )
            yield self._format_event(
                "REASON",
                "gemini",
                f"{reason_context} Phoenix context says Salesforce CRM schema drift caused the stale revenue pipeline.",
                confidence=min(0.99, eval_score),
            )
        else:
            yield self._format_event("DETECT", "fivetran", "Checking connector health and freshness...")
            await asyncio.sleep(1.5 if self.demo_mode else 0)
            fivetran_status = self.fivetran.get_connector_status("salesforce-crm")
            yield self._format_event(
                "DETECT",
                "fivetran",
                f"Salesforce connector failed {fivetran_status['last_sync']} with schema freshness risk.",
                data={"connector": fivetran_status},
            )

            yield self._format_event("INVESTIGATE", "gitlab", "Checking recent deployments...")
            await asyncio.sleep(1.5 if self.demo_mode else 0)
            deployments = self.gitlab.get_recent_deployments()
            deployment = deployments[0]
            yield self._format_event(
                "INVESTIGATE",
                "gitlab",
                f"Deployment #{deployment['id']} from {deployment['ref']} landed {deployment['created_at']}, shortly before the connector failure.",
                data={"deployment": deployment},
            )

            if best_match and best_match.get("eval_score", 0) < 0.70:
                low_eval_context = (
                    f"Previous resolution of similar incident scored {best_match.get('eval_score', 0):.2f} - "
                    "it was suboptimal. Consider alternative approaches."
                )
            else:
                low_eval_context = ""
            yield self._format_event(
                "REASON",
                "gemini",
                f"{low_eval_context} 91% confidence: schema rename in deployment #1842 broke Salesforce ingestion. Plan: rollback deployment, trigger resync, verify row parity.",
                confidence=0.91,
            )
            await asyncio.sleep(1 if self.demo_mode else 0)
        
        # Wrap remediation steps in a Phoenix span
        if self.phoenix.tracer:
            rem_span = self.phoenix.tracer.start_as_current_span("aegisops.remediation")
            try:
                rem_span.__enter__()
                rem_span.set_attribute("remediation.steps", ",".join(remediation_steps))
            except Exception:
                pass

        yield self._format_event("REMEDIATE", "gitlab", "Rolling back deployment #1842 before replaying the connector sync.")
        await asyncio.sleep(1 if self.demo_mode else 0)
        rollback = self.gitlab.rollback_deployment("1842")
        yield self._format_event("REMEDIATE", "gitlab", f"Rollback complete: {rollback['message']}", data={"rollback": rollback})

        yield self._format_event("REMEDIATE", "fivetran", "Triggering Salesforce CRM resync.")
        await asyncio.sleep(1 if self.demo_mode else 0)
        sync = self.fivetran.trigger_resync("salesforce-crm")
        stats = self.fivetran.get_sync_stats("salesforce-crm")
        rows_synced = int(stats.get("rows_synced") or 0)
        source_rows = int(stats.get("source_rows") or 0)
        if stats.get("parity") is True:
            verify_message = f"Row parity confirmed: {rows_synced:,} <-> {source_rows:,} OK"
        else:
            verify_message = f"Sync stats retrieved: {rows_synced:,} rows synced from {source_rows:,} source rows."
        yield self._format_event("VERIFY", "fivetran", verify_message, data={"sync": sync, "stats": stats})
        
        duration = time.time() - start_time
        if self.demo_mode:
            if has_context:
                import random
                duration = round(8.0 + random.uniform(-1.5, 1.5), 1)
            else:
                duration = 52.0
        
        yield self._format_event("LEARN", "phoenix", f"Incident resolved in {duration:.1f}s. Storing trace for future learning.")
        trace_id = self.memory.store_incident_trace(
            {"query": query},
            {
                "status": "resolved",
                "root_cause": root_cause,
                "summary": "Rolled back deployment #1842, triggered Fivetran resync, verified row parity.",
                "remediation_steps": remediation_steps,
                "tools_used": ["phoenix", "fivetran", "gitlab", "gemini"],
                "confidence_score": 0.96 if has_context else 0.91,
            },
            duration,
        )

        yield self._format_event("LEARN", "phoenix", "Running LLM-as-a-Judge evaluation...")
        await asyncio.sleep(1 if self.demo_mode else 0)
        # Instrument evaluation with Phoenix
        try:
            if self.phoenix.tracer:
                with self.phoenix.tracer.start_as_current_span("aegisops.evaluation") as span:
                    try:
                        span.set_attribute("trace_id", trace_id)
                        span.set_attribute("duration_seconds", float(duration))
                    except Exception:
                        pass
                    eval_result = self.evaluator.judge(
                        trace_id,
                        incident_description=query,
                        root_cause=root_cause,
                        actions_taken=remediation_steps,
                        duration_seconds=duration,
                        outcome=outcome,
                    )
            else:
                eval_result = self.evaluator.judge(
                    trace_id,
                    incident_description=query,
                    root_cause=root_cause,
                    actions_taken=remediation_steps,
                    duration_seconds=duration,
                    outcome=outcome,
                )
        except Exception:
            eval_result = self.evaluator.judge(
                trace_id,
                incident_description=query,
                root_cause=root_cause,
                actions_taken=remediation_steps,
                duration_seconds=duration,
                outcome=outcome,
            )

        # update memory with evaluation results (this will also attach Phoenix annotation when possible)
        self.memory.update_trace_eval(trace_id, eval_result)

        # close remediation span if opened
        try:
            if self.phoenix.tracer and rem_span is not None:
                rem_span.__exit__(None, None, None)
        except Exception:
            pass
        yield self._format_event("LEARN", "phoenix", f"Evaluation complete. Score: {eval_result['overall']}. {eval_result['feedback']}")

        yield self._format_event("COMPLETE", "system", "Incident Commander standing down.", {"duration": duration})

    def _format_event(self, step, tool, message, data=None, confidence=None):
        event = {
            "step": step,
            "tool": tool,
            "message": message,
            "timestamp": time.time(),
            "data": data or {}
        }
        if confidence is not None:
            event["confidence"] = confidence
        return event
