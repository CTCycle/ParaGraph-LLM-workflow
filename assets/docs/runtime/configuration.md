# Configuration
Last updated: 2026-06-18

## Shared Configuration Sources
- Shared environment keys are loaded from `settings/.env`.
- Non-database runtime settings are stored in `settings/configurations.json`.

## Default Local Values
- `.env.example` provides defaults such as:
  - `FASTAPI_PORT=5002`
  - `UI_PORT=8002`
  - `VITE_API_BASE_URL=/api`
  - `RELOAD=false`

## Runtime-Specific Differences
- In packaged desktop mode, the backend sets `PARAGRAPH_TAURI_MODE=true`.
- In Tauri mode, FastAPI serves the built `client/dist` frontend from the application root.
- Database and runtime behavior split across:
  - `settings/.env` for all internal application database mode and connection values.
  - `settings/configurations.json` for non-database runtime settings such as `global.seed` and `jobs.polling_interval`.
- The default database mode is embedded SQLite through `DATABASE_EMBEDDED=true`.
- PostgreSQL is optional when embedded mode is disabled.
- Provider credentials and endpoint overrides are persisted as configuration access key records.
- Ollama settings remain first-class session fields; DeepSeek, LM Studio, and llama.cpp use access key records with `provider`, optional `api_key`, optional `base_url`, and local default model metadata.
- Default provider endpoints:
  - DeepSeek: `https://api.deepseek.com`
  - LM Studio: `http://localhost:1234/v1`
  - llama.cpp: `http://localhost:8080/v1`

## Cross-Runtime Communication
- Frontend to backend communication targets the relative API base path `/api`.
- In web mode, Vite handles proxying or rewriting to the backend.
- WebSocket execution streaming uses `/api/executions/ws/runs/{run_id}` derived from the current origin.
- In desktop mode, the Rust launcher starts uvicorn and redirects the UI to the backend URL after a readiness check.

## Shared Runtime Data
- Shared persistence lives under `app/resources`, including workflows, database files, logs, artifacts, and model assets.
