# Getting Started
Last updated: 2026-07-11

## Overview
ParaGraph is a local-first application for building and executing LLM workflows through a visual node canvas.

## Main UI Areas
- Workflow at `/`
  - Build, connect, compile, run, and monitor workflows.
- Nodes at `/nodes`
  - Browse the node catalog, templates, and custom import flow.
- Models at `/models`
  - Explore Ollama and Hugging Face model catalogs.
- Configurations at `/config`
  - Manage runtime, provider, and saved profile settings.

## Starting The Application
Recommended on Windows:

```powershell
.\start_on_windows.ps1
```

The launcher prepares runtimes and dependencies, starts the backend and frontend, and opens the UI.

## Standard User Journey
1. Open Configurations and set required provider or runtime credentials.
2. Open Workflow and add nodes from the node library.
3. Connect compatible ports and controllers to build a valid graph.
4. Compile the workflow.
5. Start execution.
6. Monitor progress and outputs through run status and event updates.
