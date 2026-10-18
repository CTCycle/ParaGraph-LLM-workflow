# ParaGraph LLM Workflow
[![Release](https://img.shields.io/github/v/release/CTCycle/ParaGraph-LLM-workflow?display_name=tag)](https://github.com/CTCycle/ParaGraph-LLM-workflow/releases)
[![Python](https://img.shields.io/badge/Python-%3E%3D3.14-blue)](https://www.python.org/)
[![Node.js](https://img.shields.io/badge/Node.js-22.12.0-339933?logo=node.js&logoColor=white)](https://nodejs.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![CI](https://github.com/CTCycle/ParaGraph-LLM-workflow/actions/workflows/ci.yml/badge.svg?branch=develop)](https://github.com/CTCycle/ParaGraph-LLM-workflow/actions/workflows/ci.yml?query=branch%3Adevelop)

**Version 1.0.0** is a local-first web application for building, running, and monitoring LLM workflows on a visual canvas. The Windows launcher manages a local FastAPI backend and React web interface. No installer or container is required. The desktop layout needs a browser window at least 1024 CSS pixels wide.

## Prerequisites

- 64-bit Windows with PowerShell.
- Git to clone the repository.
- Internet access for the first launch to download the portable runtimes and dependencies.
- A modern browser. Python and Node.js do not need to be installed separately; the launcher prepares local copies.

## Install and launch

In PowerShell:

```powershell
git clone https://github.com/CTCycle/ParaGraph-LLM-workflow.git
Set-Location ParaGraph-LLM-workflow
.\start_on_windows.ps1
```

Choose **1. Launch application**. On first use, the launcher creates `settings/.env` from the tracked example, prepares missing runtimes and dependencies, checks the database migrations, builds the frontend when needed, and opens the application at <http://127.0.0.1:8002>. The backend API documentation is at <http://127.0.0.1:5002/docs>.

To install development tools and run project checks, choose **3. Install or update dependencies**, then select **1. Development**. Choose **2. Standard** for application runtime dependencies only. The launcher retains installed dependencies between starts. Reopen it and choose **2. Kill all app processes** to stop the application.

## Configuration and data

The launcher copies [`settings/.env.example`](settings/.env.example) to `settings/.env` when the local file is missing. The default web and API addresses are `127.0.0.1:8002` and `127.0.0.1:5002`; set `UI_PORT` or `FASTAPI_PORT` in `settings/.env` if those ports are occupied. Keep `VITE_API_BASE_URL` as a relative path such as `/api` so the frontend uses the local backend.

Shared data, including the embedded SQLite database, logs, workflow templates, and runtime assets, is stored under `data` by default. Set `PARAGRAPH_RESOURCES_DIR` to an absolute or repository-relative path in `settings/.env` to move it. Provider credentials are configured in the application; do not put real credentials in `.env.example` or commit `settings/.env`.

## Use the application

- Build a node graph, connect compatible ports, and compile it to review diagnostics.
- Run deterministic local workflows and follow status, outputs, and event history.
- Browse templates and nodes, import custom node manifests, and manage provider settings.
- Create retrieval workflows to load, split, embed, store, search, rank, and answer questions.

See [Getting Started](assets/docs/user/getting_started.md) and the [Workflow Editor guide](assets/docs/user/workflow_editor.md) for the standard user journey. Provider execution requires a configured local provider or service and its own credentials.

## Troubleshooting and development

- A first launch can take several minutes while runtimes and dependencies are installed. Choose launcher option **3** to repair the development or standard install.
- If a configured port is occupied, the launcher shows the owning process and asks whether to stop it. Decline and choose another port in `settings/.env` if you need to keep that process running.
- Startup applies pending SQLite migrations. For schema or data errors, see [Troubleshooting and Data](assets/docs/user/troubleshooting_and_data.md) before using any data-removal action.
- For direct backend and frontend development commands, see the [Startup guide](assets/docs/runtime/startup.md). The frontend unit, lint, and build commands are listed in [Testing and Quality](assets/docs/coding/testing_and_quality.md).

The [documentation index](assets/docs/project_index.md) maps the full project guides. Current validation scope and known limitations are in the [status ledger](assets/docs/project_status_ledger.md). Release history is in [CHANGELOG.md](CHANGELOG.md).

## License

This project is licensed under the [MIT License](LICENSE).
