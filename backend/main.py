import json
import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse
from pydantic import BaseModel
from dotenv import load_dotenv
from agent.orchestrator import IncidentOrchestrator
from agent.tools.phoenix import DEMO_TRACE_STORE

load_dotenv()

app = FastAPI(title="AegisOps v2 API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory store for demo metrics
incident_history = []
DEMO_MODE = os.getenv("DEMO_MODE", "true").lower() in {"1", "true", "yes"}

class IncidentRequest(BaseModel):
    query: str

@app.post("/api/incident")
async def create_incident(request: IncidentRequest):
    orchestrator = IncidentOrchestrator(demo_mode=DEMO_MODE)
    
    async def event_generator():
        async for event in orchestrator.resolve_incident(request.query):
            if event["step"] == "COMPLETE":
                incident_history.append(event["data"]["duration"])
            yield {
                "event": "message",
                "data": json.dumps(event)
            }
            
    return EventSourceResponse(event_generator())

@app.get("/api/metrics")
async def get_metrics():
    total = len(incident_history)
    avg_time = sum(incident_history) / total if total > 0 else 0
    
    # Simulate improvement ratio
    improvement = 0
    if total >= 2:
        improvement = (incident_history[0] - incident_history[-1]) / incident_history[0] * 100

    return {
        "total_incidents": total,
        "avg_resolution_time": round(avg_time, 2),
        "improvement_ratio": round(improvement, 1),
        "traces_stored": total
    }

@app.get("/api/traces")
async def get_traces():
    traces = DEMO_TRACE_STORE[-10:]
    if traces:
        return [
            {
                "id": trace["id"],
                "incident": trace.get("incident", {}).get("query", "Unknown incident"),
                "duration": trace.get("duration", 0),
                "status": trace.get("resolution", {}).get("status", "resolved"),
                "root_cause": trace.get("resolution", {}).get("root_cause"),
                "eval_score": trace.get("resolution", {}).get("eval_score") or trace.get("eval_score"),
            }
            for trace in traces
        ]

    return [
        {"id": f"trace-{i + 1}", "incident": "Revenue dashboard mismatch", "duration": d, "status": "resolved"}
        for i, d in enumerate(incident_history[-10:])
    ]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
