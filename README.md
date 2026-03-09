# ParaGraph Easy Retrieval

ParaGraph is a local-first workflow builder for retrieval and LLM orchestration. It provides a FastAPI backend and a React workflow canvas where users compose typed node graphs, inspect the node registry, validate workflows, and run them as background jobs.

Current state: workflow graph validation/execution is the most complete feature. Preparation, training, validation, and inference routes are present but still partially placeholder implementations.

## 1. Project Structure

```text
ParaGraph/
- client/                   # React + TypeScript + Vite frontend
- server/                   # FastAPI backend (routes/services/repositories)
- scripts/                  # Utility scripts (database initialization)
- settings/                 # .env profiles + configurations.json
- resources/                # logs, checkpoints, database, portable runtimes
- start_on_windows.bat      # Windows launcher and runtime bootstrap
- setup_and_maintenance.bat # Maintenance menu

docker/
- backend.Dockerfile
- frontend.Dockerfile
- nginx/default.conf

tests/
- conftest.py
- run_tests.bat
- unit/server/...           # Backend unit/API tests
```

## 2. Architecture Overview

- Backend entrypoint: `ParaGraph/server/app.py`
- Active routers:
  - `/upload`
  - `/preparation`
  - `/training`
  - `/validation`
  - `/inference`
  - `/workflow`
- Workflow service (`server/services/workflow/executor.py`) provides:
  - node catalog
  - graph validation (topology, type compatibility, category rules)
  - execution with LLM provider dispatch
- Long-running work uses `server/services/jobs.py` with polling/cancellation endpoints.
- Frontend workflow UI is implemented in `client/src/pages/WorkflowPage.tsx` using `@xyflow/react`.
- Node registry and system guidance live in `client/src/pages/NodesPage.tsx`.

## 3. Installation

### 3.1 Windows (recommended)

1. Ensure `ParaGraph/settings/.env` exists (copy from local profile if needed):
   - `copy /Y ParaGraph\settings\.env.local.example ParaGraph\settings\.env`
2. Launch:
   - `ParaGraph\start_on_windows.bat`

First run installs portable Python, uv, and Node.js under `ParaGraph/resources/runtimes`, syncs backend/frontend dependencies, builds the client, and starts backend + UI.

### 3.2 macOS / Linux (manual)

Prerequisites:
- Python 3.14+
- Node.js 22+
- `uv`

Install and run:

```bash
uv sync
cd ParaGraph/client && npm install && npm run build
cd ../..
uv run python -m uvicorn ParaGraph.server.app:app --host 127.0.0.1 --port 5002
cd ParaGraph/client && npm run preview -- --host 127.0.0.1 --port 8002
```

## 4. How to Use

1. Open the UI at `http://<UI_HOST>:<UI_PORT>`.
2. Open `Nodes` to inspect the current node catalog, typed ports, and runnable-vs-catalog-only status.
3. In `Workflow`, add nodes from the top-right controls or by right-clicking on the canvas.
4. Connect ports (Prompt -> LLM -> Output).
5. Configure node parameters.
6. Click `Run` to validate and execute.
7. Watch status updates while backend job runs.
8. Read generated text from Output node `outputText` field.

Notes:
- Graph state is persisted in browser localStorage key `paragraph.workflow.graph`.
- LLM provider credentials/URLs come from `.env`.

## 5. Setup and Maintenance

Use `ParaGraph/setup_and_maintenance.bat`:
- Remove logs.
- Uninstall local runtime artifacts (`resources/runtimes`, `.venv`, frontend build/deps).
- Initialize database (`ParaGraph/scripts/initialize_database.py`).

## 6. Testing

Run backend tests:

```cmd
tests\run_tests.bat
```

Direct pytest invocation:

```cmd
.\.venv\Scripts\python.exe -m pytest tests/unit -v
```

Current automated coverage is focused on workflow routes/executor and job manager behavior.

## 7. Configuration

Main runtime config file: `ParaGraph/settings/.env`

Key variables:

| Variable | Description |
|---|---|
| `FASTAPI_HOST`, `FASTAPI_PORT` | Backend bind address. |
| `UI_HOST`, `UI_PORT` | Frontend host/port. |
| `VITE_API_BASE_URL` | Frontend API base path (`/api` default). |
| `DB_EMBEDDED` | `true` for SQLite; `false` for PostgreSQL. |
| `DB_*` | External DB connection settings when not embedded. |
| `OLLAMA_BASE_URL` | Local Ollama endpoint. |
| `OPENAI_API_KEY`, `OPENAI_BASE_URL` | OpenAI provider settings. |
| `GEMINI_API_KEY`, `GEMINI_BASE_URL` | Gemini provider settings. |
| `LLM_TIMEOUT_S` | LLM request timeout in seconds. |

Non-runtime defaults (`jobs.polling_interval`, seed, base DB mode) live in `ParaGraph/settings/configurations.json`.

## 8. Docker Deployment

```bash
docker compose --env-file ParaGraph/settings/.env build --no-cache
docker compose --env-file ParaGraph/settings/.env up -d
```

- Frontend is served by Nginx.
- `/api/*` is proxied to backend container.

Stop:

```bash
docker compose --env-file ParaGraph/settings/.env down
```


