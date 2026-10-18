# ParaGraph LLM Workflow
[![Release](https://img.shields.io/github/v/release/CTCycle/ParaGraph-LLM-workflow?display_name=tag)](https://github.com/CTCycle/ParaGraph-LLM-workflow/releases)
[![Python](https://img.shields.io/badge/Python-%3E%3D3.14-blue)](https://www.python.org/)
[![Node.js](https://img.shields.io/badge/Node.js-22.12.0-339933?logo=node.js&logoColor=white)](https://nodejs.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![CI](https://github.com/CTCycle/ParaGraph-LLM-workflow/actions/workflows/ci.yml/badge.svg?branch=develop)](https://github.com/CTCycle/ParaGraph-LLM-workflow/actions/workflows/ci.yml?query=branch%3Adevelop)

ParaGraph is a local-first application for building, running, and monitoring LLM workflows on a visual canvas. Its supported Windows launcher starts a FastAPI backend and a React browser interface. The desktop layout requires a browser window at least 1024 CSS pixels wide.

## Workflows

- Build a graph by connecting nodes, then compile it to see diagnostics before running.
- Follow execution status, outputs, and event history.
- Browse node templates, import custom node manifests, and manage provider models and configuration profiles.
- Create retrieval workflows that load, split, embed, store, search, rank, and answer questions.

## Start on Windows

Run the launcher from the repository root:

    .\start_on_windows.ps1

It prepares or repairs the local runtimes, initializes the database, starts the backend and frontend, and opens the interface. The first launch may take longer while dependencies are prepared. See the [startup guide](assets/docs/runtime/startup.md) for launcher actions and manual startup commands.

## Documentation

The [project documentation index](assets/docs/project_index.md) maps the full documentation structure.

User guides:

- [Getting started](assets/docs/user/getting_started.md)
- [Workflow editor](assets/docs/user/workflow_editor.md)
- [Models and configurations](assets/docs/user/models_and_configurations.md)
- [Nodes and execution](assets/docs/user/nodes_and_execution.md)
- [Troubleshooting and data](assets/docs/user/troubleshooting_and_data.md)

Project references:

- [Status ledger](assets/docs/project_status_ledger.md) — current component status, evidence, known issues, and validation gaps.
- [Validation strategy](assets/docs/validation/strategy.md) — campaign tiers and evidence rules.
- [Testing and quality](assets/docs/coding/testing_and_quality.md) — tools, commands, and repository conventions.

## Data

Shared runtime data is stored under the repository's data directory by default. Set PARAGRAPH_RESOURCES_DIR in settings/.env to use an absolute or repository-relative location instead. Data includes the application database, logs, workflow and node assets, downloaded models, and runtime artifacts. The launcher provides a confirmed Remove All Data action; see the [troubleshooting and data guide](assets/docs/user/troubleshooting_and_data.md) before using it.

## License

This project is licensed under the [MIT License](LICENSE).
