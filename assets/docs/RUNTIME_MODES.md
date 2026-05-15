# RUNTIME_MODES

Last updated: 2026-04-24

## Supported Modes

### 1. Local Launcher Mode (Web App + API)

- Primary Windows mode.
- Uses `ParaGraph\start_on_windows.bat` to bootstrap portable runtimes, sync Python deps, build/serve frontend, and run backend.
- Frontend runs from Vite preview; backend runs as uvicorn.

### 2. Manual Development Mode

- Backend and frontend started separately for development control.
- Backend: FastAPI/uvicorn process.
- Frontend: Vite dev server (`npm run dev`) or preview/build scripts.

### 3. Desktop Packaged Mode (Tauri)

- Implemented via `app/client/src-tauri`.
- Desktop app boots backend runtime internally, then loads web UI in Tauri window.
- Release packaging provided by `release/tauri/build_with_tauri.bat` and npm tauri scripts.

### 4. Containerized Mode

- No Docker/container runtime is implemented in this repository at present.

## Startup Procedures

### Local launcher (recommended)

CMD:

```bat
ParaGraph\start_on_windows.bat
```

PowerShell:

```powershell
.\ParaGraph\start_on_windows.bat
```

### Manual backend

CMD:

```bat
runtimes\.venv\Scripts\python.exe -m uvicorn server.app:app --host 127.0.0.1 --port 5002 --reload
```

PowerShell:

```powershell
.\runtimes\.venv\Scripts\python.exe -m uvicorn server.app:app --host 127.0.0.1 --port 5002 --reload
```

### Manual frontend

CMD:

```bat
cd ParaGraph\client
npm run dev
```

PowerShell:

```powershell
Set-Location ParaGraph\client
npm run dev
```

### Desktop build/package

CMD:

```bat
copy /Y ParaGraph\settings\.env.local.tauri.example ParaGraph\settings\.env
ParaGraph\start_on_windows.bat
release\tauri\build_with_tauri.bat
```

PowerShell:

```powershell
Copy-Item ParaGraph\settings\.env.local.tauri.example ParaGraph\settings\.env -Force
.\ParaGraph\start_on_windows.bat
.\release\tauri\build_with_tauri.bat
```

## Configuration Differences

- Shared environment keys come from `settings/.env*`.
- Local defaults (`.env.local.example`): `FASTAPI_PORT=5002`, `UI_PORT=8002`, `VITE_API_BASE_URL=/api`, `RELOAD=true`.
- Tauri-oriented local example (`.env.local.tauri.example`) sets `RELOAD=false`.
- In packaged desktop mode, backend sets `PARAGRAPH_TAURI_MODE=true`; server serves static `client/dist` from FastAPI root.
- Database/runtime behavior comes from `settings/configurations.json`:
  - Default embedded SQLite (`embedded_database=true`).
  - Optional PostgreSQL when embedded mode is disabled.

## Interoperability Between Runtimes

- Frontend-to-backend communication always targets relative API base (`/api`) and is proxied/rewritten by Vite in web mode.
- WebSocket execution streaming uses `/api/executions/ws/runs/{run_id}` derived from current origin.
- Tauri runtime hosts both layers locally:
  - Rust launcher starts backend uvicorn.
  - UI window redirects to backend URL after readiness check.
- Shared persistence layer is under `app/resources` (workflows, db, logs, artifacts, models).

## Limitations and Constraints

- Packaged desktop launcher logic is Windows-only in current implementation.
- First run can be slow due to `uv sync`, runtime hydration, and frontend build steps.
- Long-running workflow execution uses background threads, with poll + event stream status updates.
- Runtime-heavy folders (`release/windows`, `src-tauri/target`, `client/node_modules`) are operational artifacts, not source-of-truth code.

## Deployment Notes

- Desktop packaging target is Tauri bundle output (`msi`, `setup.exe`, portable executable).
- Build orchestration is script-driven (`release/tauri/build_with_tauri.bat`).
- Exported artifacts are copied into `release/windows/installers` and `release/windows/portable`.

