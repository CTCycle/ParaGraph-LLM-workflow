# Startup
Last updated: 2026-08-31

## Local Launcher
PowerShell:

```powershell
.\start_on_windows.ps1
```

The menu can launch the application, install dependencies, initialize the database, run tests, clear logs or caches, and uninstall local runtime files.

The interactive menu provides these options:

- `1` Launch application, then exit the launcher after starting the backend and frontend.
- `2` Install or update portable runtimes, Python dependencies, frontend dependencies, and the frontend build.
- `3` Rebuild the frontend only, using the existing frontend dependencies.
- `4` Initialize or upgrade the application database with Alembic.
- `5` Run the project test suite.
- `6` Update from `origin/main` with `git pull`; this requires a clean worktree and the `main` branch to be checked out.
- `7` Check for a different `origin/main` revision without downloading or applying changes.
- `8` Remove application log files.
- `9` Clear runtime caches under `runtimes/cache` and test/tool caches plus generated test/build artifacts under `app/tests/cache`.
- `10` Remove user data and the embedded database, including database sidecars, while preserving application files and settings. This requires typing `REMOVE` to confirm.
- `11` Uninstall local runtimes, dependencies, caches, and build output while preserving dependency lockfiles, settings, and user data.
- `12` Exit without changing the workspace.

## Manual Backend
CMD:

```bat
runtimes\.venv\Scripts\python.exe -m uvicorn server.app:app --host 127.0.0.1 --port 5002 --reload
```

PowerShell:

```powershell
.\runtimes\.venv\Scripts\python.exe -m uvicorn server.app:app --host 127.0.0.1 --port 5002 --reload
```

## Manual Frontend
CMD:

```bat
cd app\client
npm run dev
```

PowerShell:

```powershell
Set-Location app\client
npm run dev
```

## Startup Notes

- The local launcher is the recommended Windows entry point.
- First-run startup can be slow because of dependency synchronization, migration execution, and runtime hydration.
- If `settings/.env` is missing, the launcher and backend environment loader create it from `settings/.env.example` before loading settings. An existing local `.env` is never overwritten.
- Set `BACKEND_LOGS_VISIBLE=true` to open a dedicated backend log terminal; set it to `false` for a hidden detached backend. The key is required.
- Launcher option `2` creates or refreshes dependencies and the frontend build. Option `3` rebuilds only the frontend using the existing frontend dependencies. Option `1` serves the existing build output and rebuilds it only when the build or required environment is missing or unusable.
- Set `PARAGRAPH_RESOURCES_DIR` in `settings/.env` to relocate shared resource data and the embedded SQLite database; leave it blank to use `app/resources`.
- Application initialization and startup check `alembic_version` and automatically apply pending migrations before validations or repository use. PostgreSQL is only selected explicitly by user-facing workflow database nodes.
- A database without an Alembic revision, or with a partial or incompatible
  schema, stops startup with an actionable error and is never overwritten.
- Option 2 synchronizes dependencies, runs the same migration check, and then builds the frontend. Option 4 can be repeated safely to create or upgrade the database without duplicating schema objects.
- The template defaults are backend `127.0.0.1:5002` and frontend `127.0.0.1:8002`; edit `settings/.env` if those ports are unavailable.
- The launcher checks the backend documentation endpoint before starting the frontend preview and releases listeners occupying the configured ports.
