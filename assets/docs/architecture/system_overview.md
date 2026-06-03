# System Overview
Last updated: 2026-06-02

## System Summary
ParaGraph is a local-first workflow platform composed of:

- A FastAPI backend in `app/server` for compile and execute APIs, node catalog management, provider integrations, configuration management, and execution event streaming.
- A React and TypeScript frontend in `app/client/src` for workflow editing, node and template browsing, model catalog operations, and runtime monitoring.
- An optional Tauri desktop wrapper in `app/client/src-tauri` that launches the backend process and loads the web UI in a desktop window.

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
|  |  |- src-tauri/
|  |  |  |- src/main.rs
|  |  |  |- tauri.conf.json
|  |  |  `- Cargo.toml
|  |  |- package.json
|  |  `- vite.config.ts
|  |- server/
|  |  |- app.py
|  |  |- api/                      (FastAPI routers)
|  |  |- configurations/           (env and runtime config loading)
|  |  |- domain/                   (Pydantic and domain models)
|  |  |- services/                 (business logic)
|  |  |- repositories/
|  |  |  |- database/              (shared tabular persistence and engine adapters)
|  |  |  |- schemas/               (SQLAlchemy ORM models)
|  |  |  `- workflow/              (workflow JSON and runtime repositories)
|  |  `- common/                   (constants, security, logging)
|  `- resources/                   (db, logs, models, nodes, workflows, artifacts)
|- settings/                       (.env and configurations.json)
|- release/
|  |- tauri/                       (desktop build scripts)
|  `- windows/                     (packaged artifacts)
|- runtimes/                       (portable Python, uv, Node, .venv, uv.lock)
`- README.md
```

## Application Entry Points
- Backend app factory: `app/server/app.py` exposes `create_app` and `app`.
- Launcher-managed backend startup: `start_on_windows.bat` runs `python -m uvicorn server.app:app`.
- Manual backend startup also targets `server.app:app` with `uvicorn`.
- Frontend entry: `app/client/src/main.tsx` bootstraps `App.tsx`.
- Desktop entry: `app/client/src-tauri/src/main.rs` starts the backend, waits for readiness, and opens the UI URL.

## Runtime Topology
- In web mode, the frontend and backend run as separate processes with API traffic routed through the configured base path.
- In desktop mode, the Rust launcher hosts the backend locally and then points the embedded webview to the same local UI.
- Shared runtime artifacts live under `app/resources`, regardless of whether the app is started through the launcher, manually, or through Tauri packaging.
