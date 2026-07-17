# Persistence
Last updated: 2026-07-17

## File-Based Persistence
- Workflow graph definitions are stored as JSON under `app/resources/workflows`.
- Workflow templates are loaded from `app/resources/workflow_templates`.
- Node definitions live as JSON assets under `app/resources/nodes`.
- Node plugins and runtime-generated artifacts are stored under `app/resources/nodes` and `app/resources/artifacts`.

## Application Database
- The default embedded database is SQLite at `app/resources/database.db`.
- PostgreSQL can be enabled through values in `settings/.env`.
- The application database stores internal application records, not workflow graph definitions.
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
- SQLite and PostgreSQL repositories share tabular persistence through `repositories/database/base.py`.
- Engine-specific adapters only construct, validate, and connect to their backends.
- Database workflow nodes use `repositories/workflow/database.py` for inspected external and SQLite connection operations.

## Execution Durability
- Runs, serialized plans, step state and outputs, pause tokens, final outputs, and ordered event history are stored in the application database.
- Event sequences are monotonic per run and survive backend restart.
- Only active WebSocket subscriber queues and thread-job control flags remain process-local.
- `ExecutionRunRepository.cleanup_retention(days)` is the explicit bounded cleanup boundary. No background deletion service runs automatically.

## Storage Boundary Rules
- Workflow definitions remain file-based by design.
- Runtime event history is durable; live subscriptions are process-local.
- Database configuration affects internal app records and database-node integrations, but not the source-of-truth workflow graph JSON files.
- Local FAISS vector indexes use temporary sibling builds, per-index bounded file locks, and atomic directory replacement so failed writes retain the last committed index.
- LanceDB relies on its versioned table commits and a per-table writer lock; Chroma uses its persistent client and backend-native collection metric metadata.
