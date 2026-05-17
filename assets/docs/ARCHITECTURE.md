# ARCHITECTURE

Last updated: 2026-05-17

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
|- app/
|  |- client/
|  |  |- src/
|  |  |  |- App.tsx
|  |  |  |- main.tsx
|  |  |  |- index.css
|  |  |  |- app/services/ (API clients)
|  |  |  |- components/ (layout + reusable UI)
|  |  |  |- pages/ (Workflow, Nodes, Models, Configurations)
|  |  |  `- workflow/ (schema + hooks + workflow-local components)
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
|  |  |  |- database/ (shared tabular persistence + engine adapters)
|  |  |  |- schemas/ (SQLAlchemy ORM models)
|  |  |  `- workflow/ (workflow JSON and runtime repositories)
|  |  `- common/ (constants, security, logging)
|  `- resources/ (runtime data: db, logs, models, nodes, workflows, artifacts)
|- settings/ (.env variants + configurations.json)
|- release/
|  |- tauri/ (desktop build scripts)
|  `- windows/ (packaged artifacts)
|- runtimes/ (portable Python/uv/Node + .venv + uv.lock)
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
- `POST /nodes/database-schema`
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
- Database node operations:
  `services/workflow/node_handlers/database/operations.py` -> `repositories/workflow/database.py`

## Responsibilities of Key Modules

- `server/api/*`: HTTP/WebSocket boundary, request validation, HTTP status mapping.
- `server/domain/*`: request/response models, workflow schema, execution/event models.
- `server/services/workflow/compiler/service.py`: graph validation, diagnostics, topological planning.
- `server/services/workflow/execution.py`: step orchestration, cache, output shaping, event publishing.
- `server/services/workflow/structured_models.py`: safe structured JSON model inference, schema generation, Pydantic-source parsing, and validation payload formatting for structured nodes.
- `server/services/workflow/provider/service.py`: provider facade, model metadata, and download orchestration.
- `server/services/workflow/provider/helpers.py`: shared provider metadata/constants and coercion helpers.
- `server/services/workflow/provider/ollama.py`: Ollama library service adapter plus cache/fetch mixin.
- `server/services/workflow/provider/huggingface_catalog.py`: Hugging Face catalog adapter plus catalog/cache/local metadata mixin.
- `server/services/workflow/provider/huggingface_downloads.py`: Hugging Face download lifecycle mixin for manifests, job status, progress, cleanup, and integrity validation.
- `server/services/workflow/node_handlers/core/prompts.py`: prompt, prompt-template, and image-input node executors used by the core handler registry.
- `server/services/workflow/node_handlers/processing/sources.py`: shared fragmentation source hydration and measurement helpers.
- `server/services/workflow/node_handlers/processing/merge.py`: merge-small-chunks executor used by the processing handler registry.
- `server/services/workflow/node_handlers/structured.py`: structured input/output, JSON validation, and output parsing node executors.
- `server/services/workflow/node_handlers/http.py`: SSRF-guarded HTTP method node executors.
- `server/services/workflow/node_handlers/rag.py`: RAG helper executors for HTML cleanup, OCR availability reporting, context building, citations, and grounding checks.
- `server/services/workflow/node_handlers/advanced_text.py`: deterministic advanced text extraction, classification, redaction, parsing, and normalization executors.
- `server/services/workflow/node_handlers/control.py`: deterministic workflow control helpers including branching, batching, caching, human review gates, and trace/debug output.
- `server/services/jobs.py`: thread-based background job manager.
- `server/services/runtime/events.py`: in-memory event bus + per-run history.
- `server/repositories/workflow/workflow.py`: filesystem workflow storage + index.
- `server/repositories/workflow/database.py`: SQLAlchemy connection URL construction, schema inspection, and database-node CRUD/custom SQL persistence.
- `server/repositories/configuration.py`: session/profile/access-key persistence in SQL database.
- `server/repositories/database/base.py`: shared dataframe and SQLAlchemy tabular persistence behavior.
- `server/repositories/database/sqlite.py`: embedded SQLite engine adapter.
- `server/repositories/database/postgres.py`: external PostgreSQL engine adapter.
- `client/src/pages/WorkflowPage.tsx`: visual workflow editor and execution control surface.
- `client/src/workflow/components/*`: workflow-local presentation components reused by the editor surface.
- `client/src/workflow/schema/*`: workflow API/domain types plus editor-facing workflow contracts.
- `client/src/app/services/*.ts`: typed frontend API clients.

## Data Persistence

- File-based:
  - Workflow graph definitions are intentionally JSON persisted under `app/resources/workflows`.
  - Workflow templates loaded from `app/resources/workflow_templates`.
  - Node definitions remain JSON assets under `app/resources/nodes`.
  - Node plugins and artifacts are stored under `app/resources/nodes` and `app/resources/artifacts`.
- Database:
  - Default embedded SQLite at `app/resources/database.db`.
  - Optional external PostgreSQL via `settings/configurations.json`.
  - The application database stores internal application records, not workflow graph definitions.
  - SQLAlchemy tables include `user_sessions`, `access_keys`, `configuration_profiles`, `nodes`, and `chat_history_messages`.
  - SQLite and PostgreSQL repositories share tabular persistence through `repositories/database/base.py`; engine-specific classes only construct and validate their backends.
  - Database workflow nodes use `repositories/workflow/database.py` for inspected external/SQLite connection operations.
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

