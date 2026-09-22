# Configuration
Last updated: 2026-09-22

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
- `PARAGRAPH_RESOURCES_DIR` is blank by default, which keeps shared resource data under `app/resources`.
- Set `PARAGRAPH_RESOURCES_DIR` to an absolute path or a path relative to the repository root to relocate resource data, including the embedded SQLite database.

## Runtime Settings
- Launcher option `3` creates or refreshes dependencies and the frontend build. Option `4` explicitly rebuilds the frontend. Application launch repairs missing dependencies independently, then serves the existing build when its content fingerprint is current.
- Database and runtime behavior split across:
  - `settings/.env` for the internal SQLite batch-size setting.
  - `settings/configurations.json` for non-database runtime settings such as `global.seed` and `jobs.polling_interval`.
- Internal application persistence always uses embedded SQLite. PostgreSQL settings belong only to user-configured workflow database nodes and are not used for application records.
- Provider credentials and endpoint overrides are persisted as canonical
  `provider_configurations` records.
- Ollama is represented by one provider configuration with an optional
  `base_url` and `metadata.chat_model` / `metadata.embedding_model`. DeepSeek,
  LM Studio, and llama.cpp use the same provider-configuration contract.
- Default provider endpoints:
  - DeepSeek: `https://api.deepseek.com`
  - LM Studio: `http://localhost:1234/v1`
  - llama.cpp: `http://localhost:8080/v1`

## Cross-Runtime Communication
- Frontend to backend communication targets the relative API base path `/api`.
- In web mode, Vite handles proxying or rewriting to the backend.
- WebSocket execution streaming uses `/api/executions/ws/runs/{run_id}` derived from the current origin.
- The Windows launcher starts uvicorn, waits for `/docs`, then starts Vite preview and opens the UI URL.

## Frontend Build Freshness
- Option `1` records a SHA-256 fingerprint at `runtimes/cache/frontend-dist/.paragraph-build-fingerprint` after a successful `npm run build`.
- The fingerprint includes every file under `app/client/src` and `app/client/public`, `index.html`, `package.json`, `package-lock.json`, `tsconfig.json`, `tsconfig.node.json`, `vite.config.ts`, and the effective `VITE_API_BASE_URL` exposed to the frontend bundle.
- A missing output, missing or malformed fingerprint, changed content, or changed `VITE_API_BASE_URL` triggers a rebuild. A source timestamp change without a content change does not.
- Frontend dependency manifests newer than `app/client/node_modules/.package-lock.json` trigger dependency repair independently of the build fingerprint.
- `FASTAPI_HOST`, `FASTAPI_PORT`, `UI_HOST`, `UI_PORT`, `RELOAD`, database settings, and model/provider runtime settings are runtime-only values. Changing them does not invalidate a current compiled bundle; the launcher applies them when starting uvicorn or Vite preview.
- A failed or interrupted build does not receive a new fingerprint. Option `1` therefore rebuilds on the next attempt.

## Shared Runtime Data
- Shared runtime data lives under `PARAGRAPH_RESOURCES_DIR` when configured, or under `app/resources` by default. This includes the SQLite database, logs, artifacts, node assets, workflow templates, and model assets. The active workflow graph remains in browser storage and JSON exports.
- The launcher imports `settings/.env` into the process environment before starting either process. `FASTAPI_HOST`, `FASTAPI_PORT`, `UI_HOST`, `UI_PORT`, and `RELOAD` are required; missing or invalid runtime values fail fast rather than selecting hidden port fallbacks.
- All disposable runtime, test, tool, browser, and generated frontend-build data is kept under `runtimes/cache`. This hierarchy is separate from persistent application runtime data and user resources under `app/resources`.
