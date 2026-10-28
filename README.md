<p align="center"><img src="app/client/public/favicon.svg" alt="" width="80"></p>

# ParaGraph LLM Workflow

**A local visual editor for building and running LLM workflows.**

Arrange prompts, model calls, data-processing nodes, and outputs on a canvas. ParaGraph runs as a web app on Windows: workflow graphs are kept in browser storage, and run history is stored in SQLite on the machine running the app.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE) [![Platform: Windows](https://img.shields.io/badge/Platform-Windows-0078D4?logo=windows&logoColor=white)](assets/docs/runtime/startup.md)

## What you can do

- Start from a workflow template or build a graph from the node catalog.
- Compile a graph before running it and review errors or warnings.
- Configure model providers and saved profiles in the app.
- Follow run status and execution events, including after reloading the page.
- Import and export workflow definitions as JSON; add custom node manifests.

## Run locally

The supported launcher is for 64-bit Windows. Install Git and use PowerShell. An internet connection is needed on first launch while the launcher prepares its portable runtimes and dependencies.

```powershell
git clone https://github.com/CTCycle/ParaGraph-LLM-workflow.git
Set-Location .\ParaGraph-LLM-workflow
.\start_on_windows.ps1
```

Choose **1. Launch application**. The launcher opens ParaGraph at <http://127.0.0.1:5002/>. Press **Ctrl+C** in the backend console to stop it.

## Build and run a workflow

1. Open **Nodes** and load a template, or add nodes to the **Workflow** canvas.
2. Fill in node settings and connect compatible ports.
3. Configure the required provider or runtime in **Configurations**.
4. Choose **Run Workflow**. ParaGraph compiles the graph first; fix any blocking diagnostics before execution.
5. Review the run status, events, and node outputs in the editor.

The editor is designed for desktop windows at least 1024 CSS pixels wide. Workflow graphs are stored in browser storage, so export important graphs before clearing browser data. Run records and events are stored in SQLite under `data/` by default.

## Configuration

If `settings/.env` is missing, the launcher creates it from [`settings/.env.example`](settings/.env.example). Set `PARAGRAPH_RESOURCES_DIR` there to move shared runtime data and the SQLite database from the default `data/` directory.

Provider credentials and saved profiles can be configured in the application. Keep machine-specific settings in the ignored `settings/.env` file.

## Documentation

- [Getting started](assets/docs/user/getting_started.md)
- [Workflow editor](assets/docs/user/workflow_editor.md)
- [Models and configurations](assets/docs/user/models_and_configurations.md)
- [Nodes and execution](assets/docs/user/nodes_and_execution.md)
- [Windows launcher](assets/docs/runtime/startup.md) and [runtime configuration](assets/docs/runtime/configuration.md)

## Contributing

Open an issue or pull request with a clear description of the change. Keep contributions focused and consistent with the project conventions.

## License

ParaGraph is licensed under the [MIT License](LICENSE).
