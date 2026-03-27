# Engineering and Python Standards

Standards for Python 3.14+ code in ParaGraph backend services.

---

## 1. Version and Scope

- Target Python `>=3.14`.
- Applies to FastAPI routes, services, repositories, scripts, and tests.

---

## 2. Typing and APIs

1. Use built-in generics (`list`, `dict`, `tuple`) and `|` unions.
2. Type all public functions and non-trivial internal helpers.
3. Prefer `collections.abc` imports for protocol types (`Callable`, `Iterable`, etc.).
4. Keep Pydantic schemas in `ParaGraph/server/domain` as the API contract source.

---

## 3. Project Structure

1. Keep HTTP concerns in `server/api`.
2. Keep business/workflow logic in `server/services`.
3. Keep data persistence logic in `server/repositories`.
4. Keep app wiring in `server/app.py` only.

---

## 4. FastAPI Rules

1. Split endpoints into routers and register them in `app.py`.
2. Use Pydantic models for request/response bodies.
3. Raise `HTTPException` with clear details for client errors.
4. Keep endpoints thin; delegate logic to services.

---

## 5. Background Jobs

1. Do not block request handlers for long-running work.
2. Use ParaGraph `JobManager` (`ParaGraph.server.services.jobs`).
3. Design runners for cooperative cancellation via `job_manager.should_stop(job_id)`.
4. Expose polling and cancellation endpoints for every long-running route.

---

## 6. Persistence Rules

1. Keep schema definitions under `repositories/schemas`.
2. Keep backend-specific logic in `repositories/database/sqlite.py` and `postgres.py`.
3. Keep database mode selection environment-driven (`DB_EMBEDDED`, DB settings).

---

## 7. Code Style

1. Follow PEP 8 and keep modules cohesive.
2. Prefer simple, explicit logic over premature abstractions.
3. Add comments only when behavior is not self-evident.
4. Keep logging structured and useful for debugging.
- Leverage classes to group methods with similar scope
- Enforce the use of cosmetic separators (series of # and - symbols) for class and functions

---

## 8. Testing

1. Use pytest for backend coverage.
2. Keep tests deterministic (no real LLM/network calls in unit tests).
3. Reuse shared fixtures in `tests/conftest.py` for job-state isolation.
4. Cover happy path, failure path, and cancellation path for job-backed services.

---

## 9. Tooling Summary

- Formatter: Black or Ruff formatter.
- Linter: Ruff.
- Type checker: mypy.
- Test runner: pytest.
