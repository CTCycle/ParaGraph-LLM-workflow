# Configuration
Last updated: 2026-08-18

## Shared Configuration Sources
- Shared environment keys are loaded from `settings/.env`.
- Non-database runtime settings are stored in `settings/configurations.json`.

## Default Local Values
- `.env.example` provides defaults such as:
  - `FASTAPI_HOST=127.0.0.1`
  - `FASTAPI_PORT=5002`
  - `UI_HOST=127.0.0.1`
  - `UI_PORT=8002`
  - `VITE_API_BASE_URL=/api`
  - `RELOAD=false`
  - `BACKEND_LOGS_VISIBLE=true`
- `PARAGRAPH_RESOURCES_DIR` is blank by default, which keeps shared resource data under `app/resources`.
- Set `PARAGRAPH_RESOURCES_DIR` to an absolute path or a path relative to the repository root to relocate resource data, including the embedded SQLite database.

## Runtime Settings
- Launcher option `2` creates or refreshes the frontend build. Application launch serves the existing build output and rebuilds it only when the build or required environment is missing or unusable.
- Database and runtime behavior split across:
  - `settings/.env` for the internal SQLite batch-size setting.
  - `settings/configurations.json` for non-database runtime settings such as `global.seed` and `jobs.polling_interval`.
- Internal application persistence always uses embedded SQLite. PostgreSQL settings belong only to user-configured workflow database nodes and are not used for application records.
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
- The Windows launcher starts uvicorn, waits for `/docs`, then starts Vite preview and opens the UI URL.

## Shared Runtime Data
- Shared persistence lives under `PARAGRAPH_RESOURCES_DIR` when configured, or under `app/resources` by default. This includes workflows, database files, logs, artifacts, and model assets.
- The launcher imports `settings/.env` into the process environment before starting either process. Its fallback values are `FASTAPI_PORT=8000` and `UI_PORT=8001` only when individual keys are absent; the checked-in template overrides them to `5002` and `8002`.
