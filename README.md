# AegisOps v2 - Self-Evolving Incident Commander

AegisOps v2 is an autonomous AI operations agent for the Google Cloud Rapid Agent Hackathon Arize track. It investigates enterprise data incidents, remediates them through Fivetran and GitLab actions, and stores every resolution in Arize Phoenix. The demo proves self-improvement by resolving a repeat incident faster after querying its own prior trace.

## How the self-improvement loop works

1. Incident fires -> AegisOps queries Phoenix for similar past traces
2. Traces ranked by semantic similarity x eval quality score
3. High-scoring matched trace -> skip investigation, use known fix
4. After resolution -> store new trace + run LLM-as-a-Judge evaluation
5. Eval score updates trace ranking for future queries
6. Result: each incident makes the next one faster and more accurate

## Architecture

```text
User -> FastAPI (SSE) -> Orchestrator -> [Phoenix MCP, Fivetran MCP, GitLab MCP]
                                             |
                                   Gemini (reasoning)
                                             |
                                   Phoenix trace store (memory)
                                             |
                                   LLM-as-a-Judge (eval -> feedback)
```

The Next.js dashboard sits in front of the SSE stream and renders the incident input, live reasoning timeline, integration status, Phoenix trace viewer, metrics, and learning curve chart.

## Run Locally From a Fresh Clone

Prerequisites:

- Node.js 20+
- Python 3.11+
- Docker Desktop, if using Compose

Create local environment files:

```bash
cp .env.example .env
cp .env.example backend/.env
cp .env.example frontend/.env.local
```

The app defaults to `DEMO_MODE=true`, so it can run without live Gemini, Fivetran, GitLab, or Phoenix API keys. Add real keys to the copied environment files only when connecting live services.

Start Phoenix first for real Arize trace storage:

```bash
python -m phoenix.server.main serve --port 6006
```

In a second terminal, start the backend:

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

On Windows PowerShell, activate the backend virtual environment with:

```powershell
.\venv\Scripts\Activate.ps1
```

In a third terminal, start the frontend:

```bash
cd frontend
npm install
npm run dev
```

The frontend runs at `http://localhost:3000` and the backend runs at `http://localhost:8000`.

## Docker Compose

For a containerized demo, start Phoenix on the host first, then run:

```bash
docker-compose up --build
```

Compose builds the frontend as a standalone Next.js app and runs the backend on Uvicorn. The frontend container talks to the backend at `http://backend:8000`; browser calls still use `http://localhost:8000`.

## Environment Variables

Required for local demo mode:

- `DEMO_MODE=true`
- `BACKEND_URL=http://localhost:8000`
- `NEXT_PUBLIC_BACKEND_URL=http://localhost:8000`

Optional live integrations:

- `GEMINI_API_KEY`
- `GEMINI_MODEL`
- `ARIZE_PHOENIX_API_KEY` or `PHOENIX_API_KEY`
- `PHOENIX_BASE_URL`
- `PHOENIX_COLLECTOR_ENDPOINT`
- `PHOENIX_PROJECT_NAME`
- `PHOENIX_AUTO_LAUNCH`
- `SIMILARITY_THRESHOLD`
- `EMBEDDING_MODEL`
- `FIVETRAN_API_KEY`
- `FIVETRAN_API_SECRET`
- `FIVETRAN_CONNECTOR_ID`
- `GITLAB_TOKEN`
- `GITLAB_PROJECT_ID`
- `GITLAB_BASE_URL`
- `GOOGLE_CLOUD_PROJECT`
- `GOOGLE_CLOUD_REGION`

Use `.env.example` as the source of truth for safe placeholder values.

## Self-Improvement Loop

AegisOps queries its own Phoenix traces before every incident resolution. On the first revenue dashboard incident, no trace exists, so it checks Fivetran, correlates the failure with GitLab deployment #1842, rolls back the deployment, triggers a Salesforce CRM resync, verifies row parity, and stores the trace.

When a similar incident appears again, Phoenix returns the prior trace with high confidence. AegisOps skips broad investigation, applies the proven resolution path, and the learning chart shows the core demo proof: 52 seconds down to 8 seconds.

LLM-as-a-Judge evaluates each stored resolution, and that score becomes part of the trace memory future incidents can use.

## Demo Video

Demo video link: coming soon.

## Compliance

AegisOps v2 uses Google Cloud Run for hosting and Gemini for agent reasoning. Arize Phoenix is the primary observability and learning engine: the agent queries Phoenix traces before every incident, stores complete traces after every resolution, and runs LLM-as-a-Judge evaluation to measure resolution quality.

## Deploy

```bash
export GOOGLE_CLOUD_PROJECT="your-project-id"
./deploy.sh
```

The deploy script builds and deploys both backend and frontend Cloud Run services, then prints the public app URL.
