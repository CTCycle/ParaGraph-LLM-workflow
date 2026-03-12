# ParaGraph Easy Retrieval

ParaGraph is a local-first workflow builder for LLM orchestration.
It ships with a FastAPI backend and a React + TypeScript frontend with a Canvas2D graph editor, typed workflow contracts, compile/execute services, and websocket runtime events.

## 1. Project Structure

```text
ParaGraph/
- client/                   # React + TypeScript + Vite frontend
- server/                   # FastAPI backend (routes/entities/services/repositories)
- scripts/                  # Utility scripts (database initialization)
- settings/                 # .env profiles + configurations.json
- resources/                # logs, checkpoints, database, runtime data
- start_on_windows.bat      # Windows launcher and runtime bootstrap

tests/
- conftest.py
- run_tests.bat
- unit/server/...           # Backend unit/API tests
```

## 2. Active API Surface

Compatibility workflow API:
- `/workflow/catalog`
- `/workflow/validate`
- `/workflow/execute`
- `/workflow/jobs/{job_id}`

Platform APIs:
- `/workflows`
- `/workflows/{workflow_id}`
- `/workflows/{workflow_id}/versions`
- `/executions/compile`
- `/executions`
- `/executions/{run_id}`
- `/executions/{run_id}/events`
- `/nodes/catalog`
- `/providers/catalog`
- websocket: `/workflow/ws/runs/{run_id}`

## 3. Architecture Highlights

- Backend contracts live in `ParaGraph/server/entities`.
- Compiler/execution/provider/node-registry services are separated under `ParaGraph/server/services/workflow`.
- Runtime events are typed and streamed via websocket through `services/runtime/events.py`.
- Frontend graph rendering is Canvas2D-based (`client/src/graph/canvas/GraphCanvas.tsx`).
- Frontend state is separated into workflow/runtime/ui/catalog stores (`client/src/app/stores`).
- Workflow persistence is schema-versioned in localStorage (`paragraph.workflow.document.v1`) with legacy migration support.

## 4. Installation

### 4.1 Windows (recommended)

1. Ensure `ParaGraph/settings/.env` exists.
2. Launch the local web app:

```cmd
ParaGraph\start_on_windows.bat
```

Supported local delivery modes:
- local web app started by `ParaGraph\start_on_windows.bat`
- packaged desktop app distributed separately as a Tauri build

### 4.2 macOS / Linux (manual)

Prerequisites:
- Python 3.14+
- Node.js 22+
- `uv`

```bash
uv sync
cd ParaGraph/client && npm install && npm run build
cd ../..
uv run python -m uvicorn ParaGraph.server.app:app --host 127.0.0.1 --port 5002
cd ParaGraph/client && npm run preview -- --host 127.0.0.1 --port 8002
```

## 5. Testing

Run backend tests:

```cmd
tests\run_tests.bat
```

Or:

```cmd
.\.venv\Scripts\python.exe -m pytest tests/unit -v
```

## 6. Configuration

Main runtime config: `ParaGraph/settings/.env`

Important variables:
- `FASTAPI_HOST`, `FASTAPI_PORT`
- `UI_HOST`, `UI_PORT`
- `VITE_API_BASE_URL`
- `DB_EMBEDDED`, `DB_*`
- `OLLAMA_BASE_URL`
- `OPENAI_API_KEY`, `OPENAI_BASE_URL`
- `GEMINI_API_KEY`, `GEMINI_BASE_URL`
- `ANTHROPIC_API_KEY`
- `LLM_TIMEOUT_S`
