# ParaGraph Architecture

ParaGraph is a FastAPI + React application for authoring and running manifest-driven workflow graphs.
The current implementation uses a React Flow editor, JSON node manifests, and a typed execution compiler/runtime.

---

## 1. Repository Layout

- `ParaGraph/server`: FastAPI backend.
  - `app.py`: app creation and router registration.
  - `routes/`: API routers (`workflows`, `executions`, `nodes`, `providers`, `configurations`, `ws`).
  - `entities/`: Pydantic contracts for manifests, workflows, and execution state.
  - `services/workflow/`: manifest registry, compiler, provider abstraction, execution orchestration, workflow CRUD.
  - `services/runtime/events.py`: typed execution event pub/sub for polling and websocket replay.
  - `services/configuration.py`: session-level configuration orchestration for access keys and Ollama defaults.
  - `repositories/workflow/`: file-backed workflow documents and in-memory run-state repository.
  - `repositories/schemas/models.py`: relational tables (`user_sessions`, `nodes`, `access_keys`) used by SQLite/PostgreSQL backends.
  - `services/jobs.py`: in-process background job manager used by execution workers.
- `ParaGraph/client`: React + TypeScript frontend.
  - `src/pages/WorkflowPage.tsx`: React Flow workflow editor shell.
  - `src/pages/NodesPage.tsx`: compact node catalog and JSON import UI.
  - `src/pages/ConfigurationsPage.tsx`: provider/Ollama configuration console.
  - `src/app/services/api.ts`: shared request helper.
  - `src/app/services/workflowApi.ts`: node catalog, compile, execute, events, and configurations client surface.
  - `src/workflow/schema/types.ts`: shared frontend contracts for manifests, workflows, execution responses, and configuration payloads.
- `ParaGraph/resources/nodes`: JSON node manifests loaded dynamically at server startup and on import.
- `ParaGraph/resources/workflows`: persisted workflow documents and version history.
- `ParaGraph/resources/artifacts`: file-backed save/load targets for serialization nodes.

---

## 2. Backend Contracts

### 2.1 Node manifests
- `GET /nodes/catalog` returns live `NodeManifest[]`.
- `POST /nodes/import` validates and persists a single manifest JSON object.
- Each manifest declares:
  - metadata (`id`, `version`, `name`, `category`, `description`)
  - typed `inputs[]` and `outputs[]`
  - `parameters[]` with UI hints and defaults
  - `ui` display metadata
  - `runtime.executor_key` resolved to Python executor code

### 2.2 Workflow model
- Workflow documents use schema version `2`.
- `definition.nodes[]`: `{ node_id, node_type, node_version, parameters }`
- `definition.connections[]`: `{ from_node, from_output, to_node, to_input }`
- visual state stays separate in `visual_graph.nodes[]` with position, size, and collapse metadata.

### 2.3 Execution APIs
- `POST /executions/compile`: validates the graph and returns diagnostics plus a compiled plan when valid.
- `POST /executions`: starts a run from a compiled plan.
- `GET /executions/{run_id}`: current run state and terminal outputs.
- `GET /executions/{run_id}/events`: recorded lifecycle events.
- `WS /executions/ws/runs/{run_id}`: event replay + live event stream.

### 2.4 Configuration APIs
- `GET /configurations`: loads session-scoped access keys and Ollama defaults.
- `PUT /configurations`: saves session-scoped access keys and Ollama defaults.
- `POST /nodes/import` also persists imported JSON manifests to the relational `nodes` table for session tracking.

### 2.5 Relational persistence model
- `user_sessions`: session identity plus Ollama defaults (`base_url`, chat model, embedding model).
- `nodes`: imported node manifest snapshots keyed by session + node id/version.
- `access_keys`: provider-scoped key material (cloud + Hugging Face) linked to a session.

---

## 3. Runtime Architecture

### 3.1 Manifest registry
- Manifests are loaded from `ParaGraph/resources/nodes/*.json`.
- Duplicate `id + version` pairs are rejected.
- `executor_key` must map to a registered Python executor.

### 3.2 Compiler
- Validates:
  - known node type/version
  - known input/output names
  - required parameters and required inputs
  - strict type compatibility with `ANY` as the only wildcard
  - per-input multiplicity rules
  - acyclic graph structure
  - provider capability checks for model nodes
- Produces deterministic topological order and step bindings by named ports.

### 3.3 Executor
- Executes compiled steps in DAG order inside the job manager.
- Resolves bound inputs by port name.
- Applies per-run output caching for cacheable nodes.
- Publishes lifecycle events and stores terminal output payloads for output nodes.

---

## 4. Frontend Architecture

### 4.1 Nodes page
- Two-column layout.
- Left column: category checkbox toolbar plus a searchable node preview list with icon, description, and I/O summaries per row.
- Right column: supporting JSON import workspace backed by `POST /nodes/import`, including a manifest template helper.
- The page avoids heavy card nesting and keeps the catalog/filter interactions in a lighter rail + list structure.

### 4.2 Workflow page
- React Flow canvas with custom Comfy-style node cards.
- Node cards support compact inline widgets, italic subtitle text, collapse/expand controls, and drag-resize handles.
- Node parameters, collapse state, delete action, and runtime output preview live inside the node card.
- The node library is now a left tree viewer with expandable categories, in-tree search, a selected-node preview, and drag-only node insertion onto the canvas.
- Client-side connection checks mirror backend rules for type compatibility and multiplicity.

### 4.3 Configurations page
- Two-column layout with a left configuration rail and right reserved workspace.
- Left top panel manages cloud/Hugging Face keys with explicit Save/Load actions.
- Left bottom panel manages Ollama defaults (base URL, chat model, embedding model).
- Payloads are loaded/saved through `/configurations`.

---

## 5. Notes

- The legacy `/workflow/*` compatibility API is no longer part of the active application surface.
- Existing persisted workflow documents are migrated on read into schema `2` shapes.
- The initial executable manifest set is limited to the base nodes required by the current editor/runtime; retrieval/RAG expansion is a follow-up wave.

