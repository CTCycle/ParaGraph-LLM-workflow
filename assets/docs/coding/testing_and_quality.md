# Testing and Quality
Last updated: 2026-10-18

## Python Tooling
- Use Ruff or the project-approved equivalent for linting and formatting, and keep typing compatible with Pylance expectations.
- Use pytest for backend behavior in unit tests and relevant end-to-end tests.
- Runtime, test, tool, browser, and generated frontend-build caches are under runtimes/cache.
- On Windows, run focused tests from the repository root with the project environment and local temporary directory:

        .\app\server\.venv\Scripts\python.exe -m pytest -c .\pytest.ini <test-path> -q --basetemp=.\runtimes\cache\pytest-tmp

- If pytest reports WinError 5 during temporary-file cleanup, keep the affected temporary roots under runtimes/cache or ignored assets/QA and treat the cleanup output as disposable. A direct harness is supplemental evidence only.

## Frontend Tooling
- Use Vitest and Testing Library for unit and component coverage.
- Use Playwright for browser-level page and runtime flows.
- Keep shared fixtures under client/src/test when reuse is warranted.

## Validation Records
Record durable outcomes in the [project status ledger](../project_status_ledger.md), following the [validation strategy](../validation/strategy.md). Keep screenshots, coverage exports, run data, test databases, and logs in ignored scratch directories; do not track standalone QA reports.

## Cross-Language Expectations
- Keep changes scoped, reviewable, and verifiable.
- Remove dead code and obsolete assets when the touched area makes them irrelevant.
- Prefer deterministic behavior and explicit error handling.
- Document architecture, runtime, and user-visible behavior in its owning document in assets/docs.
