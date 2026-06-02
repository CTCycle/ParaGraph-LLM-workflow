# Startup
Last updated: 2026-06-02

## Local Launcher
CMD:

```bat
start_on_windows.bat
```

PowerShell:

```powershell
.\start_on_windows.bat
```

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

## Desktop Build And Package
CMD:

```bat
copy /Y settings\.env.local.tauri.example settings\.env
start_on_windows.bat
release\tauri\build_with_tauri.bat
```

PowerShell:

```powershell
Copy-Item settings\.env.local.tauri.example settings\.env -Force
.\start_on_windows.bat
.\release\tauri\build_with_tauri.bat
```

## Startup Notes
- The local launcher is the recommended Windows entry point.
- Desktop packaging expects the environment file to be prepared before the build starts.
- First-run startup can be slow because of dependency synchronization, runtime hydration, and frontend build work.
