# USER_MANUAL

Last updated: 2026-04-24

## Overview

ParaGraph is a local-first application for building and executing LLM workflows through a visual node canvas.

Primary UI areas:

- Workflow (`/`): build, connect, compile, run, and monitor workflows.
- Nodes (`/nodes`): browse node catalog, templates, and import custom nodes.
- Models (`/models`): explore Ollama and Hugging Face model catalogs.
- Configurations (`/config`): manage runtime/provider settings and saved profiles.

## Starting the Application

Recommended (Windows):

```bat
ParaGraph\start_on_windows.bat
```

This launcher prepares runtimes/dependencies, starts backend + frontend, and opens the UI.

## Main User Flow

1. Open `Configurations` and set required provider/runtime credentials.
2. Open `Workflow` and add nodes from the node library.
3. Connect node ports/controllers to build a valid execution graph.
4. Compile the workflow.
5. Start execution.
6. Monitor progress and outputs via run status and event updates.

## Workflow Editor Basics

- Drag nodes from the left node tree to the canvas.
- Connect output handles to compatible input handles.
- Use context menu actions (for example: clone, skip, set global, remove).
- Use import/export controls for workflow JSON where needed.
- Use compile diagnostics to fix graph errors before running.

## Configurations Page

Manage:

- Ollama base URL and connectivity checks.
- Cloud provider keys (OpenAI/Gemini/Claude as configured in UI).
- Hugging Face key.
- Named configuration profiles (save/load).

Configuration APIs are backed by `/configurations` and `/configurations/profiles` endpoints.

## Models Page

Ollama section:

- Browse available library models.
- Pull missing models into local runtime.

Hugging Face section:

- Search/filter/sort catalog.
- Start, monitor, or cancel model downloads.
- Open model cards in browser.

## Nodes Page

- Filter node catalog by category and search query.
- Review node input/output/parameter summaries.
- Load predefined workflow templates into the workflow editor.
- Import custom manifest JSON.

## Execution Monitoring

Execution uses:

- Polling endpoint: `GET /executions/{run_id}`
- Event history endpoint: `GET /executions/{run_id}/events`
- WebSocket stream: `WS /executions/ws/runs/{run_id}`

Common statuses include queued, running, completed, failed, and cancelled.

## Troubleshooting

- If startup fails, rerun `ParaGraph\start_on_windows.bat` and check console output.
- If APIs are unreachable, verify configured host/port values in `ParaGraph/settings/.env`.
- If model operations fail, verify provider credentials and network reachability.
- If compile fails, inspect diagnostics and fix missing inputs/controllers or type mismatches.

## Data Location

Runtime data is stored under `ParaGraph/resources`, including:

- Local database
- Logs
- Workflow persistence
- Node assets/plugins
- Downloaded model artifacts
- Browser upload artifacts
