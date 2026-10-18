# ParaGraph LLM Workflow
[![Release](https://img.shields.io/github/v/release/CTCycle/ParaGraph-LLM-workflow?display_name=tag)](https://github.com/CTCycle/ParaGraph-LLM-workflow/releases)
[![Python](https://img.shields.io/badge/Python-%3E%3D3.14-blue)](https://www.python.org/)
[![Node.js](https://img.shields.io/badge/Node.js-22.12.0-339933?logo=node.js&logoColor=white)](https://nodejs.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![CI](https://github.com/CTCycle/ParaGraph-LLM-workflow/actions/workflows/ci.yml/badge.svg?branch=develop)](https://github.com/CTCycle/ParaGraph-LLM-workflow/actions/workflows/ci.yml?query=branch%3Adevelop)

ParaGraph is a local application for planning, running, and observing LLM workflows in a visual way. Instead of writing everything from scratch, you connect building blocks on a canvas, define how information moves through them, run the workflow, and watch what happens as it executes.

It is a local web application for Windows, optimized for a desktop or laptop browser window at least 1024 CSS pixels wide. Narrower windows show a minimum-window-size notice instead of a mobile layout.

## What You Can Do

- create workflows on a visual canvas instead of in a text-only editor
- connect nodes into a clear sequence of steps and check the workflow before running it
- launch an execution and follow its progress, outputs, and event history
- manage available nodes, models, providers, and saved configuration profiles
- build retrieval-style workflows: load documents, split content, create embeddings, store vectors, search, rank, and generate an answer

## Main Screens

- **Workflow** — the main workspace: place nodes, connect them, adjust settings, compile the graph, run it, and monitor progress.
- **Nodes** — browse the node catalog and templates, search and filter by category, and import custom node manifests.
- **Models** — browse Ollama and Hugging Face catalogs, download models, track download progress, and open model cards.
- **Configurations** — set provider access details, verify local model connectivity, and save or reuse named profiles.

## Getting Started

On Windows, run:

```powershell
.\start_on_windows.ps1
```

The launcher prepares its portable runtimes and dependencies, initializes the database, starts the backend and frontend, and opens the interface. The first launch can take longer because it sets up the local runtime; later launches are usually much faster. See the [Startup Guide](assets/docs/runtime/startup.md) for the full launcher menu and manual startup commands.

A typical session:

1. Open **Configurations** and enter the provider or runtime details you need.
2. Open **Workflow** (or load a template from **Nodes**) and place the nodes you want.
3. Connect the nodes so the workflow has a clear path from start to finish.
4. Compile the workflow and fix anything the compiler points out.
5. Start the run and watch the execution status; inspect the output as it arrives.

## Documentation

User guides:

- [Getting Started](assets/docs/user/getting_started.md)
- [Workflow Editor](assets/docs/user/workflow_editor.md)
- [Models And Configurations](assets/docs/user/models_and_configurations.md)
- [Nodes And Execution](assets/docs/user/nodes_and_execution.md)
- [Troubleshooting And Data](assets/docs/user/troubleshooting_and_data.md)

Project documentation:

- [Project Overview](assets/docs/project_index.md) — entry point for the documentation tree.
- [Project Status Ledger](assets/docs/project_status_ledger.md) — current component status, known issues, and validation outcomes.
- [Validation Strategy](assets/docs/validation/strategy.md) — how validation is planned and recorded.
- [Testing And Quality](assets/docs/coding/testing_and_quality.md) — tooling and quality expectations.

## Data And Files

The app stores its local runtime data under `data` by default. Set `PARAGRAPH_RESOURCES_DIR` in `settings/.env` to use another absolute or repository-relative location. Stored data includes logs, workflow data, downloaded models and related assets, local database files, and runtime artifacts. Launcher option 11 removes user data while preserving application files and settings.

## Troubleshooting

If something does not work as expected:

- try starting the app again with `start_on_windows.ps1` and read the console output
- check that the host, port, and provider values in `settings/.env` are correct
- make sure the model or provider you need is available
- review the compile diagnostics before running a workflow

See [Troubleshooting And Data](assets/docs/user/troubleshooting_and_data.md) for common causes and data locations.

## License

This project is licensed under the [MIT License](LICENSE).
