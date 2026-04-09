# ParaGraph Packaging and Runtime Modes
Last updated: 2026-04-08

## 1. Strategy

ParaGraph uses one active runtime profile file: `ParaGraph/settings/.env`.

- Local web app mode: run directly on the host via launcher.
- Local packaged app mode: distribute the app as a packaged Tauri desktop build.
- Mode switching: update/copy the active local `.env` profile when running the web app.
- Backend code paths are split by ownership:
  - `settings/configurations.json`: technical defaults (`database`, `global`, `jobs`)
  - `.env`: runtime environment values (ports, deployment mode, reload, runtime toggles)
  - UI Configurations: provider credentials/endpoints and Ollama session defaults

## 2. Runtime Profiles

- `ParaGraph/settings/.env.local.example`: local defaults (loopback hosts, embedded SQLite).
- `ParaGraph/settings/.env`: active profile used by the launcher and tests.
- `ParaGraph/settings/configurations.json`: non-secret defaults (`database`, `global`, `jobs`).

## 3. Required Environment Keys

| Key | Purpose |
|---|---|
| `FASTAPI_HOST`, `FASTAPI_PORT` | Backend bind host/port. |
| `UI_HOST`, `UI_PORT` | Frontend host/port for local preview. |
| `VITE_API_BASE_URL` | Frontend API base path (default `/api`). |
| `PARAGRAPH_CLOUD_MODE` | Cloud mode flag (`true` enables cloud restrictions). Cloud mode disables public docs/openapi routes and enforces tighter filesystem guards for workflow artifacts. |
| `RELOAD` | Enables Uvicorn reload in launcher flow when `true`. |
| `LLM_TIMEOUT_S` | Timeout used by LLM HTTP clients. |

Provider credentials/endpoints (`ollama`, `openai`, `gemini`, `claude`, `huggingface`) are managed in the UI Configurations flow and stored in the application session database.

Database mode and connection/tuning values are loaded from `settings/configurations.json`.

## 4. Local Web App Mode (Windows)

1. Copy local profile to active env:
   - `copy /Y ParaGraph\settings\.env.local.example ParaGraph\settings\.env`
2. Start app:
   - `ParaGraph\start_on_windows.bat`
3. Optional tests:
   - `tests\run_tests.bat`

This mode is fully local.

### Cloud deployment note

- Set `PARAGRAPH_CLOUD_MODE=true` for gateway-backed deployments.
- In this mode, frontend API access is expected through the configured relative gateway path (`VITE_API_BASE_URL`, typically `/api`).
- Backend docs/OpenAPI UI routes are disabled by default in cloud mode.

### Launcher behavior summary

`start_on_windows.bat` currently:
- installs portable Python 3.14, `uv`, and Node.js under `runtimes/` at repository root
- syncs backend deps from `pyproject.toml` using runtime-local state and installs all declared dependencies unconditionally:
  - virtual environment: `runtimes/.venv`
  - lockfile source of truth: `runtimes/uv.lock` (mirrored through root `uv.lock` during sync)
- installs frontend deps and builds client when needed
- starts backend (`uvicorn ParaGraph.server.app:app`) and frontend preview server

## 5. Local Packaged App Mode

ParaGraph also supports local desktop distribution as a packaged Tauri application.

- Treat the packaged app as a local-only delivery target.
- Reuse the same backend/runtime assumptions as the local web app flow.
- Keep release documentation limited to local runtime and packaging flows.

## 6. Deterministic Build Notes

- Backend dependencies are lockfile-backed through `runtimes/uv.lock` and installed into `runtimes/.venv`.
- Frontend dependencies are lockfile-backed via `ParaGraph/client/package-lock.json` and installed via `npm ci` (fallback `npm install`).
- Tauri packaging requires Rust tooling on the build host (`cargo` + a default `rustup` toolchain such as `stable`).

