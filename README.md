# Generic Repository Bootstrap Template

This folder is a topic-agnostic bootstrap distilled from the current repository.  
It preserves the same core strategy:

- Monorepo layout with `APP/` as the main package.
- Client/server separation (`APP/client` and `APP/server`).
- Dual runtime modes: local launcher and cloud Docker deployment.
- Environment-driven configuration (`APP/settings/.env` + profile examples).
- Embedded SQLite or external PostgreSQL database wiring.
- Job-based backend workflows with polling endpoints.
- Matching test/tooling layout (`tests/unit`, `tests/e2e`, `tests/backend/verification`).

## 1. Structure

```text
template/
- APP/
  - client/                 # React + Vite + TypeScript frontend
  - server/                 # FastAPI backend (routes/services/repositories)
  - settings/               # Active env + local/cloud env templates
  - scripts/                # Utility scripts (database initialization)
  - resources/              # Runtime artifacts (logs, checkpoints, models, etc.)
  - start_on_windows.bat    # Local launcher strategy
  - setup_and_maintenance.bat
- docker/
  - backend.Dockerfile
  - frontend.Dockerfile
  - nginx/default.conf
- tests/
  - unit/
  - e2e/
  - backend/verification/
- docker-compose.yml
- pyproject.toml
- .gitignore
- .dockerignore
```

## 2. Architecture and Layering

- `APP/server/app.py` composes FastAPI and registers route modules.
- `APP/server/routes/` exposes HTTP endpoints and orchestrates services.
- `APP/server/services/` contains workflow/service logic (including job orchestration).
- `APP/server/repositories/` contains persistence adapters (SQLite/PostgreSQL), schema definitions, and data serialization helpers.
- `APP/server/configurations/` loads JSON + env settings and applies runtime overrides.
- `APP/client/src/pages/` holds route pages.
- `APP/client/src/components/` holds reusable UI blocks.
- `APP/client/src/services/` holds API client functions and polling helpers.
- `APP/client/src/AppStateContext.tsx` centralizes page-level state.

## 3. Naming and Conventions

- Keep framework-neutral, use-case-neutral names in shared layers:
  - `Dataset*`, `Training*`, `Inference*`, `Validation*` can be renamed to your domain workflows if needed.
- Place domain logic only in:
  - backend services (`APP/server/services`)
  - backend route orchestration (`APP/server/routes`)
  - frontend pages/components (`APP/client/src/pages`, `APP/client/src/components`)
- Keep persistence and runtime plumbing generic and reusable.

## 4. Local Run Strategy

1. Copy local profile to active env:
   - `copy /Y APP\settings\.env.local.example APP\settings\.env`
2. Launch:
   - `APP\start_on_windows.bat`
3. Optional tests:
   - `tests\run_tests.bat`

The launcher mirrors the repository pattern:
- reads `APP/settings/.env`
- syncs backend deps with `uv`
- builds frontend with `npm`
- starts backend (`uvicorn`) and frontend preview server

## 5. Cloud Deployment Strategy

1. Copy cloud profile:
   - `copy /Y APP\settings\.env.cloud.example APP\settings\.env`
2. Build:
   - `docker compose --env-file APP/settings/.env build --no-cache`
3. Run:
   - `docker compose --env-file APP/settings/.env up -d`
4. Stop:
   - `docker compose --env-file APP/settings/.env down`

Topology:
- `backend`: FastAPI/Uvicorn
- `frontend`: Nginx static hosting
- `/api` proxied from frontend to backend

## 6. Where to Add Business Logic

- Backend:
  - workflow/business rules in `APP/server/services`
  - request/response contracts in `APP/server/entities`
  - route composition in `APP/server/routes`
- Frontend:
  - domain workflows in `APP/client/src/pages`
  - reusable domain UI in `APP/client/src/components`
  - API domain wrappers in `APP/client/src/services`
- Database:
  - domain schema in `APP/server/repositories/schemas/models.py`
  - domain query helpers in `APP/server/repositories/queries`

## 7. Instantiation Checklist

1. Rename `APP` package/folder to your project name.
2. Replace placeholder route/service/schema names with domain terms.
3. Keep env/deployment/runtime plumbing as-is unless infrastructure requires changes.
4. Keep client/server separation and job polling strategy for long-running operations.
