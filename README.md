# Generic Repository Bootstrap Template

This folder is a topic-agnostic bootstrap distilled from the current repository.  
It preserves the same core strategy:

- Monorepo layout with `ParaGraph/` as the main package.
- Client/server separation (`ParaGraph/client` and `ParaGraph/server`).
- Dual runtime modes: local launcher and cloud Docker deployment.
- Environment-driven configuration (`ParaGraph/settings/.env` + profile examples).
- Embedded SQLite or external PostgreSQL database wiring.
- Job-based backend workflows with polling endpoints.
- Matching test/tooling layout (`tests/unit`, `tests/e2e`, `tests/backend/verification`).

## 1. Structure

```text
template/
- ParaGraph/
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

- `ParaGraph/server/app.py` composes FastAPI and registers route modules.
- `ParaGraph/server/routes/` exposes HTTP endpoints and orchestrates services.
- `ParaGraph/server/services/` contains workflow/service logic (including job orchestration).
- `ParaGraph/server/repositories/` contains persistence adapters (SQLite/PostgreSQL), schema definitions, and data serialization helpers.
- `ParaGraph/server/configurations/` loads JSON + env settings and applies runtime overrides.
- `ParaGraph/client/src/pages/` holds route pages.
- `ParaGraph/client/src/components/` holds reusable UI blocks.
- `ParaGraph/client/src/services/` holds API client functions and polling helpers.
- `ParaGraph/client/src/AppStateContext.tsx` centralizes page-level state.

## 3. Naming and Conventions

- Keep framework-neutral, use-case-neutral names in shared layers:
  - `Dataset*`, `Training*`, `Inference*`, `Validation*` can be renamed to your domain workflows if needed.
- Place domain logic only in:
  - backend services (`ParaGraph/server/services`)
  - backend route orchestration (`ParaGraph/server/routes`)
  - frontend pages/components (`ParaGraph/client/src/pages`, `ParaGraph/client/src/components`)
- Keep persistence and runtime plumbing generic and reusable.

## 4. Local Run Strategy

1. Copy local profile to active env:
   - `copy /Y ParaGraph\\settings\.env.local.example ParaGraph\\settings\.env`
2. Launch:
   - `ParaGraph\\start_on_windows.bat`
3. Optional tests:
   - `tests\run_tests.bat`

The launcher mirrors the repository pattern:
- reads `ParaGraph/settings/.env`
- syncs backend deps with `uv`
- builds frontend with `npm`
- starts backend (`uvicorn`) and frontend preview server

## 5. Cloud Deployment Strategy

1. Copy cloud profile:
   - `copy /Y ParaGraph\\settings\.env.cloud.example ParaGraph\\settings\.env`
2. Build:
   - `docker compose --env-file ParaGraph/settings/.env build --no-cache`
3. Run:
   - `docker compose --env-file ParaGraph/settings/.env up -d`
4. Stop:
   - `docker compose --env-file ParaGraph/settings/.env down`

Topology:
- `backend`: FastAPI/Uvicorn
- `frontend`: Nginx static hosting
- `/api` proxied from frontend to backend

## 6. Where to Add Business Logic

- Backend:
  - workflow/business rules in `ParaGraph/server/services`
  - request/response contracts in `ParaGraph/server/entities`
  - route composition in `ParaGraph/server/routes`
- Frontend:
  - domain workflows in `ParaGraph/client/src/pages`
  - reusable domain UI in `ParaGraph/client/src/components`
  - API domain wrappers in `ParaGraph/client/src/services`
- Database:
  - domain schema in `ParaGraph/server/repositories/schemas/models.py`
  - domain query helpers in `ParaGraph/server/repositories/queries`

## 7. Instantiation Checklist

1. Rename `ParaGraph` package/folder to your project name.
2. Replace placeholder route/service/schema names with domain terms.
3. Keep env/deployment/runtime plumbing as-is unless infrastructure requires changes.
4. Keep client/server separation and job polling strategy for long-running operations.

