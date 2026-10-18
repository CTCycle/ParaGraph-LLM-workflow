# Testing And Quality
Last updated: 2026-10-18

## Python Tooling
- Lint and format with Ruff or the project-approved equivalent.
- Keep typing compatible with Pylance expectations.
- Test backend behavior with pytest, including `tests/unit` and relevant `tests/e2e` coverage.
- All runtime, test, tool, browser, and generated frontend-build caches are centralized under `runtimes/cache`, including uv, npm, Python bytecode, pytest, Ruff, coverage, Vite, Vitest, Playwright, ESLint, and Hugging Face runtime caches.
- On Windows, run focused pytest commands from the repository root with the repository-local cache and base temp directories:
  `.\app\server\.venv\Scripts\python.exe -m pytest -c .\pytest.ini <test-path> -q --basetemp=.\runtimes\cache\pytest-tmp`
- If pytest still ends with `WinError 5` during temp cleanup, keep the affected temporary roots under `runtimes/cache` or the ignored `assets/QA` scratch area and treat the output as disposable; use a direct harness only as supplemental evidence.

## Validation Evidence
- Record durable validation outcomes in `assets/docs/project_status_ledger.md` and define campaign slices in `assets/docs/validation/strategy.md`; do not create standalone QA report files.
- Keep transient evidence (screenshots, coverage data, run exports, test databases, logs) in the ignored `assets/QA` or `runtimes/cache` scratch areas; never commit it.
- Prefer tracked tests as the reproducible evidence backing a ledger entry; link a CI run URL only for CI-side coverage.

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
