# Testing And Quality
Last updated: 2026-07-06

## Python Tooling
- Lint and format with Ruff or the project-approved equivalent.
- Keep typing compatible with Pylance expectations.
- Test backend behavior with pytest, including `tests/unit` and relevant `tests/e2e` coverage.
- On Windows, run focused pytest commands from `app/` with a repo-local base temp and cache disabled when the default user temp root is locked:
  `.\server\.venv\Scripts\python.exe -m pytest <test-path> -q -p no:cacheprovider --basetemp=..\assets\QA\pytest-tmp`
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
