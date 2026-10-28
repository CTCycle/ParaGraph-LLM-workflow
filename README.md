<p align="center"><img src="app/client/public/favicon.svg" alt="" width="80"></p>

<h1 align="center">ParaGraph</h1>

<p align="center">A local visual editor for building and running LLM workflows.</p>

<p align="center">
  <a href="#run-locally">Run locally</a> ·
  <a href="#build-and-run-a-workflow">Build a workflow</a> ·
  <a href="#configuration">Configuration</a> ·
  <a href="#documentation">Documentation</a>
</p>

ParaGraph is a local web application for assembling prompts, model calls, data-processing nodes, and outputs into a workflow graph. The graph is kept in browser storage; run records and execution events are stored in SQLite on the computer running the app.

Start from a template or the node catalog, configure model providers and saved profiles, then compile and run the graph. The editor shows diagnostics, run status, events, and outputs. Workflow definitions can be imported or exported as JSON, and custom node manifests can be added to the catalog.

## Run locally

On 64-bit Windows, install Git and use PowerShell. An internet connection is needed on first launch while the launcher prepares its portable runtimes and dependencies.

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

The editor is designed for desktop windows at least 1024 CSS pixels wide. Export important graphs before clearing browser data.

## Configuration

If `settings/.env` is missing, the launcher creates it from [the example](settings/.env.example). Set `PARAGRAPH_RESOURCES_DIR` there to move shared runtime data and the SQLite database from the default `data/` directory. Provider credentials and saved profiles can be configured in the application; keep machine-specific settings in the ignored `settings/.env` file.

See [runtime configuration](assets/docs/runtime/configuration.md) for the available options.

## Development

The frontend uses React, TypeScript, and Vite. The FastAPI backend serves the built UI and API from one local origin, with SQLite as the default run-history store. The Windows launcher prepares the runtimes used for local development and launch.

See [startup](assets/docs/runtime/startup.md) for launcher options and manual frontend or backend commands.

## Documentation

- [Project documentation index](assets/docs/project_index.md)
- [Getting started](assets/docs/user/getting_started.md)
- [Workflow editor](assets/docs/user/workflow_editor.md)
- [Models and configurations](assets/docs/user/models_and_configurations.md)
- [Nodes and execution](assets/docs/user/nodes_and_execution.md)

## Contributing

Issues and pull requests are welcome. Describe the problem and keep changes focused and consistent with the project conventions.

## License

[MIT](LICENSE)
