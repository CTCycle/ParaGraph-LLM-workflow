# Troubleshooting And Data
Last updated: 2026-08-31

## Troubleshooting
- If startup fails, rerun `start_on_windows.ps1` and check the console output.
- If startup reports a database migration failure, stop other ParaGraph instances, resolve the reported schema or file-lock problem, and rerun option 4. The migration runner fails closed and does not replace existing application tables.
- If an unversioned database is reported as incompatible, preserve a copy of
  the database and use an explicit reviewed migration or recovery procedure;
  do not delete or recreate `alembic_version` to bypass the check.
- If APIs are unreachable, verify host and port values in `settings/.env`.
- If model operations fail, verify provider credentials and network reachability.
- If compile fails, inspect diagnostics and fix missing inputs, controller mismatches, or type mismatches.
- To reset local user data, use launcher option 10 (`Remove All Data`), give an affirmative response at the `[y/N]` confirmation prompt, and restart the application so a fresh database can be initialized.

## Data Location
Runtime data is stored under `app/resources` by default. Set `PARAGRAPH_RESOURCES_DIR` in `settings/.env` to use another absolute or repository-relative location. Stored data includes:

- Local database
- Logs
- Browser-local workflow editor state and JSON exports
- Node assets and plugins
- Downloaded model artifacts
- Browser upload artifacts

Launcher option 10 removes the database, database sidecars, logs, downloaded
model artifacts, runtime artifacts, and imported custom-node contents. Built-in
node definitions, workflow templates, settings, browser-local workflow state,
and application source files are preserved. Clear the browser site's storage
separately when the active editor graph must be reset.
