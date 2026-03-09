# ParaGraph Packaging and Runtime Modes

## 1. Strategy

ParaGraph uses one active runtime file: `ParaGraph/settings/.env`.

- Local mode: run directly on Windows host via launcher.
- Cloud mode: run backend + frontend containers with Docker Compose.
- Mode switching: update/copy the active `.env` profile.
- Backend code paths are environment-driven (`DB_EMBEDDED`, DB host settings, ports, provider keys).

## 2. Runtime Profiles

- `ParaGraph/settings/.env.local.example`: local defaults (loopback hosts, embedded SQLite).
- `ParaGraph/settings/.env.cloud.example`: cloud/container defaults (bind all interfaces, external PostgreSQL).
- `ParaGraph/settings/.env`: active profile used by launcher, tests, and compose.
- `ParaGraph/settings/configurations.json`: non-secret defaults (`global`, `jobs`, base DB mode).

## 3. Required Environment Keys

| Key | Purpose |
|---|---|
| `FASTAPI_HOST`, `FASTAPI_PORT` | Backend bind host/port. |
| `UI_HOST`, `UI_PORT` | Frontend host/port for preview (local) and host publish port (compose). |
| `VITE_API_BASE_URL` | Frontend API base path (default `/api`). |
| `RELOAD` | Enables Uvicorn reload in launcher flow when `true`. |
| `OPTIONAL_DEPENDENCIES` | Controls optional dependency sync behavior in launcher/test flows. |
| `DB_EMBEDDED` | `true` for SQLite, `false` for PostgreSQL settings. |
| `DB_ENGINE`, `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` | External DB settings used when `DB_EMBEDDED=false`. |
| `DB_SSL`, `DB_SSL_CA`, `DB_CONNECT_TIMEOUT`, `DB_INSERT_BATCH_SIZE` | PostgreSQL TLS/connect/write tuning. |
| `OLLAMA_BASE_URL` | Base URL for local Ollama provider. |
| `OPENAI_API_KEY`, `OPENAI_BASE_URL` | OpenAI provider credentials and endpoint. |
| `GEMINI_API_KEY`, `GEMINI_BASE_URL` | Gemini provider credentials and endpoint. |
| `LLM_TIMEOUT_S` | Timeout used by LLM HTTP clients. |

## 4. Local Mode (Windows)

1. Copy local profile to active env:
   - `copy /Y ParaGraph\settings\.env.local.example ParaGraph\settings\.env`
2. Start app:
   - `ParaGraph\start_on_windows.bat`
3. Optional tests:
   - `tests\run_tests.bat`

Local mode does not require Docker.

### Launcher behavior summary

`start_on_windows.bat` currently:
- installs portable Python 3.14, `uv`, and Node.js under `ParaGraph/resources/runtimes`
- syncs backend deps from `pyproject.toml` (with `uv.lock` when available)
- installs frontend deps and builds client when needed
- starts backend (Uvicorn) and frontend preview server

## 5. Cloud Mode (Docker Compose)

1. Copy cloud profile:
   - `copy /Y ParaGraph\settings\.env.cloud.example ParaGraph\settings\.env`
2. Build images:
   - `docker compose --env-file ParaGraph/settings/.env build --no-cache`
3. Start services:
   - `docker compose --env-file ParaGraph/settings/.env up -d`
4. Stop services:
   - `docker compose --env-file ParaGraph/settings/.env down`

Cloud topology:
- `backend`: FastAPI/Uvicorn (`python:3.14.2-slim-bookworm` base).
- `frontend`: Nginx serving Vite build (`nginx:1.27.5-alpine` base).
- `/api/*` on frontend origin proxies to `backend:8000/*`.
- Named volume `app_resources` persists backend `ParaGraph/resources` in containers.

## 6. Deterministic Build Notes

- Backend dependencies are lockfile-backed through `uv.lock` and installed via `uv sync --frozen` when possible.
- Frontend dependencies are lockfile-backed via `ParaGraph/client/package-lock.json` and installed via `npm ci` fallbacking to `npm install`.
- Docker images pin major runtime versions in Dockerfiles.
