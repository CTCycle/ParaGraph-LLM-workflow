# ParaGraph Architecture
Last updated: 2026-04-21

ParaGraph is a local-first workflow system built from:
- FastAPI backend (`ParaGraph/server`)
- React + TypeScript frontend (`ParaGraph/client`)
- Manifest-driven node catalog (`ParaGraph/resources/nodes`)

## 1. High-Level Structure

- `ParaGraph/server`
  - `app.py`: FastAPI app composition and router registration
  - `api/`: route modules (`workflows`, `executions`, `nodes`, `providers`, `configurations`, `ws`)
  - `domain/`: typed request/response and runtime contracts
  - `services/`: orchestration for workflows, providers, runtime events, jobs, and persistence-facing logic
    - `services/workflow/nodes/connectivity.py`: node connection validation service used by `/nodes` connection-check endpoints
    - `services/workflow/node_handlers/core/`: core node executors split by concern (`storage.py`, `routing.py`, plus core registry/orchestration in `__init__.py`)
    - `services/workflow/vector_stores/`: adapter-per-backend modules (`lancedb.py`, `qdrant.py`, `pinecone.py`, `weaviate.py`, `milvus.py`, `chroma.py`) with shared infrastructure in `base.py`
- `ParaGraph/client`
  - `src/pages/WorkflowPage.tsx`: workflow authoring, compile/run, and execution monitoring
  - `src/pages/NodesPage.tsx`: node catalog browsing and manifest import
  - `src/pages/ModelsPage.tsx`: provider model browsing, Ollama pulls, Hugging Face downloads
  - `src/pages/ConfigurationsPage.tsx`: session/profile configuration management

## 2. Active API Surface

Routers are mounted in `ParaGraph/server/app.py`.

- Workflows (`/workflows`)
  - `GET /workflows`
  - `POST /workflows`
  - `GET /workflows/templates`
  - `GET /workflows/{workflow_id}`
  - `PUT /workflows/{workflow_id}`
- Executions (`/executions`)
  - `POST /executions/compile`
  - `POST /executions`
  - `GET /executions/{run_id}`
  - `GET /executions/{run_id}/events`
- Nodes (`/nodes`)
  - `GET /nodes/catalog`
  - `POST /nodes/import`
  - `POST /nodes/uploads/directory`
  - `POST /nodes/check-database-connection`
  - `POST /nodes/check-vector-store-connection`
- Providers (`/providers`)
  - `GET /providers/catalog`
  - `GET /providers/models`
  - `GET /providers/ollama/library`
  - `POST /providers/ollama/pull`
  - `GET /providers/huggingface/models`
  - `POST /providers/huggingface/download`
  - `GET /providers/huggingface/download/{job_id}`
  - `DELETE /providers/huggingface/download/{job_id}`
- Configurations (`/configurations`)
  - `GET /configurations`
  - `PUT /configurations`
  - `GET /configurations/profiles`
  - `GET /configurations/profiles/{profile_name}`
  - `PUT /configurations/profiles/{profile_name}`
  - `POST /configurations/ollama/ping`
- Websocket
  - `WS /executions/ws/runs/{run_id}` (supports replay by default)

## 3. Runtime Lifecycle

1. User builds graph in the workflow editor.
2. UI compiles with `POST /executions/compile`.
3. Backend validates node contracts, links, and execution plan.
4. UI starts run with `POST /executions`.
5. Runtime executes steps and publishes event updates.
6. UI monitors state through polling (`GET /executions/{run_id}`), event history, and websocket stream.

## 3.1 Bootstrap And Runtime Ownership

- App bootstrap is explicit through `create_app()` in `ParaGraph/server/app.py`.
- Package import (`ParaGraph/server/__init__.py`) is side-effect free.
- Root behavior is API-owned (`ParaGraph/server/api/root.py`):
  - cloud mode returns `{"status": "ok"}`
  - non-cloud mode redirects to `/docs`
- Configuration bootstrap is centralized in `ParaGraph/server/configurations/startup.py` through `get_configuration_runtime()` and `get_server_settings()`.
- `EnvironmentLoader` in `ParaGraph/server/configurations/environment.py` is instance-based and does not rely on mutable module-level globals.

## 3.2 Service And Repository Boundaries

- API modules delegate to services; endpoints do not access repositories directly.
- Services own orchestration and request/response composition.
- Repositories own persistence and storage primitives only.
- Workflow orchestration (create/update document assembly and merge semantics) belongs to `ParaGraph/server/services/workflow/workflow.py`.
- Workflow repository (`ParaGraph/server/repositories/workflow/workflow.py`) is persistence-only.
- Configuration repository resolves database backends through `ParaGraph/server/repositories/database/factory.py`.
- Repositories must not read runtime settings at import time.

## 4. Node and Contract Model

- Node schemas are loaded from manifests in `ParaGraph/resources/nodes`.
- Frontend forms are manifest-driven and keep parameter editing aligned with node contracts.
- Backend executes nodes via registered runtime handlers and typed domain models.
- Data links and controller links are distinct and validated at compile/runtime boundaries.

## 5. Providers and Model Capabilities

- Provider catalog is exposed through `/providers/catalog`.
- Model inventory is exposed through `/providers/models`.
- Capabilities are used by the UI/runtime for compatibility checks (for example embeddings support).
- Operational provider paths include:
  - Ollama library listing and pull operations
  - Hugging Face model listing with filters and async download jobs

Known capability constraints in current runtime:
- Claude embeddings are not supported.
- Hugging Face image-input generation is rejected in the local generation path.
- Hugging Face structured output remains best-effort generation with JSON validation.

## 6. Execution Events and Background Work

- Execution state/events are available via run polling, event history, and websocket stream.
- Long-running provider jobs (for example Hugging Face downloads) use job-style async status endpoints.
- Download cancellation is supported through `DELETE /providers/huggingface/download/{job_id}`.

## 7. Test Reset Boundaries

- Stateful runtime components expose explicit test reset APIs:
  - `workflow_repository.reset_for_tests()`
  - `execution_run_repository.reset_for_tests()`
  - `execution_event_service.reset_for_tests()`
  - `job_manager.reset_for_tests()`
  - `provider_service.reset_for_tests()`
- Tests use these public boundaries instead of mutating private internals.
