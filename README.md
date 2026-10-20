<h1 align="center"><img src="app/client/public/favicon.svg" alt="" width="44">&nbsp;ParaGraph LLM Workflow</h1>

Last updated: 2026-10-20

**Build and run LLM workflows with a local visual node editor.**

[![License](https://img.shields.io/github/license/CTCycle/ParaGraph-LLM-workflow?style=flat-square)](LICENSE) [![Release](https://img.shields.io/github/v/release/CTCycle/ParaGraph-LLM-workflow?style=flat-square)](https://github.com/CTCycle/ParaGraph-LLM-workflow/releases) [![CI](https://img.shields.io/github/actions/workflow/status/CTCycle/ParaGraph-LLM-workflow/ci.yml?branch=develop&style=flat-square)](https://github.com/CTCycle/ParaGraph-LLM-workflow/actions/workflows/ci.yml?query=branch%3Adevelop) [![Python 3.14](https://img.shields.io/badge/Python-3.14-3776AB?logo=python&logoColor=white&style=flat-square)](app/server/pyproject.toml) [![React](https://img.shields.io/badge/React-18-149ECA?logo=react&logoColor=white&style=flat-square)](app/client/package.json) [![Windows](https://img.shields.io/badge/platform-Windows-0078D4?logo=windows&logoColor=white&style=flat-square)](assets/docs/runtime/startup.md)

## Overview

ParaGraph is a local-first web application for building, compiling, running, and monitoring LLM workflows. The React frontend runs locally with a FastAPI backend. The active workflow graph is stored in browser storage and can be exchanged as JSON; run and execution records are stored in SQLite.

## Key Features

- Build graphs from the node catalog and templates, import custom node manifests, and connect compatible data and controller ports.
- Compile workflows before execution and review diagnostics for blocking errors and warnings.
- Monitor workflow runs and event history, reconnect to active runs after a page reload, and resume supported human-review steps.
- Configure local and hosted model providers, browse supported model catalogs, and save named configuration profiles.
- Import and export workflow definitions as JSON.

Provider execution depends on the configured endpoint, model, credentials, and external service.

## Technology Stack

- React frontend with TypeScript and Vite.
- FastAPI backend using the launcher-pinned Python 3.14.2 runtime.
- SQLite for application persistence and Node.js 22.12.0 for frontend tooling.
- Windows PowerShell launcher for runtime setup and local startup.

## Installation and Usage

On 64-bit Windows, install Git and use PowerShell. A modern browser is required; internet access is needed on first launch to download the portable runtimes and dependencies.

```powershell
git clone https://github.com/CTCycle/ParaGraph-LLM-workflow.git
Set-Location .\ParaGraph-LLM-workflow
.\start_on_windows.ps1
```

Choose **1. Launch application**. On first use, the launcher prepares its Python and Node.js runtimes, dependencies, SQLite database, and frontend build, then opens the app at <http://127.0.0.1:8002>. Backend API documentation is available at <http://127.0.0.1:5002/docs>.

To build a workflow, choose a template or add nodes from the catalog, connect compatible ports, select **Run Workflow**, and resolve any blocking diagnostics shown by the compiler. Runs report status and events in the editor; workflow graphs can be exported to JSON.

## Configuration

- The launcher creates `settings/.env` from [`settings/.env.example`](settings/.env.example) when it is missing. The default UI and backend addresses are `127.0.0.1:8002` and `127.0.0.1:5002`.
- Shared runtime data and the embedded SQLite database use `data/` by default. Set `PARAGRAPH_RESOURCES_DIR` in `settings/.env` to an absolute or repository-relative path to relocate them.
- Configure provider credentials in the application and keep machine-specific settings in the ignored `settings/.env` file.

## Documentation

- [Getting started](assets/docs/user/getting_started.md)
- [Workflow editor](assets/docs/user/workflow_editor.md)
- [Models and configurations](assets/docs/user/models_and_configurations.md)
- [Nodes and execution](assets/docs/user/nodes_and_execution.md)
- [Startup](assets/docs/runtime/startup.md) and [configuration](assets/docs/runtime/configuration.md)

## License

Licensed under the MIT License. See [LICENSE](LICENSE).
