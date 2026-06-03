# Troubleshooting And Data
Last updated: 2026-06-02

## Troubleshooting
- If startup fails, rerun `start_on_windows.bat` and check the console output.
- If APIs are unreachable, verify host and port values in `settings/.env`.
- If model operations fail, verify provider credentials and network reachability.
- If compile fails, inspect diagnostics and fix missing inputs, controller mismatches, or type mismatches.

## Data Location
Runtime data is stored under `app/resources`, including:

- Local database
- Logs
- Workflow persistence
- Node assets and plugins
- Downloaded model artifacts
- Browser upload artifacts
