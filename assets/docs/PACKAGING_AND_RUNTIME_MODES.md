# ParaGraph Packaging and Runtime Modes
Last updated: 2026-04-10

## 1. Runtime strategy

ParaGraph is configuration-first and uses one active runtime file:
- `ParaGraph/settings/.env`

Modes:
- Local mode (default developer workflow)
- Desktop packaged mode (Tauri shell + local backend runtime)

Switch modes by copying a profile into `ParaGraph/settings/.env`.

## 2. Runtime profile files

- `ParaGraph/settings/.env.local.example`
- `ParaGraph/settings/.env.local.tauri.example`
- `ParaGraph/settings/.env` (active)
- `ParaGraph/settings/.env.tauri` (frontend build-mode overrides for desktop packaging)
- `ParaGraph/settings/configurations.json` (non-secret defaults/tuning, including database settings)

## 3. Environment contract (core keys)

| Key | Purpose |
|---|---|
| `FASTAPI_HOST`, `FASTAPI_PORT` | Backend bind host/port. |
| `UI_HOST`, `UI_PORT` | Frontend host/port for local preview mode. |
| `VITE_API_BASE_URL` | Frontend API base path (`/api` in local web mode, `/` in packaged desktop build mode). |
| `PARAGRAPH_CLOUD_MODE` | Cloud mode flag (`true` enables cloud restrictions). |
| `RELOAD` | Backend auto-reload toggle for local workflow. |
| `MPLBACKEND` | Runtime Matplotlib backend override (optional). |
| `KERAS_BACKEND` | Runtime Keras backend override (optional). |
| `LLM_TIMEOUT_S` | Timeout used by LLM HTTP clients. |

Database values are loaded from `settings/configurations.json`.
Provider credentials/endpoints are managed in the UI Configurations flow and persisted by the application.

## 4. Local mode

1. Activate profile:
   - `copy /Y ParaGraph\settings\.env.local.example ParaGraph\settings\.env`
2. Start application:
   - `ParaGraph\start_on_windows.bat`
3. Optional full test run:
   - `tests\run_tests.bat`

## 5. Desktop packaged mode (Tauri)

Build entrypoint:
- `release\tauri\build_with_tauri.bat`

Typical flow:
1. Activate desktop profile:
   - `copy /Y ParaGraph\settings\.env.local.tauri.example ParaGraph\settings\.env`
2. Ensure runtimes exist:
   - `ParaGraph\start_on_windows.bat`
3. Ensure Rust toolchain is available (`rustup`).
4. Build package:
   - `release\tauri\build_with_tauri.bat`

Packaged runtime behavior:
- Tauri starts a local Python backend (`uvicorn ParaGraph.server.app:app`) with `PARAGRAPH_TAURI_MODE=true`.
- Backend serves packaged frontend static assets from `ParaGraph/client/dist`.
- Runtime setup prefers reusable `runtimes/.venv`, otherwise runs `uv sync --frozen` against bundled runtime lockfiles.
- On shutdown, desktop wrapper terminates the backend process tree.

Windows artifacts:
- `release/windows/installers`
- `release/windows/portable`

## 6. Deterministic build notes

- Backend lockfile: `runtimes/uv.lock`.
- Frontend lockfile: `ParaGraph/client/package-lock.json`.
- Tauri packaging requires Rust tooling on the build host (`cargo` + a default `rustup` toolchain such as `stable`).

