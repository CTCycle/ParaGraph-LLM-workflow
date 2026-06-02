# Persistence
Last updated: 2026-06-02

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

## Persistence Layer Responsibilities
- SQLite and PostgreSQL repositories share tabular persistence through `repositories/database/base.py`.
- Engine-specific adapters only construct, validate, and connect to their backends.
- Database workflow nodes use `repositories/workflow/database.py` for inspected external and SQLite connection operations.

## In-Memory Runtime Stores
- Execution runs are tracked in `repositories/workflow/execution_run.py`.
- Execution event history and subscribers are tracked in `services/runtime/events.py`.

## Storage Boundary Rules
- Workflow definitions remain file-based by design.
- Runtime event history is ephemeral and process-local.
- Database configuration affects internal app records and database-node integrations, but not the source-of-truth workflow graph JSON files.
