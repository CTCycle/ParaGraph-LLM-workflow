# ParaGraph LLM Workflow

Last updated: 2026-10-18

[![Release](https://img.shields.io/github/v/release/CTCycle/ParaGraph-LLM-workflow?display_name=tag)](https://github.com/CTCycle/ParaGraph-LLM-workflow/releases)
[![Python](https://img.shields.io/badge/Python-%3E%3D3.14-blue)](https://www.python.org/)
[![Node.js](https://img.shields.io/badge/Node.js-22.12.0-339933?logo=node.js&logoColor=white)](https://nodejs.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![CI](https://github.com/CTCycle/ParaGraph-LLM-workflow/actions/workflows/ci.yml/badge.svg?branch=develop)](https://github.com/CTCycle/ParaGraph-LLM-workflow/actions/workflows/ci.yml?query=branch%3Adevelop)

Version **1.0.0** is a local-first web application for designing, running, and monitoring LLM workflows on a visual node canvas. Its React frontend and FastAPI backend run on your computer. On Windows, the project launcher prepares the portable runtimes and starts both services.

## What it does

- Build workflows by placing nodes on the canvas and connecting compatible data and controller ports. The editor compiles a graph before execution and shows diagnostics for blocking errors and warnings.
- Start from a workflow template, browse the node catalog, or import custom node manifests. Workflows can be imported from and exported to JSON.
- Run workflows and monitor their status and event history. Run state is stored in the local SQLite database; active runs can be reconnected to after a page reload, and paused human-review steps can be resumed.
- Compose document and retrieval flows from available input, processing, embedding, vector storage, retrieval, database, control, and output nodes.
- Configure local and hosted model providers, browse model catalogs, and manage named configuration profiles.

The active workflow graph is held in browser storage and can be exchanged as JSON. The backend stores run records and execution state in SQLite. Provider and external-service behavior depends on the configured service, model, credentials, and node integration.

## Prerequisites

- 64-bit Windows with PowerShell.
- Git to clone the repository.
- A modern browser. The desktop layout needs a browser window at least 1024 CSS pixels wide.
- Internet access on first launch so the launcher can download portable runtimes and dependencies.

Python and Node.js do not need to be installed separately; the launcher prepares project-local copies.

## Install and launch

In PowerShell:

```powershell
git clone https://github.com/CTCycle/ParaGraph-LLM-workflow.git
Set-Location ParaGraph-LLM-workflow
.\start_on_windows.ps1
```

Choose **1. Launch application**. On first use, the launcher creates `settings/.env` from the tracked example, prepares runtimes and dependencies, checks and applies pending database migrations, builds the frontend when needed, and opens the app at <http://127.0.0.1:8002>. The backend API documentation is at <http://127.0.0.1:5002/docs>.

To install development tools, choose **3. Install or update dependencies**, then select **1. Development**. The launcher keeps installed dependencies between starts. To stop the backend and frontend, reopen the launcher and choose **2. Kill all app processes**.

## Build and run a workflow

1. Open **Nodes** and load a template, or open **Workflow** and add nodes from the catalog.
2. Connect compatible data ports and any required controller ports. Controller connections explicitly attach providers, memory, or stores to nodes that use them.
3. Select **Run Workflow**. The editor compiles the graph automatically before starting a run; resolve any blocking diagnostics first.
4. Follow run status and event updates in the editor. You can cancel a run, reconnect to an active run after reloading, and resume a paused human-review step when its resume token is available.
5. Export the workflow as JSON when you want to save or share the graph definition.

## Models and providers

The Configurations page supports provider settings for Ollama, OpenAI, Gemini, Claude, DeepSeek, Hugging Face, LM Studio, and llama.cpp. Local OpenAI-compatible endpoints can use optional API keys and default chat or embedding model metadata. Named configuration profiles let you save and load provider settings.

The Models page can browse and pull Ollama models and search and download Hugging Face models. Workflows can also use LM Studio or llama.cpp through locally exposed OpenAI-compatible `/v1` endpoints. Cloud providers need their credentials; local providers need an available endpoint and model.

Catalog availability does not guarantee complete end-to-end validation. Provider execution and external database or vector-store integrations have remaining validation limits; see the [project status ledger](assets/docs/project_status_ledger.md) for the current scope.

## Configuration and data

The launcher copies [`settings/.env.example`](settings/.env.example) to `settings/.env` when the local file does not exist. The defaults bind the UI and API to `127.0.0.1` on ports `8002` and `5002`. Set `UI_PORT` or `FASTAPI_PORT` in `settings/.env` if a port is occupied. Keep `VITE_API_BASE_URL` as a relative path such as `/api` so the frontend uses the local backend.

Shared runtime data, including the application database, logs, node assets, workflow templates, artifacts, and model assets, is stored under `data` by default. Set `PARAGRAPH_RESOURCES_DIR` in `settings/.env` to an absolute or repository-relative path to move the shared resource directory. The application database uses embedded SQLite; database workflow nodes may connect to separately configured databases.

Configure provider credentials in the application. Keep machine-specific values in the ignored `settings/.env`, do not commit that file, and never put real credentials in `.env.example`.

## Scope and limitations

ParaGraph is a local web application. This repository does not produce an installer, standalone executable, or container image. The Windows launcher is the recommended way to bootstrap and run the app; manual backend and frontend commands are available in the [startup guide](assets/docs/runtime/startup.md).

Provider execution and external node families have limited validation coverage. A catalog entry or configuration screen should not be read as proof that every provider or external integration has passed an end-to-end workflow campaign. The status ledger records validated scopes, partial coverage, and open validation work.

## Troubleshooting

- First launch can take several minutes while runtimes and dependencies are installed. Choose launcher option **3** to repair or update dependencies.
- If a configured port is occupied, the launcher shows the owning process and asks before stopping it. Decline and change the corresponding port in `settings/.env` if you need to keep that process running.
- Startup applies pending SQLite migrations. If migration or data errors occur, preserve the database and follow [Troubleshooting and Data](assets/docs/user/troubleshooting_and_data.md) before using any data-removal action.
- For direct backend or frontend startup commands, see the [Startup guide](assets/docs/runtime/startup.md). Frontend lint, build, unit, and backend test guidance is in [Testing and Quality](assets/docs/coding/testing_and_quality.md).

## Documentation

- [Getting Started](assets/docs/user/getting_started.md): application areas and the standard user journey.
- [Workflow Editor](assets/docs/user/workflow_editor.md): graph editing, connections, compilation, and Chat nodes.
- [Models and Configurations](assets/docs/user/models_and_configurations.md): provider setup, profiles, and model catalogs.
- [Nodes and Execution](assets/docs/user/nodes_and_execution.md): node catalog, run status, recovery, and human review.
- [Project documentation index](assets/docs/project_index.md): architecture, runtime, API, node, and user guides.
- [Project status ledger](assets/docs/project_status_ledger.md): current validation evidence, limitations, and open work.
- [CHANGELOG](CHANGELOG.md): release history.

## License

This project is licensed under the [MIT License](LICENSE).
