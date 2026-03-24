# ParaGraph Packaging and Runtime Modes

## 1. Strategy

ParaGraph uses one active runtime file: `ParaGraph/settings/.env`.

- Local web app mode: run directly on the host via launcher.
- Local packaged app mode: distribute the app as a packaged Tauri desktop build.
- Mode switching: update/copy the active local `.env` profile when running the web app.
- Backend code paths are environment-driven (`DB_EMBEDDED`, DB host settings, ports, provider keys).

## 2. Runtime Profiles

- `ParaGraph/settings/.env.local.example`: local defaults (loopback hosts, embedded SQLite).
- `ParaGraph/settings/.env`: active profile used by the launcher and tests.
- `ParaGraph/settings/configurations.json`: non-secret defaults (`global`, `jobs`, base DB mode).

## 3. Required Environment Keys

| Key | Purpose |
|---|---|
| `FASTAPI_HOST`, `FASTAPI_PORT` | Backend bind host/port. |
| `UI_HOST`, `UI_PORT` | Frontend host/port for local preview. |
| `VITE_API_BASE_URL` | Frontend API base path (default `/api`). |
| `PARAGRAPH_DEPLOYMENT_MODE` | Deployment mode switch (`local` or `cloud`). Cloud mode disables public docs/openapi routes and enforces tighter filesystem guards for workflow artifacts. |
| `RELOAD` | Enables Uvicorn reload in launcher flow when `true`. |
| `OPTIONAL_DEPENDENCIES` | Controls optional dependency sync behavior in launcher/test flows. |
| `DB_EMBEDDED` | `true` for SQLite, `false` for PostgreSQL settings. |
| `DB_ENGINE`, `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` | External DB settings used when `DB_EMBEDDED=false`. |
| `DB_SSL`, `DB_SSL_CA`, `DB_CONNECT_TIMEOUT`, `DB_INSERT_BATCH_SIZE` | PostgreSQL TLS/connect/write tuning. |
| `OLLAMA_BASE_URL` | Base URL for local Ollama provider. |
| `OPENAI_API_KEY`, `OPENAI_BASE_URL` | OpenAI provider credentials and endpoint. |
| `GEMINI_API_KEY`, `GEMINI_BASE_URL` | Gemini provider credentials and endpoint. |
| `LLM_TIMEOUT_S` | Timeout used by LLM HTTP clients. |

## 4. Local Web App Mode (Windows)

1. Copy local profile to active env:
   - `copy /Y ParaGraph\settings\.env.local.example ParaGraph\settings\.env`
2. Start app:
   - `ParaGraph\start_on_windows.bat`
3. Optional tests:
   - `tests\run_tests.bat`

This mode is fully local.

### Cloud deployment note

- Set `PARAGRAPH_DEPLOYMENT_MODE=cloud` for gateway-backed deployments.
- In this mode, frontend API access is expected through the configured relative gateway path (`VITE_API_BASE_URL`, typically `/api`).
- Backend docs/OpenAPI UI routes are disabled by default in cloud mode.

### Launcher behavior summary

`start_on_windows.bat` currently:
- installs portable Python 3.14, `uv`, and Node.js under `runtimes/` at repository root
- syncs backend deps from `pyproject.toml` using runtime-local state:
  - virtual environment: `runtimes/.venv`
  - lockfile source of truth: `runtimes/uv.lock` (mirrored through root `uv.lock` during sync)
- installs frontend deps and builds client when needed
- starts backend (Uvicorn) and frontend preview server

## 5. Local Packaged App Mode

ParaGraph also supports local desktop distribution as a packaged Tauri application.

- Treat the packaged app as a local-only delivery target.
- Reuse the same backend/runtime assumptions as the local web app flow.
- Keep release documentation limited to local runtime and packaging flows.

## 6. Deterministic Build Notes

- Backend dependencies are lockfile-backed through `runtimes/uv.lock` and installed into `runtimes/.venv`.
- Frontend dependencies are lockfile-backed via `ParaGraph/client/package-lock.json` and installed via `npm ci` fallbacking to `npm install`.
- Tauri packaging requires Rust tooling on the build host (`cargo` + a default `rustup` toolchain such as `stable`).

