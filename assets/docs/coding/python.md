# Python
Last updated: 2026-06-02

## Runtime Baseline
- Target Python version is `>=3.14` as defined in `pyproject.toml`.
- Use `app/server/.venv` when present; otherwise use `runtimes/.venv`.
- Keep dependencies aligned with `uv` and `runtimes/uv.lock`.

## Typing
- Type annotations are required for public APIs and non-trivial logic.
- Use built-in generics such as `list[str]` and `dict[str, Any]`.
- Prefer `|` unions over `typing.Union`.
- Prefer `collections.abc` abstract container types where they fit.
- Treat typing as an enforceable quality gate, not optional documentation.

## Validation And API Contracts
- Use Pydantic and domain models for input and output validation.
- Avoid manual ad-hoc validation when a model can express the contract.
- Return explicit HTTP status codes and stable response shapes.
- Keep error handling safe, actionable, and traceable.
- Preserve execution and job traceability through fields such as `run_id`, `job_id`, and ordered event history.

## Async And Background Work
- Use async only with genuinely non-blocking dependencies.
- Do not run CPU-heavy work directly inside async request handlers.
- Route long-running work through `services/jobs.py`.
- Prefer start, poll, and cancel style APIs for long tasks when supported.

## Structure
- Keep functions small and focused.
- Make side effects explicit.
- Prefer composable logic over hidden coupling.
- Keep imports at the top of the file.
- Avoid nested function definitions unless there is no simpler structure.
- Use classes when they meaningfully group state or behavior.
- Keep modules under roughly 1000 lines where feasible.
- Avoid broad stylistic rewrites unrelated to the task.

## Documentation Expectation
- When Python behavior changes architecture, runtime behavior, or public contracts, update the relevant files under `assets/docs` in the same change set.
