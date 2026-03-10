# ParaGraph Architecture

ParaGraph is a FastAPI + React application for authoring and running typed LLM workflow graphs.
The current implementation now has explicit workflow/compiler/runtime contracts, a Canvas2D editor surface, and websocket runtime events.

---

## 1. Repository Layout

- `ParaGraph/server`: FastAPI backend.
  - `app.py`: app creation and router registration.
  - `routes/`: API routers (`workflow`, `workflows`, `executions`, `nodes`, `providers`, `ws`).
  - `entities/`: Pydantic API/domain contracts (workflow, execution, node catalog, jobs, settings).
  - `services/workflow/`: compiler, execution orchestration, provider abstraction, node registry, legacy adapters.
  - `services/runtime/events.py`: typed execution event pub/sub for websocket fanout.
  - `repositories/workflow/`: workflow version persistence and in-memory run state repository.
  - `services/jobs.py`: in-process background job manager used by execution workers.
- `ParaGraph/client`: React + TypeScript frontend.
  - `src/graph/canvas/GraphCanvas.tsx`: Canvas2D graph rendering + interaction layer.
  - `src/graph/core/`: graph model ops, edge validation, serialization adapter, command history.
  - `src/app/stores/`: separated workflow/runtime/ui/catalog stores.
  - `src/app/services/workflowApi.ts`: API and websocket client surface.
  - `src/pages/WorkflowPage.tsx`: editor shell + inspector + runtime event panel.

---

## 2. Runtime Topology

### Local launcher path (`ParaGraph/start_on_windows.bat`)
- Boots portable runtimes and runs FastAPI + built frontend preview.
- Frontend uses `VITE_API_BASE_URL` and websocket path `/workflow/ws/runs/{run_id}` via same host/proxy base.

### Docker path
- Backend container runs Uvicorn.
- Frontend container serves static assets through Nginx.
- `/api/*` is proxied to backend routes.

---

## 3. Backend Architecture

### 3.1 API surface
- Compatibility API:
  - `GET /workflow/catalog`
  - `POST /workflow/validate`
  - `POST /workflow/execute`
  - `GET/DELETE /workflow/jobs/{job_id}`
- New platform APIs:
  - `GET/POST /workflows`
  - `GET/PUT /workflows/{workflow_id}`
  - `GET /workflows/{workflow_id}/versions`
  - `POST /executions/compile`
  - `POST /executions`
  - `GET /executions/{run_id}`
  - `GET /executions/{run_id}/events`
  - `GET /nodes/catalog`
  - `GET /providers/catalog`
  - `WS /workflow/ws/runs/{run_id}`

### 3.2 Service boundaries
- `compiler.py`: graph diagnostics, typed-port checks, DAG checks, provider capability checks, execution plan construction.
- `execution.py`: step orchestration, per-step state, job progress/result updates, typed event publication.
- `provider.py`: provider capabilities and normalized chat call dispatch.
- `legacy.py`: adapters from legacy graph payloads to versioned workflow contracts.
- `workflow.py`: workflow CRUD and version orchestration.

### 3.3 Runtime events
Typed envelope (`ExecutionEventEnvelope`) fields:
- `event_type`
- `run_id`
- `step_id`
- `sequence`
- `timestamp`
- `payload`

Published lifecycle events:
- `execution.queued`
- `execution.started`
- `execution.step.started`
- `execution.step.completed`
- `execution.step.failed`
- `execution.completed`
- `execution.failed`

---

## 4. Frontend Architecture

### 4.1 Editor layer
- Canvas2D graph surface for nodes/edges and interactions.
- Inspector panel for node config editing.
- Runtime event panel and run controls.
- Nodes registry page with a primary catalog-first layout, compact filter/search toolbar, a scrollable row-based node preview list with optional schema expansion, compactable core artifacts, and a secondary accordion-based system reference rail.

### 4.2 Store separation
- `workflowStore`: in-memory workflow definition + visual graph (initialized empty on app launch).
- `runtimeStore`: run status, events, per-step state, outputs.
- `uiStore`: camera/grid/connection pointer interaction state.
- `nodeCatalogStore` + `providerCatalogStore`: catalog loading and state.

### 4.3 Persistence
- Workflow editor state is session-scoped and starts from an empty graph on each application launch.
- Runtime outputs are not persisted inside workflow configs.

---

## 5. Notes

- Legacy non-workflow route modules from the original template were removed from the server route layer.
- Existing backend pytest suite remains green and continues covering root workflow compatibility behavior.
- Additional coverage for websocket stream behavior and workflow CRUD/version APIs should be expanded in subsequent hardening phases.

