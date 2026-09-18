# Testing And Quality
Last updated: 2026-09-18

## Python Tooling
- Lint and format with Ruff or the project-approved equivalent.
- Keep typing compatible with Pylance expectations.
- Test backend behavior with pytest, including `tests/unit` and relevant `tests/e2e` coverage.
- All runtime, test, tool, browser, and generated frontend-build caches are centralized under `runtimes/cache`, including uv, npm, Python bytecode, pytest, Ruff, coverage, Vite, Vitest, Playwright, ESLint, and Hugging Face runtime caches.
- On Windows, run focused pytest commands from `app/` with the repository-local cache and base temp directories:
  `.\app\server\.venv\Scripts\python.exe -m pytest -c .\pytest.ini <test-path> -q --basetemp=.\runtimes\cache\pytest-tmp`
- If pytest still ends with `WinError 5` during temp cleanup, preserve the exact traceback under `assets/QA/` and use a direct harness only as supplemental evidence.

## Frontend Tooling
- Use Vitest and Testing Library for unit and integration coverage.
- Use Playwright for browser-level validation across pages and runtime flows.
- Keep shared test fixtures and utilities under `client/src/test` when reuse is warranted.

## Cross-Language Expectations
- Keep changes scoped, reviewable, and verifiable.
- Remove dead code and obsolete assets when the touched area makes them irrelevant.
- Prefer deterministic behavior and explicit error handling.
- Document architecture-impacting, runtime-impacting, and user-visible behavior changes in `assets/docs` within the same change set.

## Documentation Quality Rules
- Prefer multiple focused leaf files over large mixed-purpose markdown files.
- Keep the root overview synchronized with every file move, addition, rename, or deletion.
- Do not leave stale paths or obsolete file names in documentation indexes.
