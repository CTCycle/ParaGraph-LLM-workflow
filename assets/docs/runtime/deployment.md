# Deployment
Last updated: 2026-07-11

## Supported Operation Model
- ParaGraph is run locally as separate FastAPI and Vite processes.
- `start_on_windows.ps1` is the supported Windows bootstrap and maintenance entry point.
- Manual development startup remains available when backend and frontend process control is needed.

## Limitations And Constraints
- No installer, standalone executable, or container image is produced by this repository.
- Long-running workflow execution uses background threads with poll and event-stream status updates.
- Runtime-heavy folders such as `runtimes`, `app/server/.venv`, and `app/client/node_modules` are operational artifacts, not source-of-truth code.

## Operational Guidance
- Keep `settings/.env` local and derive it from `settings/.env.example` when needed.
- Do not commit generated runtime environments, dependency folders, logs, or user data.
- Keep these notes aligned with `start_on_windows.ps1` and the manual startup commands.
