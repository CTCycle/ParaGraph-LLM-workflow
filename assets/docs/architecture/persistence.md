# Persistence
Last updated: 2026-10-21

## File-Based Persistence
- The active workflow graph is browser-owned. The editor persists its state in
  browser `localStorage` and supports explicit JSON import/export; it is not
  written to the backend resource root. Normal edits use a short debounce, and
  pending graph state is flushed on browser page exit so an immediate reload
  does not lose a newly loaded or edited graph.
- Workflow templates are read-only JSON manifests loaded from the configured
  resource root (`data/workflow_templates` by default).
- Node definitions live as JSON assets under the configured resource root (`data/nodes` by default).
- Node plugins and runtime-generated artifacts are stored under the configured resource root (`data/nodes` and `data/artifacts` by default).

## Application Database
- The default embedded database is SQLite at `data/database.db`.
- Set `PARAGRAPH_RESOURCES_DIR` in `settings/.env` to relocate the shared resource root. `<RESOURCES_ROOT>/database_config.json` independently stores the internal SQLite path and dataframe batch size; relative database paths are resolved from the resource root. Its write is validated and atomically replaced. SQLite requires no credentials.
- The active database is the only source of truth for backend application settings. The `application_settings` singleton stores seed and job polling/retention values; provider configurations, profiles, chat history, and execution records remain in their existing tables.
- Provider values edited on the Settings page are debounced, serialized, and persisted to the active database automatically. The UI flushes pending edits on blur, route changes, and page exit, and reports persistence failures without discarding the draft. Loading a named profile activates it in the current database; profiles and active credentials remain database-owned.
- A one-time startup import reads legacy `settings/configurations.json` values into the first database transaction and removes the file only after commit. `DATABASE_INSERT_BATCH_SIZE` is imported once from an old `.env` into `database_config.json`; it is removed from `.env` and is not loaded as a runtime setting. `PARAGRAPH_RESOURCES_DIR` remains an environment setting.
- The application database stores internal application records, not workflow graph definitions.
- `DatabaseRuntime` owns the active internal engine and leases repository sessions. Startup reaches it through `repositories/database/initializer.py`; it prepares and validates each target schema before switching. Direct Alembic commands also use the selected path from `database_config.json`. Application repositories do not lazily create application tables or migrate legacy structures. Dynamic tables created by database nodes remain explicit user-data operations.
- Alembic revisions live under `app/server/migrations`, and `alembic_version` records the synchronized revision. Empty databases are created by `upgrade head`; databases without a revision, or with an incompatible or partial schema, fail closed without destructive repair.
- The migration runner serializes startup and explicit initialization with a database-adjacent file lock and uses a transaction-scoped SQLite migration connection. A failed migration aborts startup and is retried safely after the underlying issue is corrected.
- SQLAlchemy tables include:
  - `user_sessions`
  - `application_settings`
  - `provider_configurations`
  - `configuration_profiles`
  - `chat_history_messages`
  - `execution_runs`
  - `execution_steps`
  - `execution_events`
- SQLite foreign-key enforcement is enabled on every checked-out application
  connection by `repositories/database/sqlite_policy.py`; repository tests
  cover the pragma and cascades.
- Revision `0002_remove_node_configuration_mirror` removes the obsolete
  `nodes` application table. Node manifests are filesystem-owned under the
  configured resource root and are not mirrored into the application database.

## Runtime Database Switching
- The Settings page can test and activate another SQLite file without restarting a single-worker backend. Every internal repository session leases the active engine; switching pauses new sessions and drains existing ones before retiring the old pool.
- A switch returns HTTP 409 while a workflow job is active. The target schema and its own application settings are prepared before the connection configuration is atomically persisted and made active. Failed preparation leaves the prior database active. Data and settings are not copied between files.
- Changing `PARAGRAPH_RESOURCES_DIR` changes the location of database configuration and other resources, so it requires a restart. Running multiple backend worker processes also requires a restart after a database change because each worker owns its own active engine. Workflow database-node connections are separate and are not switched.

## Migration Workflow

From `app` with the backend environment installed:

```powershell
.\server\.venv\Scripts\python.exe -m alembic -c server\pyproject.toml revision --autogenerate -m "describe the schema change"
.\server\.venv\Scripts\python.exe -m alembic -c server\pyproject.toml check
.\server\.venv\Scripts\python.exe -m alembic -c server\pyproject.toml upgrade head
.\server\.venv\Scripts\python.exe -m alembic -c server\pyproject.toml current
.\server\.venv\Scripts\python.exe -m alembic -c server\pyproject.toml history
```

Review and edit every autogenerated revision before applying it; name new constraints and indexes explicitly. Do not rebuild populated baseline tables solely to retrofit names. Use launcher option 5 for the supported application initialization path and startup locking.

## Persistence Layer Responsibilities
- `repositories/database/runtime.py` owns the active internal SQLite engine and session lifecycle. `repositories/database/sqlite.py` retains tabular persistence behavior for explicit repository use.
- Database workflow nodes independently use `repositories/workflow/database.py` for inspected external and SQLite connection operations, including intentional PostgreSQL connections.

## Execution Durability
- Runs, serialized plans, step state and outputs, pause tokens, final outputs, and ordered event history are stored in the application database.
- The workflow editor persists its `execution_session_id` alongside the local
  graph state. Chat history is then scoped by workflow ID, execution session ID,
  and Chat node ID. `CHAT_HISTORY_MEMORY` is process-local;
  `CHAT_HISTORY_PERSISTED` uses the application SQLite database. There is no
  filesystem chat-history repository.
- Persisted pause checkpoints reject unknown fields and malformed or status-inconsistent payloads.
- Paused runs store a durable checkpoint containing the gate node, step, reviewed-payload schema, pause payload, and one-time resume token. Resume consumes the checkpoint atomically with the reviewed `result` output.
- Cancelling a paused run clears its run and step checkpoints in the same transaction; the paused step becomes `skipped` with `execution_cancelled` as its blocked reason. Its resume token can no longer be used.
- Event sequences are monotonic per run and survive backend restart.
- Only active WebSocket subscriber queues and thread-job control flags remain process-local.
- `ExecutionRunRepository.cleanup_retention(days)` is the explicit bounded cleanup boundary. No background deletion service runs automatically.

## Storage Boundary Rules
- The active workflow graph remains browser-local by design; the backend receives
  a validated graph only for compilation and execution.
- Node manifests remain file-based by design; the node manifest repository is
  the single persistence boundary for imported and built-in manifests.
- Runtime event history is durable; live subscriptions are process-local.
- SQLite persistence affects internal app records; database-node integrations remain independent and do not change the browser-owned graph or its explicit JSON exports.
- Local FAISS vector indexes use temporary sibling builds, per-index bounded file locks, and atomic directory replacement so failed writes retain the last committed index.
- LanceDB relies on its versioned table commits and a per-table writer lock; Chroma uses its persistent client and backend-native collection metric metadata.
