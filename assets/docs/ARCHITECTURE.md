# ParaGraph Architecture

ParaGraph is a local-first workflow system with:
- FastAPI backend (`ParaGraph/server`)
- React + TypeScript frontend (`ParaGraph/client`)
- Manifest-driven workflow compilation and execution
- Polling + websocket execution observability

## 1. Repository Structure

- `ParaGraph/server`
  - `app.py`: FastAPI app bootstrap and router registration
  - `api/`: route modules (`workflows`, `executions`, `nodes`, `providers`, `configurations`, `ws`)
  - `domain/`: request/response and runtime contracts
  - `services/workflow/`: compile/execute/provider/node services
  - `services/runtime/events.py`: in-memory execution event history + pub/sub
  - `services/jobs.py`: thread-based background job manager
  - `repositories/workflow/`: workflow and run-state persistence
- `ParaGraph/client`
  - `src/App.tsx`: route wiring
  - `src/pages/WorkflowPage.tsx`: editor + compile/run UI
  - `src/pages/NodesPage.tsx`: node catalog/import
  - `src/pages/ModelsPage.tsx`: provider model browser/downloads
  - `src/pages/ConfigurationsPage.tsx`: runtime configuration/profile management
  - `src/app/services/api.ts`: shared fetch wrapper (`VITE_API_BASE_URL`)
  - `src/app/services/workflowApi.ts`: typed API client
  - `src/workflow/schema/types.ts`: shared client-side contracts
- `ParaGraph/resources`
  - `nodes/`, `workflows/`, `models/`, `artifacts/`, `logs/`

## 2. Active Backend API Surface

### Workflows
- `GET /workflows`
- `POST /workflows`
- `GET /workflows/{workflow_id}`
- `PUT /workflows/{workflow_id}`
- `GET /workflows/{workflow_id}/versions`

### Executions
- `POST /executions/compile`
- `POST /executions`
- `GET /executions/{run_id}`
- `GET /executions/{run_id}/events`
- `WS /executions/ws/runs/{run_id}`

### Nodes
- `GET /nodes/catalog`
- `POST /nodes/import`
- `POST /nodes/uploads/directory`
- `POST /nodes/check-database-connection`

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

## 3. Runtime Flow

1. UI builds workflow definition and calls `POST /executions/compile`.
2. Compiler validates topology, node contracts, data/controller bindings, and constraints.
3. UI starts execution via `POST /executions`.
4. Execution runs in background job threads and updates run state.
5. UI observes progress via:
   - `GET /executions/{run_id}`
   - `GET /executions/{run_id}/events`
   - `WS /executions/ws/runs/{run_id}` (replay + live stream)

## 4. Frontend Routes

- `/` workflow editor
- `/nodes` node library and manifest import
- `/models` model/provider operations
- `/config` configuration and profile management

## 5. Persistence and Runtime State

- Workflows and versions are stored under `ParaGraph/resources/workflows`.
- Node manifests are loaded from `ParaGraph/resources/nodes`.
- Uploaded browser files are staged under `ParaGraph/resources/artifacts`.
- Model artifacts are stored under `ParaGraph/resources/models`.
- Configuration defaults come from `ParaGraph/settings/configurations.json` plus `.env` overrides.

## 6. Deployment Modes

- `PARAGRAPH_DEPLOYMENT_MODE=local`: docs/openapi routes enabled.
- `PARAGRAPH_DEPLOYMENT_MODE=cloud`: docs/openapi routes disabled; API expected behind relative gateway path (typically `/api`).
