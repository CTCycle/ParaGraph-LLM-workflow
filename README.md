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
- **Building RAG pipelines** with embedding, vector storage, retrieval, reranking, and answer synthesis stages.

> **Work in Progress**: ParaGraph is under active development. Behavior and available features may evolve.

## User Documentation

- [User Manual](assets/docs/USER_MANUAL.md)

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

### 2.3 Desktop Packaging (Windows, Tauri)

1. Activate desktop runtime profile:
   - `copy /Y ParaGraph\settings\.env.local.tauri.example ParaGraph\settings\.env`
2. Ensure local portable runtimes are provisioned:
   - `ParaGraph\start_on_windows.bat`
3. Build Tauri desktop release:
   - `release\tauri\build_with_tauri.bat`

Generated artifacts:
- `release/windows/installers`
- `release/windows/portable`

## 3. Usage

### 3.1 Launching

- Run `ParaGraph/start_on_windows.bat` for the standard local workflow.
- The app serves backend and frontend using values from `ParaGraph/settings/.env`.
- For packaged desktop mode, Tauri launches the backend directly and serves the built frontend from backend static assets.

### 3.2 Typical User Workflow

1. Configure runtime and provider access (profiles, provider/model availability).
2. Build or edit a node workflow in the visual editor.
3. Compile and start an execution run.
4. Monitor status via polling/websocket events.
5. Inspect generated outputs and execution history.

### 3.3 Typical RAG Path

1. `LOAD_DOCUMENTS`
2. Chunking node(s)
3. `TEXT_EMBEDDING`
4. `VECTOR_STORE`
5. `PROMPT_TEMPLATE` for retrieval query rendering
6. `SIMILARITY_SEARCH`
7. `RERANK_RESULTS`
8. `PROMPT_TEMPLATE` for final answer prompt
9. `LLM_CHAT` or `LLM_STRUCTURED`

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
- `ParaGraph/settings/.env.local.tauri.example`
- `ParaGraph/settings/.env.tauri`
- `ParaGraph/settings/configurations.json`

Runtime variables commonly used in local execution:

| Variable | Description |
| --- | --- |
| `FASTAPI_HOST` | Backend bind host for the FastAPI server. |
| `FASTAPI_PORT` | Backend bind port for the FastAPI server. |
| `UI_HOST` | Frontend host binding. |
| `UI_PORT` | Frontend port binding. |
| `VITE_API_BASE_URL` | Frontend API base URL (typically relative, e.g. `/api`). |
| `PARAGRAPH_CLOUD_MODE` | Cloud mode flag (`true` enables cloud restrictions). |
| `RELOAD` | Enables hot-reload for local launcher runs when `true`. |
| `LLM_TIMEOUT_S` | Timeout used by LLM HTTP clients. |

Provider-specific credentials and runtime endpoints are managed in-app under **Configurations** (session settings), not via `.env`.
Database mode and connection/tuning values are defined in `ParaGraph/settings/configurations.json`.

## 6. Resources and Storage

Runtime artifacts are stored under `ParaGraph/resources`.
This includes generated artifacts, logs, model assets, node assets, workflow persistence, and local database files used by runtime execution.

## 7. Maintenance Scripts

- `ParaGraph/setup_and_maintenance.bat`: setup and maintenance utility for local environment operations.
- `tests/run_tests.bat`: end-to-end local test orchestration across backend/frontend suites.
- `release/tauri/build_with_tauri.bat`: Windows Tauri release build and artifact export.
- `release/tauri/scripts/clean-tauri-build.ps1`: cleanup helper for Tauri release outputs.
- `release/tauri/scripts/export-windows-artifacts.ps1`: export helper for installer and portable release artifacts.

## 8. License

This project is licensed under the **MIT License**. See `LICENSE` for details.
