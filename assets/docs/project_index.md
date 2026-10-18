# Project Overview
Last updated: 2026-10-18

## Purpose
This is the entry point for the ParaGraph documentation tree. Use it to find the owning concept document and keep related knowledge there.

## How To Navigate
1. Choose the topic that matches the behavior or task.
2. Read the narrowest linked document first.
3. Follow adjacent links only when the work crosses concepts.
4. Update this index when documents are added, removed, moved, or renamed.

## Documentation Ontology

### Root
- [Project status ledger](project_status_ledger.md) — canonical current component status, durable validation outcomes, active issues, and validation debt.

### Architecture
- [System overview](architecture/system_overview.md) — product structure, repository layout, entry points, and runtime topology.
- [Backend API](architecture/backend_api.md) — HTTP and WebSocket surface and contract boundaries.
- [Execution and data flow](architecture/execution_and_data_flow.md) — backend layers, module responsibilities, and execution lifecycle.
- [Persistence](architecture/persistence.md) — file storage, database responsibilities, and runtime stores.

### Coding
- [Python](coding/python.md) — Python runtime, typing, validation, and async conventions.
- [TypeScript](coding/typescript.md) — TypeScript, React, state, styling, and frontend structure.
- [Testing and quality](coding/testing_and_quality.md) — tooling, commands, and quality expectations.

### Runtime
- [Modes](runtime/modes.md) — supported runtime modes and operational differences.
- [Startup](runtime/startup.md) — Windows launcher and manual startup procedures.
- [Configuration](runtime/configuration.md) — environment keys, runtime settings, and cross-runtime communication.
- [Deployment](runtime/deployment.md) — supported local operation model, limitations, and generated runtime outputs.

### Validation
- [Validation strategy](validation/strategy.md) — campaign tiers, slice conventions, and evidence rules. Current outcomes belong in the status ledger.

### UI
- [Design tokens](ui/design_tokens.md) — typography, spacing, radius, color, and theme tokens.
- [Components and patterns](ui/components_and_patterns.md) — navigation, route structure, and reusable interactions.
- [Experience](ui/experience.md) — responsiveness, accessibility, and design principles.

### Nodes
- [Catalog and manifests](nodes/catalog_and_manifests.md) — catalog sources, category model, manifests, and compatibility.
- [Processing and retrieval](nodes/processing_and_retrieval.md) — structured data, retrieval, web requests, control, tokenizer, metadata, and vector search.
- [Database and tools](nodes/database_and_tools.md) — database nodes, tool collection and call nodes, and runtime contracts.
- [Import and integration](nodes/import_and_integration.md) — custom node import, workflow integration, and connectivity checks.

### User
- [Getting started](user/getting_started.md) — product overview, main UI areas, startup, and standard journey.
- [Workflow editor](user/workflow_editor.md) — graph editing, compilation, and building workflows.
- [Models and configurations](user/models_and_configurations.md) — saved profiles and provider operations.
- [Nodes and execution](user/nodes_and_execution.md) — node usage, execution monitoring, and runtime statuses.
- [Troubleshooting and data](user/troubleshooting_and_data.md) — common causes and runtime data locations.

## Reading Order
For current-state, validation, or revalidation work, read the [status ledger](project_status_ledger.md) first, then the owning concept document.

## Documentation Rules
- Keep implementation behavior in its owning concept document; keep reproducible checks in tracked test suites.
- The status ledger is the only canonical record of durable validation outcomes. Do not add standalone QA reports.
- Record test revision, date, scope, result, and remaining limits in the ledger. Link to tracked tests and CI runs where they provide the evidence.
- Keep transient screenshots, logs, databases, and run exports in ignored scratch directories such as assets/QA or runtimes/cache; they are not durable evidence.
- Treat source inspection or the existence of a test as insufficient proof of a validated behavior.
- Add a Last updated: YYYY-MM-DD line to each modified document.

## Environment Rules
- Windows is the default operating environment.
- Document both PowerShell and CMD variants when commands differ.
- Keep runtime guidance aligned with start_on_windows.ps1.
