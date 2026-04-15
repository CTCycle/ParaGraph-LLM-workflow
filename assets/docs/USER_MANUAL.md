# ParaGraph User Manual
Last updated: 2026-04-10

## 1. What ParaGraph Is

ParaGraph is a local-first application for designing and running deterministic LLM workflows.

Core experience:
- Build workflows in a visual node editor.
- Configure providers and runtime profiles.
- Compile and run workflows.
- Monitor progress and inspect outputs.

## 2. Getting Started

### 2.1 Start the application (Windows)

1. Open the repository root.
2. Run `ParaGraph\start_on_windows.bat`.
3. Wait for backend and frontend services to become available.

### 2.2 Verify startup

- Frontend opens in your browser using `UI_HOST` and `UI_PORT`.
- Backend serves API routes using `FASTAPI_HOST` and `FASTAPI_PORT`.

If this is the first run, setup can take longer due to dependency/runtime bootstrap.

### 2.3 Desktop packaged mode (Tauri)

ParaGraph desktop packaging is available via Tauri. See `assets/docs/PACKAGING_AND_RUNTIME_MODES.md` for the full build/runtime contract.

## 3. Main User Journeys

### 3.1 Build and run a workflow

1. Open the Workflow page.
2. Add nodes from the catalog.
3. Configure node parameters.
4. Connect nodes using data and controller links.
5. Compile the workflow.
6. Start execution.
7. Monitor status and view outputs/events.

### 3.2 Configure providers and profiles

1. Open Configurations.
2. Enter provider credentials and runtime values.
3. Save configuration or named profile.
4. Optionally test Ollama connectivity.

### 3.3 Browse/manage models

1. Open Models.
2. Check provider catalog/model availability.
3. Pull Ollama models when needed.
4. Search/download Hugging Face models and track download status.

### 3.4 Manage node library

1. Open Nodes.
2. Browse shipped node catalog.
3. Import custom manifests through the node import flow.

## 4. Primary Commands

### 4.1 Launch and setup

- Standard launcher:
  - `ParaGraph\start_on_windows.bat`
- Optional maintenance:
  - `ParaGraph\setup_and_maintenance.bat`
- Switch runtime profile to local mode:
  - `copy /Y ParaGraph\settings\.env.local.example ParaGraph\settings\.env`
- Switch runtime profile to local Tauri mode:
  - `copy /Y ParaGraph\settings\.env.local.tauri.example ParaGraph\settings\.env`
- Build desktop artifacts (Windows):
  - `release\tauri\build_with_tauri.bat`

### 4.2 Testing commands

- Backend tests:
  - `.\runtimes\.venv\Scripts\python.exe -m pytest tests/unit tests/e2e -v`
- Frontend unit tests:
  - `cd ParaGraph\client && npm run test:unit`
- Frontend E2E:
  - `cd ParaGraph\client && npm run test:e2e`
- Combined orchestration:
  - `tests\run_tests.bat`

## 5. Usage Patterns

### 5.1 General workflow pattern

1. Configure runtime/provider access first.
2. Build graph structure.
3. Compile before each run to validate links/contracts.
4. Start execution and monitor events.
5. Inspect outputs and iterate.

### 5.2 Typical RAG pattern

1. `LOAD_DOCUMENTS`
2. One or more chunking nodes
3. `TEXT_EMBEDDING`
4. `VECTOR_STORE`
5. `PROMPT_TEMPLATE` for retrieval query creation
6. `SIMILARITY_SEARCH`
7. `RERANK_RESULTS` (optional but recommended)
8. `PROMPT_TEMPLATE` for answer synthesis
9. `LLM_CHAT` or `LLM_STRUCTURED`

## 6. Key Features

- Manifest-driven node catalog and parameter forms.
- Compile-time and runtime validation for deterministic execution flow.
- Execution monitoring through:
  - run polling (`/executions/{run_id}`)
  - event history (`/executions/{run_id}/events`)
  - live websocket stream (`/executions/ws/runs/{run_id}`)
- Provider integrations for model discovery and operations:
  - `/providers/catalog`
  - `/providers/models`
  - Ollama pull flow
  - Hugging Face browse/download/cancel flow

## 7. Troubleshooting

- Compile fails with missing controller/value:
  - verify required links and required parameters.
- Embedding options unavailable:
  - confirm provider configuration and model capability support.
- Vector store connection checks fail:
  - verify provider-specific required fields (local path vs endpoint URL).
- Hugging Face image input fails:
  - expected in current local generation path.

## 8. Practical Tips

- Keep workflows modular and test incrementally.
- Use profiles for different provider/runtime setups.
- Prefer explicit connections over implicit assumptions for reproducibility.
- For packaged desktop mode, always re-run `ParaGraph\start_on_windows.bat` before `release\tauri\build_with_tauri.bat` if runtimes were updated.
