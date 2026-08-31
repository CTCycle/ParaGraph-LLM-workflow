# System Overview
Last updated: 2026-08-31

## System Summary
ParaGraph is a local-first workflow platform composed of:

- A FastAPI backend in `app/server` for compile and execute APIs, node catalog management, provider integrations, configuration management, and execution event streaming.
- A React and TypeScript frontend in `app/client/src` for workflow editing, node and template browsing, model catalog operations, and runtime monitoring.

## Repository Structure
The repository contains source code plus generated and runtime-heavy folders. The structure below focuses on implementation and operational artifacts that matter for development.

```text
.
|- assets/
|  `- docs/
|- app/
|  |- client/
|  |  |- src/
|  |  |  |- App.tsx
|  |  |  |- main.tsx
|  |  |  |- index.css
|  |  |  |- app/services/          (typed API clients)
|  |  |  |- components/            (shared layout and UI)
|  |  |  |- pages/                 (Workflow, Nodes, Models, Configurations)
|  |  |  `- workflow/              (editor schema, hooks, and workflow-local UI)
|  |  |- package.json
|  |  `- vite.config.ts
|  |- server/
|  |  |- app.py
|  |  |- api/                      (FastAPI routers)
|  |  |- contracts/                (portable API, workflow, and node contracts)
|  |  |- services/                 (business logic)
|  |  |- repositories/
|  |  |  |- database/              (shared tabular persistence and engine adapters)
|  |  |  |- schemas/               (SQLAlchemy ORM models)
|  |  |  `- workflow/              (node manifests, database integrations, and chat history adapters)
|  |  `- common/                   (constants, security, logging)
|  `- resources/                   (db, logs, models, nodes, templates, artifacts)
|- settings/                       (.env and configurations.json)
|- runtimes/                       (portable Python, uv, Node, .venv, uv.lock)
|- start_on_windows.ps1            (Windows launcher and maintenance menu)
`- README.md
```

Backend contract and runtime ownership is intentionally split. `server/contracts`
contains portable validation and data models; configuration settings live in
`server/configurations`; runtime-only node handlers, provider metadata, and job
state live under `server/services`. Contracts do not import API, service,
repository, or SQLAlchemy implementation modules.

## Application Entry Points
- Backend app factory: `app/server/app.py` exposes `create_app` and `app`.
- Launcher-managed backend startup: `start_on_windows.ps1` runs `python -m uvicorn server.app:app`.
- Manual backend startup also targets `server.app:app` with `uvicorn`.
- Frontend entry: `app/client/src/main.tsx` bootstraps `App.tsx`.

## Runtime Topology
- In web mode, the frontend and backend run as separate processes with API traffic routed through the configured base path.
- Shared runtime artifacts live under `app/resources`, regardless of whether the app is started through the launcher or manually.
- The active workflow graph is browser-local and can be exchanged as JSON. The
  backend reads validated graph payloads for compilation and execution; it does
  not maintain a workflow CRUD store.
- Workflow runs are durable application-database records: the frontend can reload or reconnect to a run, recover queued or interrupted work after backend startup, and resume paused human-review steps with a resume token.
