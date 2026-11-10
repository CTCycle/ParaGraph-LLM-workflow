# Changelog

## [Unreleased]

## [1.0.1] - 2026-11-10

Patch release with launcher, configuration, node, and documentation updates since 1.0.0.

- The launcher now runs a single backend process that serves the built frontend, the `/api` path, and the execution WebSocket from one origin; the Vite preview server is no longer started.
- `start_on_windows.bat` launches the app (PowerShell 7 required); `setup_and_maintenance.ps1` provides the maintenance menu, with safer cleanup and uninstall and launch timing reporting.
- Provider settings save automatically and can be stored as named profiles; the SQLite database can be switched from the Configurations page.
- CORS policy and runtime settings are configurable through `settings/.env`.
- Local text-safety, text-transformation, HTML-to-text, retrieval, and vector-store nodes were validated and several node contract defects fixed.
- Custom node import validation is stricter and its UI feedback clearer.
- README refreshed with screenshots; known limitations are unchanged and tracked in the [project status ledger](assets/docs/project_status_ledger.md).

## [1.0.0] - 2026-10-18

First stable local web application release.

- Includes the visual workflow editor, node catalog and templates, deterministic local execution, run history, SQLite persistence, and Windows launcher.
- Documents clone, configuration, startup, usage, and troubleshooting for a local Windows setup.
- Corrects the manual backend startup instructions and aligns frontend package metadata to version 1.0.0.
- Updates vulnerable frontend dependencies and records the exact dependency tree in the lockfile.
- Provider execution and several external node families remain dependent on configured services and have limited validation; see the [project status ledger](assets/docs/project_status_ledger.md).
