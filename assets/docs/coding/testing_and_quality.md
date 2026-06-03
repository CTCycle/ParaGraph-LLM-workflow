# Testing And Quality
Last updated: 2026-06-02

## Python Tooling
- Lint and format with Ruff or the project-approved equivalent.
- Keep typing compatible with Pylance expectations.
- Test backend behavior with pytest, including `tests/unit` and relevant `tests/e2e` coverage.

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
