# CODING_RULES

Last updated: 2026-04-24

## Python Rules

### Baseline

- Target Python version: `>=3.14` (from `pyproject.toml`).
- Use `runtimes/.venv` when present; otherwise use the project fallback virtual environment.
- Keep dependencies aligned with `uv` and `runtimes/uv.lock`.

### Typing

- Type annotations are required for public APIs and non-trivial logic.
- Use built-in generics (`list[str]`, `dict[str, Any]`).
- Prefer `|` unions over `typing.Union`.
- Prefer `collections.abc` abstract container types where applicable.
- Treat typing as a quality gate, not optional documentation.

### Validation and API Contracts

- Use Pydantic/domain models for input/output validation.
- Avoid ad-hoc manual validation when a model can encode constraints.
- Return explicit HTTP status codes and stable response shapes.
- Keep error handling safe and actionable.
- Preserve execution/job traceability (`run_id`, `job_id`, event sequences).

### Async and Background Work

- Use async only with non-blocking dependencies.
- Do not run CPU-heavy operations directly inside async request handlers.
- Route long-running work through the job system (`services/jobs.py`).
- For long tasks, maintain start + poll + cancel style APIs when supported.

### Code Structure

- Keep functions small and focused.
- Make side effects explicit.
- Prefer composable logic over hidden coupling.
- Add comments only when needed for clarity or safety.
- Keep imports at file top.
- Avoid nested function definitions unless unavoidable.
- Use classes where they meaningfully group behavior/state.
- Keep modules under approximately 1000 LOC where feasible.
- Avoid broad stylistic rewrites unrelated to the task.

### Tooling

- Lint/format with Ruff (or project-approved equivalent).
- Type-check with Pylance-compatible typing.
- Test with pytest, including `tests/unit` and relevant `tests/e2e` paths.

## TypeScript Rules

### Baseline

- Use strict TypeScript typing for application logic and service boundaries.
- Prefer explicit interfaces/types for API payloads and domain state.
- Keep API calls centralized under `client/src/app/services`.

### React and State

- Use function components with hooks.
- Keep page components orchestrating behavior; move reusable logic into hooks/services/components.
- Use memoization (`useMemo`, `useCallback`) only where behavior/performance benefits are clear.
- Keep route-level pages in `client/src/pages` and shared UI in `client/src/components`.

### UI and Styling

- Reuse design tokens and CSS variables from `src/index.css`.
- Keep component/page-specific styles in colocated CSS files.
- Preserve accessibility primitives (`focus-visible`, semantic labels, reduced-motion handling).

### Testing

- Unit/integration UI tests with Vitest + Testing Library.
- Browser flow validation with Playwright for cross-page/runtime behavior.
- Keep test fixtures/utilities under `client/src/test` when shared.

## Cross-Language Expectations

- Keep changes scoped and verifiable.
- Remove dead code and obsolete assets when touched.
- Prefer deterministic behavior and explicit error handling.
- Document architectural or runtime-impacting changes in `assets/docs` within the same change set.
