# ParaGraph Architecture

ParaGraph is a FastAPI + React application for building and executing node-based workflow graphs.
The current implementation is an MVP with one fully wired workflow path and additional domain routes that still use placeholder job runners.

---

## 1. Repository Layout

- `ParaGraph/server`: FastAPI backend.
  - `app.py`: app creation and router registration.
  - `routes/`: HTTP endpoints (`upload`, `preparation`, `training`, `validation`, `inference`, `workflow`).
  - `services/jobs.py`: in-process background job manager.
  - `services/workflow/executor.py`: workflow catalog, validation, execution.
  - `services/llm/providers.py`: Ollama/OpenAI/Gemini/Anthropic provider clients (Anthropic currently placeholder).
  - `repositories/`: SQLAlchemy schema + SQLite/PostgreSQL adapters + query/serialization helpers.
  - `configurations/`: JSON + environment settings loader.
- `ParaGraph/client`: React + TypeScript frontend.
  - `src/pages/WorkflowPage.tsx`: React Flow canvas, graph persistence, run orchestration.
  - `src/components/workflow/WorkflowNodeCard.tsx`: node UI and parameter editors.
  - `src/services/workflow.ts`: API client + polling helpers.
- `ParaGraph/settings`: `.env` runtime profiles and `configurations.json`.
- `ParaGraph/resources`: logs, checkpoints, database file, and portable runtimes used by the Windows launcher.
- `docker/`: backend/frontend Dockerfiles and Nginx reverse proxy config.
- `tests/unit`: pytest coverage for app wiring, workflow routes/executor, and job manager behavior.

---

## 2. Runtime Topology

### Local launcher path (`ParaGraph/start_on_windows.bat`)
- Downloads/sets up portable Python, `uv`, and Node.js into `ParaGraph/resources/runtimes`.
- Runs backend as `uv run python -m uvicorn ParaGraph.server.app:app`.
- Builds frontend once (`npm run build`) and serves it with `npm run preview`.
- Opens the UI URL from `UI_HOST:UI_PORT`.

### Docker path
- `backend` container runs Uvicorn on port `8000`.
- `frontend` container runs Nginx and serves built static assets.
- Nginx proxies `/api/*` to `backend:8000/*`.

### API routing model
- Frontend uses `VITE_API_BASE_URL` (default `/api`).
- Local Vite preview and Docker Nginx both proxy to backend, so CORS is avoided in normal usage.

---

## 3. Backend Architecture

### 3.1 App composition
`ParaGraph/server/app.py` registers these routers:
- `/upload`
- `/preparation`
- `/training`
- `/validation`
- `/inference`
- `/workflow`

Root (`/`) redirects to `/docs`.

### 3.2 Job execution model
- All long-running tasks run through singleton `job_manager` (`ParaGraph/server/services/jobs.py`).
- Execution is thread-based only in this repository state.
- Jobs expose shared lifecycle fields: `pending`, `running`, `completed`, `failed`, `cancelled`.
- Cancellation is cooperative (`cancel_job` sets `stop_requested`; runners must call `should_stop`).
- Route handlers return `job_id` and expose `GET/DELETE /jobs/{job_id}` patterns for polling/cancel.

See `BACKGROUND_JOBS.md` for implementation details.

### 3.3 Workflow subsystem (currently most complete path)

#### Catalog
`GET /workflow/catalog` returns node definitions:
- `Prompt` (input)
- `LLM` (process)
- `Retrieval` (process, catalog-visible placeholder)
- `VectorDB` (process, catalog-visible placeholder)
- `Output` (output)

#### Validation
`POST /workflow/validate` checks:
- duplicate ids
- missing source/target references
- category flow constraints (`input->process`, `process->process`, `process->output`)
- handle existence and type compatibility
- DAG acyclicity
- connected-node executor support (only `Prompt`, `LLM`, `Output` supported by MVP executor)

#### Execution
`POST /workflow/execute`:
- validates graph first
- starts a background job
- executes nodes topologically
- calls selected LLM provider for `LLM` nodes
- writes output text into `outputs` map keyed by output node id

### 3.4 Additional domain routes (MVP placeholders)
- `upload`: parses CSV/XLSX into in-memory upload state.
- `preparation`: dataset browsing/linking + simulated preparation job.
- `training`: checkpoint listing + simulated epoch loop.
- `validation`: simulated validation/evaluation jobs and in-memory report maps.
- `inference`: checkpoint listing + simulated inference output.

These routes are API-stable for UI integration but still return placeholder metrics/results in several flows.

---

## 4. Persistence and Data Layer

### 4.1 Database modes
- Embedded SQLite when `DB_EMBEDDED=true`.
- External PostgreSQL when `DB_EMBEDDED=false`.

### 4.2 Schema (SQLAlchemy)
Current tables:
- `datasets`
- `dataset_records`
- `processing_runs`
- `training_samples`
- `validation_runs`
- `checkpoints`
- `inference_runs`
- `inference_reports`

### 4.3 Repository adapters
- `SQLiteRepository` and `PostgresRepository` share `load/save/upsert/count` operations.
- `ParaGraphDatabase` selects backend from environment/config settings at startup.
- Database initialization script: `ParaGraph/scripts/initialize_database.py`.

---

## 5. Frontend Architecture

- Router entrypoint: `src/App.tsx`.
- Main implemented page: `WorkflowPage`.
- Placeholder pages exist for `Configurations`, `Edit`, and `Help`.
- Workflow canvas:
  - built with `@xyflow/react`
  - supports Add Node (toolbar + context menu)
  - enforces connection validity client-side
  - persists graph in `localStorage` key `paragraph.workflow.graph`
  - triggers validate -> execute -> poll flow and writes returned output text into `Output` nodes

---

## 6. Logging and Observability

- Logger is configured in `ParaGraph/server/common/utils/logger.py`.
- Console handler: `INFO` with minimal format.
- File handler: `DEBUG` with timestamped entries under `ParaGraph/resources/logs/`.
- Job status payloads are the primary progress surface consumed by the frontend.

---

## 7. Extension Guidance

- New API capability: add service logic under `server/services`, expose via `server/routes`, include router in `server/app.py`.
- New workflow node:
  - add definition in `services/workflow/executor.py`
  - extend execution logic for that node type
  - add corresponding frontend parameter handling via catalog-driven UI.
- New long-running operation: use `job_manager.start_job(...)`, expose polling/cancel endpoints, and keep worker cancellation cooperative.
