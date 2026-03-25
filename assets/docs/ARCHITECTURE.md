# ParaGraph Architecture

ParaGraph is a FastAPI + React application for authoring and executing manifest-driven workflow graphs.

## 1. Repository Structure

- `ParaGraph/server`
  - `app.py`: FastAPI app wiring and router registration.
  - `api/`: HTTP and websocket route modules (`workflows`, `executions`, `nodes`, `providers`, `configurations`, `ws`).
  - `domain/`: Pydantic/dataclass contracts (workflow, execution, provider, configuration, node API payloads, node handler parameter schemas, runtime payload contracts).
  - `services/workflow/`: compiler, execution orchestration, provider integration, node runtime logic, workflow CRUD.
  - `services/runtime/events.py`: in-memory execution event history + pub/sub used by REST and websocket replay.
  - `repositories/workflow/`: file-backed workflow persistence and run-state repository.
  - `services/jobs.py`: in-process background job manager.

- `ParaGraph/client`
  - `src/pages/WorkflowPage.tsx`: workflow canvas, import/export, compile/run interactions.
  - `src/pages/NodesPage.tsx`: node catalog and JSON manifest import modal.
  - `src/pages/ModelsPage.tsx`: Ollama/Hugging Face catalog and download flows.
  - `src/pages/ConfigurationsPage.tsx`: active configuration and profile load/save flows.
  - `src/app/services/api.ts`: shared fetch wrapper.
  - `src/app/services/workflowApi.ts`: typed frontend API surface.
  - `src/workflow/schema/types.ts`: shared frontend contract types.

- `ParaGraph/resources`
  - `nodes/`: node manifests.
  - `workflows/`: persisted workflows/version history.
  - `models/`: local model artifacts.
  - `artifacts/`: staged browser uploads and local runtime outputs.

## 2. Active API Surface

### Workflows
- `/workflows`
- `/workflows/{workflow_id}`
- `/workflows/{workflow_id}/versions`

### Executions
- `/executions/compile`
- `/executions`
- `/executions/{run_id}`
- `/executions/{run_id}/events`
- websocket `/executions/ws/runs/{run_id}`

### Nodes
- `/nodes/catalog`
- `/nodes/import`
- `/nodes/uploads/directory`
- `/nodes/check-database-connection`

### Providers
- `/providers/models`
- `/providers/ollama/library`
- `/providers/ollama/pull`
- `/providers/huggingface/models`
- `/providers/huggingface/download`
- `/providers/huggingface/download/{job_id}`
- Hugging Face model catalog queries request expanded metadata (for example safetensors and siblings) so backend size estimation can be populated when available.

### Configurations
- `/configurations`
- `/configurations/profiles`
- `/configurations/profiles/{profile_name}`
- `/configurations/ollama/ping`

## 3. Runtime Flow

1. Frontend builds a workflow definition and submits `/executions/compile`.
2. Compiler validates graph topology, port/controller compatibility, multiplicity, and manifest/runtime constraints.
3. Frontend starts execution via `/executions` using a compiled plan.
4. Runtime emits step/run events to `execution_event_service`.
5. Frontend consumes:
   - polling (`/executions/{run_id}`)
   - event history (`/executions/{run_id}/events`)
   - websocket replay/live stream (`/executions/ws/runs/{run_id}`)

## 4. Frontend Behavior Surfaces

- Workflow page:
  - import/export workflow JSON bundles
  - compile + run actions
  - status updates from polling + websocket events
  - node runtime output rendering

- Nodes page:
  - category-filtered node catalog
  - modal-driven JSON validate/import flow

- Configurations page:
  - active session configuration load
  - named profile list/load/save modals
  - Ollama ping action

- Models page:
  - Ollama pull status and refresh
  - Hugging Face query/filter/download/cancel/status polling

## 5. Test Architecture

### Backend tests (`pytest`)
- `tests/unit/server/...` for route/service/repository behavior.
- `tests/e2e/server/...` for compile->start->poll->outputs->events->websocket lifecycle.
- `tests/conftest.py` isolates job manager, workflow persistence roots, execution/event state, and provider caches.

### Frontend unit tests (`Vitest + RTL`)
- service-layer tests for `api.ts` and `workflowApi.ts`
- hook tests for node catalog loading/reload behavior
- page interaction tests for nodes/configurations/models deterministic flows

### Frontend browser E2E (`Playwright`)
- `ParaGraph/client/tests/e2e`
- local mock-backend route stubs for API endpoints
- deterministic websocket stub for execution event stream
- no external service dependency

## 6. Compatibility Notes

- Current architecture and tests target `/workflows` + `/executions` + `/nodes` + `/providers` + `/configurations` route families.
- Websocket execution streaming uses `/executions/ws/runs/{run_id}`.
- Legacy `/workflow/*` compatibility endpoints are not the primary active surface for this repository.

## 7. Database Initialization

- On backend startup, ORM metadata is synchronized with the active database engine using `Base.metadata.create_all(...)`.
- This is idempotent and ensures newly introduced tables (for example `configuration_profiles`) are created even when an older database file already exists.
