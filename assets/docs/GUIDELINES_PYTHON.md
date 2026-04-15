# Python Guidelines (ParaGraph Backend)
Last updated: 2026-04-08

Standards for Python code under `ParaGraph/server` and backend tests.

## 1. Runtime Baseline

- Python target: `>=3.14` (from `pyproject.toml`)
- Use repository environment when available:
  - `.\runtimes\.venv\Scripts\python.exe`
- Manage deps with `uv` and lockfiles; avoid ad-hoc global installs.

## 2. Layering and Ownership

- `server/api`: HTTP/websocket transport only
- `server/services`: business logic, orchestration, integrations
- `server/repositories`: persistence and state access
- `server/domain`: typed contracts/models
- `server/app.py`: app composition and router registration only

## 3. FastAPI Rules

- Define routes in dedicated router modules.
- Keep handlers thin; delegate behavior to services.
- Use typed request/response models.
- Map expected client faults to explicit `HTTPException` status codes.

## 4. Typing and Style

- Type public functions and non-trivial internal helpers.
- Use modern typing (`|`, built-in generics).
- Prefer explicit, readable control flow over meta-programming.
- Keep logs actionable and structured.
- Add comments only when behavior is not obvious from code.

## 5. Background Work

- Do not block API handlers with long tasks.
- Use `job_manager` for long-running tasks.
- Implement cooperative cancellation with `job_manager.should_stop(job_id)`.
- Keep job results JSON-serializable for polling consumers.

## 6. Persistence and Configuration

- Keep DB mode and DB connection/tuning configuration-file-driven (`settings/configurations.json`).
- Keep configuration load/coercion in configuration modules, not route handlers.
- Keep repository interfaces deterministic and easy to test.

## 7. Testing Expectations

- Use `pytest`.
- Use shared fixtures in `tests/conftest.py` for isolation.
- Keep unit tests deterministic (no live provider/network calls).
- For async/background flows, cover success, failure, and cancellation behavior where exposed.

## 8. Quality Gates

- Lint: `ruff`
- Type check: `mypy`
- Tests: `pytest`
