# Persistence
Last updated: 2026-08-18

## File-Based Persistence
- Workflow graph definitions are stored as JSON under the configured resource root (`app/resources/workflows` by default).
- Workflow templates are loaded from the configured resource root (`app/resources/workflow_templates` by default).
- Node definitions live as JSON assets under the configured resource root (`app/resources/nodes` by default).
- Node plugins and runtime-generated artifacts are stored under the configured resource root (`app/resources/nodes` and `app/resources/artifacts` by default).

## Application Database
- The default embedded database is SQLite at `app/resources/database.db`.
- Set `PARAGRAPH_RESOURCES_DIR` in `settings/.env` to relocate the shared resource root; the embedded database then uses `<PARAGRAPH_RESOURCES_DIR>/database.db`.
- Internal application persistence always uses the embedded SQLite database; `DATABASE_INSERT_BATCH_SIZE` controls its dataframe batch size.
- The application database stores internal application records, not workflow graph definitions.
- `repositories/database/initializer.py` is the only application-schema creation boundary. Startup or explicit initialization must run before repository use; application repositories do not lazily create application tables or migrate legacy structures. Dynamic tables created by database nodes remain explicit user-data operations.
- SQLAlchemy tables include:
  - `user_sessions`
  - `access_keys`
  - `configuration_profiles`
  - `nodes`
  - `chat_history_messages`
  - `execution_runs`
  - `execution_steps`
  - `execution_events`

## Persistence Layer Responsibilities
- `repositories/database/sqlite.py` owns the internal SQLite engine and tabular persistence behavior.
- Database workflow nodes independently use `repositories/workflow/database.py` for inspected external and SQLite connection operations, including intentional PostgreSQL connections.

## Execution Durability
- Runs, serialized plans, step state and outputs, pause tokens, final outputs, and ordered event history are stored in the application database.
- Event sequences are monotonic per run and survive backend restart.
- Only active WebSocket subscriber queues and thread-job control flags remain process-local.
- `ExecutionRunRepository.cleanup_retention(days)` is the explicit bounded cleanup boundary. No background deletion service runs automatically.

## Storage Boundary Rules
- Workflow definitions remain file-based by design.
- Runtime event history is durable; live subscriptions are process-local.
- SQLite persistence affects internal app records; database-node integrations remain independent and do not change the source-of-truth workflow graph JSON files.
- Local FAISS vector indexes use temporary sibling builds, per-index bounded file locks, and atomic directory replacement so failed writes retain the last committed index.
- LanceDB relies on its versioned table commits and a per-table writer lock; Chroma uses its persistent client and backend-native collection metric metadata.
