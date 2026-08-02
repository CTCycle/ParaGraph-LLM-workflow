# Startup
Last updated: 2026-07-20

## Local Launcher
PowerShell:

```powershell
.\start_on_windows.ps1
```

The menu can launch the application, install dependencies, initialize the database, run tests, clear logs or caches, and uninstall local runtime files.

The interactive menu provides these options:

- `1` Launch application, then exit the launcher after starting the backend and frontend.
- `2` Install or update portable runtimes, Python dependencies, frontend dependencies, and the frontend build.
- `3` Initialize the application database and reseed catalogs.
- `4` Run the project test suite.
- `5` Remove application log files.
- `6` Clear Python and uv caches.
- `7` Uninstall local runtimes, dependencies, caches, and lockfiles while preserving settings and user data.
- `8` Exit without changing the workspace.

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
- First-run startup can be slow because of dependency synchronization, runtime hydration, and frontend build work.
- If `settings/.env` is missing, the launcher and backend environment loader create it from `settings/.env.example` before loading settings. An existing local `.env` is never overwritten.
- Set `BACKEND_LOGS_VISIBLE=true` to open a dedicated backend log terminal. If the key is absent, the launcher defaults to visible logs; set it to `false` for a hidden detached backend.
- Set `ALWAYS_REBUILD=false` to skip the frontend build during application startup; it defaults to `true`.
- The template defaults are backend `127.0.0.1:5002` and frontend `127.0.0.1:8002`; edit `settings/.env` if those ports are unavailable.
- The launcher checks the backend documentation endpoint before starting the frontend preview and releases listeners occupying the configured ports.
