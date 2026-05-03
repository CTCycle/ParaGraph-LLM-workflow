# ARCHITECTURE

Last updated: 2026-05-03

## System Summary

ParaGraph is a local-first workflow platform composed of:

- FastAPI backend (`app/server`) for compile/execute APIs, node catalog, provider integrations, configuration management, and execution event streaming.
- React + TypeScript frontend (`app/client/src`) for workflow editing, node/template browsing, model catalog operations, and runtime monitoring.
- Optional Tauri desktop wrapper (`app/client/src-tauri`) that launches the backend process and loads the web UI in a desktop window.

## Repository Structure

The project includes source code plus generated/runtime-heavy folders. Expanded structure below focuses on authoritative implementation files and runtime-critical artifacts.

```text
.
|- assets/
|  |- docs/
|  |  |- ARCHITECTURE.md
|  |  |- CODING_RULES.md
|  |  |- PROJECT_OVERVIEW.md
|  |  |- RUNTIME_MODES.md
|  |  `- UI_STANDARDS.md
|- ParaGraph/
|  |- client/
|  |  |- src/
|  |  |  |- App.tsx
|  |  |  |- main.tsx
|  |  |  |- index.css
|  |  |  |- app/services/ (API clients)
|  |  |  |- components/ (layout + reusable UI)
|  |  |  |- pages/ (Workflow, Nodes, Models, Configurations)
|  |  |  `- workflow/ (schema + hooks)
|  |  |- src-tauri/
|  |  |  |- src/main.rs
|  |  |  |- tauri.conf.json
|  |  |  `- Cargo.toml
|  |  |- package.json
|  |  `- vite.config.ts
|  |- server/
|  |  |- app.py
|  |  |- api/ (FastAPI routers)
|  |  |- configurations/ (env + runtime config loading)
|  |  |- domain/ (Pydantic/domain models)
|  |  |- services/ (business logic)
|  |  |- repositories/ (file/db persistence)
|  |  `- common/ (constants, security, logging)
|  |- resources/ (runtime data: db, logs, models, nodes, workflows, artifacts)
|  |- settings/ (.env variants + configurations.json)
|  |- scripts/ (maintenance/init scripts)
|  |- start_on_windows.bat
|  `- setup_and_maintenance.bat
|- release/
|  |- tauri/ (desktop build scripts)
|  `- windows/ (packaged artifacts)
|- runtimes/ (portable Python/uv/Node + .venv + uv.lock)
|- tests/
|  |- unit/server/...
|  `- e2e/server/...
|- pyproject.toml
|- uv.lock
`- README.md
```

## Application Entry Points

- Backend app factory: `app/server/app.py` (`create_app`, exported as `app`).
- Backend process startup:
  - Launcher-managed: `start_on_windows.bat` runs `python -m uvicorn server.app:app`.
  - Manual: run `uvicorn` against `server.app:app`.
- Frontend entry: `app/client/src/main.tsx` -> `App.tsx` (React Router shell).
- Desktop entry: `app/client/src-tauri/src/main.rs` (spawns backend, waits for readiness, opens UI URL).

## API Endpoints

### Root

- `GET /` (redirects to `/docs` when not cloud mode; returns JSON health in cloud mode)

### Workflows

- `GET /workflows`
- `POST /workflows`
- `GET /workflows/templates`
- `GET /workflows/{workflow_id}`
- `PUT /workflows/{workflow_id}`

### Executions

- `POST /executions/compile`
- `POST /executions`
- `GET /executions/{run_id}`
- `GET /executions/{run_id}/events`
- `WS /executions/ws/runs/{run_id}`

### Nodes

- `GET /nodes/catalog`
- `POST /nodes/import`
- `POST /nodes/uploads/directory` (multipart upload)
- `POST /nodes/check-database-connection`
- `POST /nodes/check-vector-store-connection`

### Providers

- `GET /providers/catalog`
- `GET /providers/models`
- `GET /providers/ollama/library`
- `POST /providers/ollama/pull`
- `GET /providers/huggingface/models`
- `POST /providers/huggingface/download`
- `GET /providers/huggingface/download/{job_id}`
- `DELETE /providers/huggingface/download/{job_id}`

### Configurations

- `GET /configurations`
- `PUT /configurations`
- `GET /configurations/profiles`
- `GET /configurations/profiles/{profile_name}`
- `PUT /configurations/profiles/{profile_name}`
- `POST /configurations/ollama/ping`

## Layered Architecture

Typical backend flow follows endpoint -> service -> repository:

- Workflows:
  `api/workflows.py` -> `services/workflow/workflow.py` -> `repositories/workflow/workflow.py`
- Execution lifecycle:
  `api/executions.py` -> `services/workflow/compiler/service.py` + `services/workflow/execution.py` -> in-memory run/event repositories
- Configurations:
  `api/configurations.py` -> `services/configuration.py` -> `repositories/configuration.py` -> SQLAlchemy models in `repositories/schemas/models.py`
- Provider catalogs/downloads:
  `api/providers.py` -> `services/workflow/provider/service.py`, with provider helper, catalog, download, and mixin modules under `services/workflow/provider/` (+ jobs/event systems)

## Responsibilities of Key Modules

- `server/api/*`: HTTP/WebSocket boundary, request validation, HTTP status mapping.
- `server/domain/*`: request/response models, workflow schema, execution/event models.
- `server/services/workflow/compiler/service.py`: graph validation, diagnostics, topological planning.
- `server/services/workflow/execution.py`: step orchestration, cache, output shaping, event publishing.
- `server/services/workflow/provider/service.py`: provider facade, model metadata, and download orchestration.
- `server/services/workflow/provider/helpers.py`: shared provider metadata/constants and coercion helpers.
- `server/services/workflow/provider/ollama.py`: Ollama library service adapter plus cache/fetch mixin.
- `server/services/workflow/provider/huggingface_catalog.py`: Hugging Face catalog adapter plus catalog/cache/local metadata mixin.
- `server/services/workflow/provider/huggingface_downloads.py`: Hugging Face download lifecycle mixin for manifests, job status, progress, cleanup, and integrity validation.
- `server/services/workflow/node_handlers/core/prompts.py`: prompt, prompt-template, and image-input node executors used by the core handler registry.
- `server/services/workflow/node_handlers/processing/sources.py`: shared fragmentation source hydration and measurement helpers.
- `server/services/workflow/node_handlers/processing/merge.py`: merge-small-chunks executor used by the processing handler registry.
- `server/services/jobs.py`: thread-based background job manager.
- `server/services/runtime/events.py`: in-memory event bus + per-run history.
- `server/repositories/workflow/workflow.py`: filesystem workflow storage + index.
- `server/repositories/configuration.py`: session/profile/access-key persistence in SQL database.
- `client/src/pages/WorkflowPage.tsx`: visual workflow editor and execution control surface.
- `client/src/app/services/*.ts`: typed frontend API clients.

## Data Persistence

- File-based:
  - Workflows persisted under `app/resources/workflows`.
  - Workflow templates loaded from `app/resources/workflow_templates`.
  - Node manifests/plugins and artifacts stored under `app/resources/nodes` and `app/resources/artifacts`.
- Database:
  - Default embedded SQLite at `app/resources/database.db`.
  - Optional external PostgreSQL via `settings/configurations.json`.
  - SQLAlchemy tables include `user_sessions`, `access_keys`, `configuration_profiles`, `nodes`, and `chat_history_messages`.
- In-memory runtime stores:
  - Execution runs (`repositories/workflow/execution_run.py`).
  - Execution event history/subscribers (`services/runtime/events.py`).

## Async vs Sync Behavior

- Mostly synchronous REST handlers (`def`) for CRUD/listing/compile operations.
- Explicit async endpoints:
  - `POST /nodes/uploads/directory` (`async def`) for multipart file uploads.
  - `WS /executions/ws/runs/{run_id}` for streaming run events.
- Long-running execution is offloaded to background threads through `JobManager`.
- Async handlers avoid CPU-heavy loops directly; blocking node execution happens in job threads, not in request handlers.

