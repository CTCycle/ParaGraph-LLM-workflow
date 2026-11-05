# Startup
Last updated: 2026-11-05

## Local Launcher

Use start_on_windows.bat from CMD or PowerShell to start ParaGraph. The wrapper invokes PowerShell 7 with setup_and_maintenance.ps1 -Launch, including first-run portable runtime, dependency, database, and frontend setup.

Run setup_and_maintenance.ps1 directly to open the maintenance menu:

```powershell
.\setup_and_maintenance.ps1
```

Pass -DryRun to preview maintenance options without changing files:

```powershell
.\setup_and_maintenance.ps1 -DryRun
```

Select maintenance options 8, 9, 10, or 11 to preview that action. Other actions are not started in dry-run mode. Cleanup and uninstall stop while ParaGraph processes are running; stop them with maintenance option 1 first.

The interactive menu provides these options:

- `1` Kill all application processes, including the backend, any frontend dev server on the configured UI port, and the backend console. This is a hard process-tree kill; prefer Ctrl+C in the backend console for a graceful stop.
- `2` Install or update portable runtimes, Python dependencies, frontend dependencies, the Playwright Chromium browser, and the frontend build.
- `3` Rebuild the frontend unconditionally, using the existing frontend dependencies.
- `4` Initialize or upgrade the application database with Alembic.
- `5` Run the project test suite.
- `6` Check for a different `origin/main` revision without downloading or applying changes.
- `7` Update from `origin/main` with `git pull`; this requires a clean worktree and the `main` branch to be checked out.
- `8` Remove ParaGraph-generated `ParaGraph_*.log` files under the configured resource root.
- `9` Clear the canonical `runtimes/cache` hierarchy, nested Python bytecode and test/tool caches, frontend `.cache` and Vite caches, root coverage outputs, and recognized `assets/cache/pytest-tmp-*` leftovers. It preserves dependency installations, settings, databases, logs, artifacts, and the tracked cache `.gitkeep`.
- `10` Remove resource artifacts, logs, models, custom nodes, and the configured SQLite database with its `-wal`, `-shm`, and `-journal` sidecars. The exact paths are shown before the affirmative `[y/N]` confirmation. Settings, built-in nodes, templates, and browser `localStorage` remain. If the database configuration is missing or invalid, no data is removed.
- `11` Uninstall local runtimes, the backend virtual environment, frontend dependencies, recognized caches and temporary files, and ParaGraph-generated logs. Settings, dependency lockfiles, the database, artifacts, models, custom nodes, templates, and browser `localStorage` are preserved.
- `12` Exit without changing the workspace.

The cache registry covers the project’s configured Python, pytest, Ruff, coverage, Vite, Vitest, ESLint, Playwright, package-manager, model-library, and generated frontend-build locations. Cleanup uses paths rooted from the launcher location, not the shell’s current directory. Reparse points are skipped and reported; arbitrary user-profile and shared browser caches are not scanned.

## Manual Backend
CMD:

```bat
cd app
server\.venv\Scripts\python.exe -m uvicorn server.app:app --host 127.0.0.1 --port 5002 --reload
```

PowerShell:

```powershell
Set-Location app
.\server\.venv\Scripts\python.exe -m uvicorn server.app:app --host 127.0.0.1 --port 5002 --reload
```

## Manual Production Backend
After a frontend build exists (maintenance options 2 or 3), the plain backend command above without `--reload` serves the application at `http://127.0.0.1:5002/`. `VITE_API_BASE_URL` must be set in the environment or `settings/.env` so the backend knows the API path prefix.

## Manual Frontend (development only)
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

- The start_on_windows.bat wrapper is the recommended Windows entry point.
- First-run startup can be slow because of dependency synchronization, migration execution, and runtime hydration.
- Launch mode reports each startup phase and total launch duration in aligned `[TIME]` lines measured in milliseconds; timings also print for phases that fail or are cancelled.
- If `settings/.env` is missing, the launcher and backend environment loader create it from `settings/.env.example` before loading settings. An existing local `.env` is never overwritten.
- Launch mode opens a visible dedicated backend terminal only after its port guard succeeds. Option 1 stops the backend, any dev server, and the titled backend console as an explicit user-selected cleanup operation. If Launch mode later fails, it cleans only the backend process created by that launch attempt. Ctrl+C in the backend console runs uvicorn's graceful shutdown (job manager and database engines are released) and frees the port; the console stays open so the logs remain readable.
- Launcher option 2 creates or refreshes dependencies, runs database initialization, and rebuilds the frontend. Option 3 always rebuilds only the frontend using the existing frontend dependencies. Launch mode serves the existing build output when its content fingerprint is current; it rebuilds only when the output, fingerprint, or a build input is missing or stale.
- The Launch mode build fingerprint covers `src/**`, `public/**`, `index.html`, the package manifests, both TypeScript configs, `vite.config.ts`, the `npm run build` contract, and the effective `VITE_API_BASE_URL`. Runtime-only host, port, reload, database, and provider settings do not invalidate a current compiled bundle.
- If `package.json` or `package-lock.json` is newer than `node_modules/.package-lock.json`, Launch mode repairs frontend dependencies before evaluating/rebuilding the bundle. Dependency repair and build freshness are separate decisions.
- Set `PARAGRAPH_RESOURCES_DIR` in `settings/.env` to relocate shared resource data and the embedded SQLite database; leave it blank to use `data`.
- Application initialization and startup check `alembic_version` and automatically apply pending migrations before validations or repository use. PostgreSQL is only selected explicitly by user-facing workflow database nodes.
- A database without an Alembic revision, or with a partial or incompatible
  schema, stops startup with an actionable error and is never overwritten.
- Option 2 synchronizes dependencies, runs the same migration check, and then builds the frontend. Option 4 can be repeated safely to create or upgrade the database without duplicating schema objects.
- The template defaults are backend `127.0.0.1:5002` (application URL) and frontend dev server `127.0.0.1:8002` (used only by `npm run dev`); edit `settings/.env` if those ports are unavailable.
- The launcher checks the backend documentation endpoint and the application root before reporting success. No Vite preview server runs in launcher mode. Launch mode never performs the broad option-`1` process cleanup automatically.
