# Getting Started
Last updated: 2026-10-22

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

The launcher prepares runtimes and dependencies, starts one backend console that serves the UI and API, and opens the app at the backend URL. Stop it with Ctrl+C in that console.

## Standard User Journey
1. Open Configurations and set required provider or runtime credentials.
2. Open Nodes and use a template when you want a known-good starting shape, or open Workflow and add nodes from the node library.
3. Connect compatible data ports and controller ports to build a valid graph.
4. Choose Run Workflow. The editor compiles the graph before starting execution.
5. Fix blocking compilation diagnostics when they appear.
6. Monitor progress and outputs through run status and event updates.

## Optional In-App Guidance
The first blank workflow can show a compact getting-started callout. `Show me` opens a four-step editor walkthrough covering the node library, canvas, connections, and Run Workflow. The walkthrough can be skipped, closed, or replayed from the top-bar Help button.

Configurations may show one short setup tip the first time a provider setup is loaded. Chat also has a manual Conversation help popover when its history wiring needs explanation. These hints are optional and are remembered per browser; newer guidance versions can become eligible again without resetting the workflow.
