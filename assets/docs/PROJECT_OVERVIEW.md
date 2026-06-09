# Project Overview
Last updated: 2026-06-02

## Purpose
This file is the root index for `assets/docs`. Read it first, then open only the smallest leaf file that matches the task.

## How To Navigate
1. Start with this file only.
2. Pick the topic branch that matches the question or change.
3. Open the narrowest leaf file in that branch.
4. Open adjacent files only when the task clearly crosses topic boundaries.
5. Return here whenever you need to jump to another topic.

## Naming Rules
- All files and folders under `assets/docs` use lower-case names.
- Root-level files are reserved for entry points and top-level guidance.
- Topic folders group related leaf files by subject so large mixed-purpose markdown files are avoided.

## Documentation Ontology
### Root
- `project_index.md`
  - Entry point, navigation rules, and complete index for the documentation tree.

### Architecture
- `architecture/system_overview.md`
  - Product structure, repository layout, entry points, and top-level runtime topology.
- `architecture/backend_api.md`
  - HTTP and WebSocket surface grouped by functional area.
- `architecture/execution_and_data_flow.md`
  - Layered backend flow, key module responsibilities, and async/background execution behavior.
- `architecture/persistence.md`
  - File-based persistence, database responsibilities, and in-memory runtime stores.

### Coding
- `coding/python.md`
  - Python runtime, typing, validation, async, and structural expectations.
- `coding/typescript.md`
  - TypeScript, React, state, styling, and frontend structure expectations.
- `coding/testing_and_quality.md`
  - Tooling, testing, quality gates, and cross-language change expectations.

### Runtime
- `runtime/modes.md`
  - Supported runtime modes and operational differences.
- `runtime/startup.md`
  - Windows startup procedures for launcher, backend, frontend, and desktop packaging flows.
- `runtime/configuration.md`
  - Shared environment keys, runtime settings, and cross-runtime communication rules.
- `runtime/deployment.md`
  - Packaging targets, artifact locations, limitations, and runtime-heavy generated outputs.

### UI
- `ui/design_tokens.md`
  - Typography, spacing, radius, color, and theme tokens.
- `ui/components_and_patterns.md`
  - Navigation, surfaces, route structure, and reusable interaction patterns.
- `ui/experience.md`
  - UX rules, responsiveness, accessibility, and design principles.

### Nodes
- `nodes/catalog_and_manifests.md`
  - Node catalog sources, category model, manifest structure, and compatibility constraints.
- `nodes/processing_and_retrieval.md`
  - Structured JSON, processing, retrieval, RAG, web API, control, tokenizer, metadata, and vector search behavior.
- `nodes/database_and_tools.md`
  - Database nodes, tool collection and tool call nodes, and runtime contracts around them.
- `nodes/import_and_integration.md`
  - Custom node import flow, workflow integration, connectivity checks, and operational notes.

### User
- `user/getting_started.md`
  - Product overview, main UI areas, startup entry point, and standard user journey.
- `user/workflow_editor.md`
  - Workflow editor basics, compile flow, and graph-building expectations.
- `user/models_and_configurations.md`
  - Configurations and models page behavior, saved profiles, and provider operations.
- `user/nodes_and_execution.md`
  - Nodes page usage, execution monitoring surfaces, and common runtime statuses.
- `user/troubleshooting_and_data.md`
  - Troubleshooting guidance and runtime data locations.

## Reading Order
1. Read this root index.
2. Open one leaf file in the relevant topic branch.
3. Expand only when the task crosses branch boundaries.
4. Update this index whenever files are added, removed, moved, or renamed.

## Context Rules
- Read documentation only when required by the current task.
- Prefer leaf files over broad branch reads.
- Keep all affected docs updated when implementation changes alter behavior.
- Always include a `Last updated: YYYY-MM-DD` line when modifying a document.
- Pre-select files by user intent, folder structure, and target subsystem before reading deeply.

## Environment Rules
- Windows is the default operating environment for this project.
- Document both PowerShell and CMD variants when commands differ.
- Keep runtime guidance aligned with `start_on_windows.bat` and `release/tauri/build_with_tauri.bat`.
- Update environment guidance when Windows-specific constraints or workarounds change.
