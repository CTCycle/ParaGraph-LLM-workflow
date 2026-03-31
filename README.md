# ParaGraph LLM Workflow

## 1. Project Overview

ParaGraph is a local-first application for building and running deterministic LLM workflows.

The platform combines:
- A **FastAPI backend** for workflow compilation, execution lifecycle, and provider integration.
- A **React + TypeScript frontend** for visual workflow authoring and runtime monitoring.
- A **manifest-driven execution model** with polling and websocket event streaming.

Primary capabilities include:
- **Designing workflows** using a node-based editor.
- **Compiling and running workflows** through backend execution APIs.
- **Tracking execution events and outputs** in near real time.
- **Managing node catalogs, model providers, and runtime profiles** from the UI.

> **Work in Progress**: ParaGraph is under active development. Behavior and available features may evolve.

## 2. Installation

### 2.1 Windows (Recommended Launcher)

1. Navigate to `ParaGraph`.
2. Run `start_on_windows.bat`.

What the launcher does:
- Bootstraps local runtimes on first run (Python/Node tooling under `runtimes/` when needed).
- Prepares backend dependencies in `runtimes/.venv`.
- Installs frontend dependencies and builds/serves the UI.
- Starts backend and frontend processes with project settings.

First run may take longer due to dependency and runtime setup. Subsequent runs are faster and primarily start services.

### 2.2 Manual Setup (Advanced)

Manual setup is supported for users who prefer explicit control over backend/frontend startup.

Minimum requirements:
- Python environment (project uses `runtimes/.venv` when available).
- Node.js/npm for the frontend.

At a high level:
- Install backend dependencies and run the FastAPI service.
- Install frontend dependencies from `ParaGraph/client` and start/build the UI.

## 3. Usage

### 3.1 Launching

- Run `ParaGraph/start_on_windows.bat` for the standard local workflow.
- The app serves backend and frontend using values from `ParaGraph/settings/.env`.

### 3.2 Typical User Workflow

1. Configure runtime and provider access (profiles, provider/model availability).
2. Build or edit a node workflow in the visual editor.
3. Compile and start an execution run.
4. Monitor status via polling/websocket events.
5. Inspect generated outputs and execution history.

### 3.3 Active API Families

- **Workflows**: `/workflows`, `/workflows/{workflow_id}`, `/workflows/{workflow_id}/versions`
- **Executions**: `/executions/compile`, `/executions`, `/executions/{run_id}`, `/executions/{run_id}/events`, websocket `/executions/ws/runs/{run_id}`
- **Nodes**: `/nodes/catalog`, `/nodes/import`, `/nodes/uploads/directory`, `/nodes/check-database-connection`
- **Providers**: `/providers/models`, `/providers/ollama/library`, `/providers/ollama/pull`, `/providers/huggingface/models`, `/providers/huggingface/download`, `/providers/huggingface/download/{job_id}`
- **Configurations**: `/configurations`, `/configurations/profiles`, `/configurations/profiles/{profile_name}`, `/configurations/ollama/ping`

## 4. Testing

### 4.1 Backend (pytest)

```cmd
.\runtimes\.venv\Scripts\python.exe -m pytest tests/unit tests/e2e -v
```

### 4.2 Frontend Unit (Vitest)

```cmd
cd ParaGraph\client
npm run test:unit
```

### 4.3 Frontend E2E (Playwright)

```cmd
cd ParaGraph\client
npm run test:e2e
```

### 4.4 Full Test Orchestration

```cmd
tests\run_tests.bat
```

This runner executes available backend and frontend suites in sequence.

## 5. Configuration

Primary runtime configuration files:
- `ParaGraph/settings/.env`
- `ParaGraph/settings/.env.local.example`
- `ParaGraph/settings/configurations.json`

Runtime variables commonly used in local execution:

| Variable | Description |
| --- | --- |
| `FASTAPI_HOST` | Backend bind host for the FastAPI server. |
| `FASTAPI_PORT` | Backend bind port for the FastAPI server. |
| `UI_HOST` | Frontend host binding. |
| `UI_PORT` | Frontend port binding. |
| `VITE_API_BASE_URL` | Frontend API base URL (typically relative, e.g. `/api`). |
| `DB_EMBEDDED` | Selects embedded/local database runtime mode. |

Provider-specific credentials and runtime keys are also sourced from the active `.env` profile when required.

## 6. Resources and Storage

Runtime artifacts are stored under `ParaGraph/resources`.

Current resource entries include:
- `artifacts` (generated execution outputs and artifacts)
- `logs` (runtime and process logs)
- `models` (downloaded/managed model assets)
- `nodes` (node-related persisted assets/imports)
- `workflows` (workflow persistence)
- `database.db` (local project database)

## 7. Maintenance Scripts

- `ParaGraph/setup_and_maintenance.bat`: setup and maintenance utility for local environment operations.
- `tests/run_tests.bat`: end-to-end local test orchestration across backend/frontend suites.

## 8. License

This project is licensed under the **MIT License**. See `LICENSE` for details.