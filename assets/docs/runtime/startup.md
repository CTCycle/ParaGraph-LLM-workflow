# Startup
Last updated: 2026-07-11

## Local Launcher
PowerShell:

```powershell
.\start_on_windows.ps1
```

The menu can launch the application, install dependencies, initialize the database, run tests, clear logs or caches, and uninstall local runtime files.

## Manual Backend
CMD:

```bat
runtimes\.venv\Scripts\python.exe -m uvicorn server.app:app --host 127.0.0.1 --port 8055 --reload
```

PowerShell:

```powershell
.\runtimes\.venv\Scripts\python.exe -m uvicorn server.app:app --host 127.0.0.1 --port 8055 --reload
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
- If `settings/.env` is missing, the launcher creates it from `settings/.env.example` before loading settings.
- Set `BACKEND_VISIBLE=true` to open a dedicated backend log terminal; the default keeps the backend window hidden.
