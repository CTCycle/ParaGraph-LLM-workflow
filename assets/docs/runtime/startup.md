# Startup
Last updated: 2026-10-26

## Local Launcher
PowerShell:

```powershell
.\start_on_windows.ps1
```

The menu can launch the application, install dependencies, initialize the database, run tests, clear logs or caches, and uninstall local runtime files. Cache and data removal uses deterministic deepest-first individual deletion so locked or protected entries can be reported without issuing a recursive delete.

The interactive menu provides these options:

- `1` Launch application: starts one uvicorn backend in a visible console that serves the built frontend and the API on the same origin, waits for `/docs` and the app root, opens `http://<FASTAPI_HOST>:<FASTAPI_PORT>/`, then exits the launcher. If the backend port is occupied, the launcher lists the port, PID, and process name and asks once whether to terminate the listed process trees. The default is no; a declined prompt returns to the menu without starting the application.
- `2` Kill all application processes, including the backend, any frontend dev server on the configured UI port, and the backend console. This is a hard process-tree kill; prefer Ctrl+C in the backend console for a graceful stop.
- `3` Install or update portable runtimes, Python dependencies, frontend dependencies, the Playwright Chromium browser, and the frontend build.
- `4` Rebuild the frontend unconditionally, using the existing frontend dependencies.
- `5` Initialize or upgrade the application database with Alembic.
- `6` Run the project test suite.
- `7` Check for a different `origin/main` revision without downloading or applying changes.
- `8` Update from `origin/main` with `git pull`; this requires a clean worktree and the `main` branch to be checked out.
- `9` Remove application log files.
- `10` Clear the complete disposable cache hierarchy under `runtimes/cache`, preserving the tracked `.gitkeep` sentinel and application data.
- `11` Remove user data and the embedded database, including database sidecars, while preserving application files and settings. This requires an affirmative response at a `[y/N]` confirmation prompt.
- `12` Uninstall local runtimes, dependencies, caches, and build output while preserving dependency lockfiles, settings, and user data.
- `13` Exit without changing the workspace.

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
After a frontend build exists (launcher option `3` or `4`), the plain backend command above without `--reload` serves the application at `http://127.0.0.1:5002/`. `VITE_API_BASE_URL` must be set in the environment or `settings/.env` so the backend knows the API path prefix.

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

- The local launcher is the recommended Windows entry point.
- First-run startup can be slow because of dependency synchronization, migration execution, and runtime hydration.
- Launcher option `1` reports each startup phase and total launch duration in aligned `[TIME]` lines measured in milliseconds; timings also print for phases that fail or are cancelled.
- If `settings/.env` is missing, the launcher and backend environment loader create it from `settings/.env.example` before loading settings. An existing local `.env` is never overwritten.
- Launcher option `1` opens a visible dedicated backend terminal only after its port guard succeeds. Option `2` stops the backend, any dev server, and the titled backend console as an explicit user-selected cleanup operation. If option `1` later fails, it cleans only the backend process created by that launch attempt. Ctrl+C in the backend console runs uvicorn's graceful shutdown (job manager and database engines are released) and frees the port; the console stays open so the logs remain readable.
- Launcher option `3` creates or refreshes dependencies, runs database initialization, and rebuilds the frontend. Option `4` always rebuilds only the frontend using the existing frontend dependencies. Option `1` serves the existing build output when its content fingerprint is current; it rebuilds only when the output, fingerprint, or a build input is missing or stale.
- The option `1` build fingerprint covers `src/**`, `public/**`, `index.html`, the package manifests, both TypeScript configs, `vite.config.ts`, the `npm run build` contract, and the effective `VITE_API_BASE_URL`. Runtime-only host, port, reload, database, and provider settings do not invalidate a current compiled bundle.
- If `package.json` or `package-lock.json` is newer than `node_modules/.package-lock.json`, option `1` repairs frontend dependencies before evaluating/rebuilding the bundle. Dependency repair and build freshness are separate decisions.
- Set `PARAGRAPH_RESOURCES_DIR` in `settings/.env` to relocate shared resource data and the embedded SQLite database; leave it blank to use `data`.
- Application initialization and startup check `alembic_version` and automatically apply pending migrations before validations or repository use. PostgreSQL is only selected explicitly by user-facing workflow database nodes.
- A database without an Alembic revision, or with a partial or incompatible
  schema, stops startup with an actionable error and is never overwritten.
- Option 3 synchronizes dependencies, runs the same migration check, and then builds the frontend. Option 5 can be repeated safely to create or upgrade the database without duplicating schema objects.
- The template defaults are backend `127.0.0.1:5002` (application URL) and frontend dev server `127.0.0.1:8002` (used only by `npm run dev`); edit `settings/.env` if those ports are unavailable.
- The launcher checks the backend documentation endpoint and the application root before reporting success. No Vite preview server runs in launcher mode. Option `1` never performs the broad option-`2` process cleanup automatically.
