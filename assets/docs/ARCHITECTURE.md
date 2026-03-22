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
  - `services/configuration.py`: session-level configuration orchestration for active settings, named profiles, and Ollama health checks.
  - `repositories/workflow/`: file-backed workflow documents and in-memory run-state repository.
  - `repositories/schemas/models.py`: relational tables (`user_sessions`, `nodes`, `access_keys`, `configuration_profiles`) used by SQLite/PostgreSQL backends.
  - `services/jobs.py`: in-process background job manager used by execution workers.
- `ParaGraph/client`: React + TypeScript frontend.
  - `src/pages/WorkflowPage.tsx`: React Flow workflow editor shell.
  - `src/pages/NodesPage.tsx`: compact node catalog and JSON import UI.
  - `src/pages/ModelsPage.tsx`: two-column model explorer (Ollama + Hugging Face) with refresh, search, filters, and incremental loading.
  - `src/pages/ConfigurationsPage.tsx`: provider/Ollama configuration console with named save/load modals.
  - `src/app/services/api.ts`: shared request helper.
  - `src/app/services/workflowApi.ts`: node catalog, compile, execute, events, configurations, and profile/Ollama status client surface.
  - `src/workflow/schema/types.ts`: shared frontend contracts for manifests, workflows, execution responses, and configuration/profile payloads.
- `ParaGraph/resources/nodes`: JSON node manifests loaded dynamically at server startup and on import. The `custom_nodes/` subfolder is used for custom node pack assets (scripts/examples/manifests).
- `ParaGraph/resources/workflows`: persisted workflow documents and version history.
- `ParaGraph/resources/models`: local model storage, including downloaded Hugging Face repositories under `huggingface/<namespace--model>/`.
- `ParaGraph/resources/database.db`: default embedded SQLite database file (legacy `ParaGraph/resources/database/database.db` is auto-migrated on startup).
- `ParaGraph/resources/artifacts`: file-backed save/load targets for serialization nodes, browser uploads, and vector store artifacts.

---

## 2. Backend Contracts

### 2.1 Node manifests
- `GET /nodes/catalog` returns live `NodeManifest[]`.
- `POST /nodes/import` validates and persists a single manifest JSON object (including optional plugin runtime descriptors).
- `GET /nodes/dialog/files` opens a native file picker on the local machine and returns selected paths for path-backed node widgets.
- `GET /nodes/dialog/directory` opens a native folder picker on the local machine and returns the selected directory path (used by legacy path fields).
- `POST /nodes/uploads/directory` accepts browser-selected folder uploads (multipart) and stages them under `ParaGraph/resources/artifacts/browser_uploads`, returning the staged server path for runtime execution.
- `POST /nodes/check-database-connection` validates SQL node connection parameters (`SQL_DATABASE` / `SQL_FILE_DATABASE`) and returns a success/failure payload for node-level health checks.
- The active model authoring flow uses a `MODEL_PROVIDER` node that emits a typed `MODEL_HANDLE`, consumed by unified `LLM_CHAT` and `LLM_STRUCTURED` nodes.
- Each manifest declares:
  - metadata (`id`, `version`, `name`, `category`, `description`)
  - typed `inputs[]` and `outputs[]`
  - `parameters[]` with UI hints and defaults
  - `ui` display metadata
  - `runtime.executor_key` resolved to built-in Python executor code, or `runtime.plugin` for script-backed custom node execution

### 2.2 Workflow model
- Workflow documents use schema version `2`.
- `definition.nodes[]`: `{ node_id, node_type, node_version, parameters, skipped? }` (skipped nodes stay in canvas state but are excluded from compiled execution plans).
- `definition.connections[]`: `{ from_node, from_output, to_node, to_input }`
- visual state stays separate in `visual_graph.nodes[]` with position, size, collapse metadata, plus UI flags such as ping and skipped highlighting.
- `GET /workflows/dialog/import-json` opens a native JSON file picker (default folder: `ParaGraph/resources/workflows`) and returns the selected file content.
- `POST /workflows/dialog/export-json` opens a native save dialog (default folder: `ParaGraph/resources/workflows`) and writes the workflow JSON payload to the chosen path.

### 2.3 Execution APIs
- `POST /executions/compile`: validates the graph and returns diagnostics plus a compiled plan when valid.
- `POST /executions`: starts a run from a compiled plan.
- `GET /executions/{run_id}`: current run state and terminal outputs.
- `GET /executions/{run_id}/events`: recorded lifecycle events.
- `WS /executions/ws/runs/{run_id}`: event replay + live event stream.

### 2.4 Configuration APIs
- `GET /configurations`: loads the currently active session-scoped access keys and Ollama defaults.
- `PUT /configurations`: saves the currently active session-scoped access keys and Ollama defaults.
- `GET /configurations/profiles`: lists named saved configuration profiles for a session.
- `GET /configurations/profiles/{profile_name}`: loads a named profile and applies it as active session configuration.
- `PUT /configurations/profiles/{profile_name}`: saves the current payload to a named profile and updates active session configuration.
- `POST /configurations/ollama/ping`: checks whether the configured Ollama base URL is reachable and returns model count/status.
- `POST /nodes/import` also persists imported JSON manifests to the relational `nodes` table for session tracking.

### 2.5 Provider Discovery APIs
- GET /providers/ollama/library: returns model rows discovered from https://ollama.com/library, enriched with local pulled status from the configured Ollama runtime.
- POST /providers/ollama/pull: pulls a selected Ollama model and returns typed pull status.
- GET /providers/huggingface/models: returns paginated Hub model rows (repo id, author, task, library, likes, downloads, visibility, url, downloaded) with API-backed filtering and sorting.
- POST /providers/huggingface/download: downloads a selected Hugging Face repository into `ParaGraph/resources/models/huggingface/<namespace--model>/` and makes it available in model-provider dropdowns.
### 2.6 Relational persistence model
- `user_sessions`: session identity plus Ollama defaults (`base_url`, chat model, embedding model).
- `nodes`: imported node manifest snapshots keyed by session + node id/version.
- `access_keys`: provider-scoped key material (LLM providers + Hugging Face) linked to a session.
- `configuration_profiles`: named full configuration snapshots (access keys + Ollama defaults) linked to a session.
- Database backend adapters (`repositories/database/sqlite.py`, `repositories/database/postgres.py`) now run through SQLAlchemy Session/query constructs (mapped models when available, reflected tables otherwise) instead of raw SQL strings.

---

## 3. Runtime Architecture

### 3.1 Manifest registry
- Manifests are loaded from `ParaGraph/resources/nodes/*.json`.
- Duplicate `id + version` pairs are rejected.
- Script-backed plugin nodes load their `runtime.plugin.script_path` relative to the manifest file for cross-machine portability.
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
- Single catalog surface with category filter rail and searchable node preview list (icon, description, and I/O summaries per row).
- Node preview header now includes a `+` action that opens a modal JSON import workspace backed by `POST /nodes/import`.
- The import modal includes template autofill, validation, and import actions without leaving the preview context.
- The page avoids heavy card nesting and keeps catalog/filter interactions in a lighter rail + list structure.

### 4.2 Workflow page
- React Flow canvas with custom Comfy-style node cards.
- Node cards support compact inline widgets, italic subtitle text, ping + collapse controls, and drag-resize handles.
- Path-backed parameters can open native file/folder pickers and persist selected source or destination paths directly in node parameters (including serialization file paths).
- `LOAD_DOCUMENTS` uses a frontend browser folder picker and uploads selected files to a staged server folder path; the picker cancel-detection guard prevents focus/change race conditions from clearing the selected folder path.
- Parameter rows use a denser Comfy-inspired control treatment for higher information density without changing the overall card shell.
- Node parameters, collapse state, and delete action live inside the node card; execution outputs are consumed through dedicated output nodes.
- The node library is now a left tree viewer with expandable categories, in-tree search, a selected-node preview, and drag-only node insertion onto the canvas.
- All node categories are collapsed on first visit, then category expansion state is persisted.
- Workflow canvas state (nodes, edges, layout metadata) persists in browser storage across page navigation.
- Workflow JSON bundles are exported/imported through native file dialogs (default folder: `ParaGraph/resources/workflows`), including required node manifests for shareable execution across ParaGraph installations.
- Runtime execution highlights the currently running node in-canvas for step-by-step guidance; pinged nodes keep a persistent visual accent independent of runtime activity and are frozen in place until unpinged.
- Client-side connection checks mirror backend rules for type compatibility and multiplicity.
- Workflow canvas keyboard commands include copy/paste for selected nodes (`Ctrl+C`, `Ctrl+V`), node/link deletion (`Delete`/`Backspace`), and `Ctrl+Click` multi-selection.
- Right-clicking a node opens a compact context menu for ping/unping, add same node (defaults), clone, reset config, skip/unskip, and remove actions.

### 4.3 Configurations page
- Two-column layout with dedicated panels: Ollama settings on the left and Access Keys on the right.
- Left panel manages Ollama base URL and exposes a runtime status check action.
- Right panel manages provider/Hugging Face keys and opens modal dialogs for named Load/Save profile flows.
- Active payloads are still loaded/saved through `/configurations`, while named profiles are persisted via `/configurations/profiles/*`.

---

### 4.4 Models page
- Two-column explorer layout: Ollama catalog on the left, Hugging Face Hub on the right.
- Each column includes a compact toolbar with search and filters, plus an explicit Update action.
- Ollama rows expose pulled/unpulled state and in-row pull actions for unpulled models.
- Hugging Face rows support API-backed search/filter/sort, incremental loading, refresh preserving active query controls, compact warning/error states, and direct in-row download to local model storage.
## 5. Phase 1 RAG Runtime
- New ingestion nodes emit normalized DOCUMENT_LIST payloads from local files, folder references (`LOAD_DOCUMENTS` deferred file-path collection), HTTP sources, and read-only database queries.
- `SQL_DATABASE` and `SQL_FILE_DATABASE` emit typed read-only connection controller payloads consumed by query-style SQL nodes (for example `DATABASE_QUERY`).
- `DATABASE_QUERY` intentionally retains a narrow raw-SQL execution path for user-authored ad-hoc read-only queries after strict statement-prefix and multi-statement guards.
- `TEXT_CLEANER` and `CHUNKER` convert documents into `CHUNK_LIST` payloads suitable for retrieval.
- `BATCH_EMBEDDER` turns chunks into `VECTOR_POINT_LIST` payloads using provider-backed embeddings.
- `VECTOR_DB_WRITER` persists local FAISS indexes under `<storage_directory>/<index_name>/` (defaulting to `ParaGraph/resources/artifacts/vectorstores`) with metadata sidecars.
- `SIMILARITY_SEARCH` embeds the query using the store handle metadata and returns typed `RETRIEVAL_RESULTS`.
- `CONTEXT_INJECTOR` converts retrieval hits into prompt-ready `TEXT` for the existing `LLM_CHAT` / `LLM_STRUCTURED` nodes.

---

## 6. Notes
- The legacy `/workflow/*` compatibility API is no longer part of the active application surface.
- Existing persisted workflow documents are migrated on read into schema `2` shapes.
- The executable manifest set now includes a Phase 1 typed RAG slice for ingestion, chunking, embedding, vector storage, retrieval, and context injection.
