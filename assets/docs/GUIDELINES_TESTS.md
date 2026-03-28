# Testing Guidelines

Deterministic local test strategy for ParaGraph.

## 1. Test Suites

- Backend unit/API/service tests (`pytest`)
- Backend end-to-end API lifecycle tests (`pytest`)
- Frontend unit/component/service tests (`Vitest + React Testing Library`)
- Frontend browser E2E (`Playwright`)

Design goal: no required cloud/provider dependencies for default test runs.

## 2. Layout

```text
tests/
|- conftest.py
|- run_tests.bat
|- unit/server/...
`- e2e/server/...

ParaGraph/client/
|- vitest.config.ts
|- playwright.config.ts
|- src/**/*.test.ts[x]
`- tests/e2e/*.spec.ts
```

## 3. Commands

Backend:

```cmd
.\runtimes\.venv\Scripts\python.exe -m pytest tests/unit tests/e2e -v
```

Frontend unit:

```cmd
cd ParaGraph\client
npm run test:unit
```

Frontend E2E:

```cmd
cd ParaGraph\client
npm run test:e2e
```

Combined runner:

```cmd
tests\run_tests.bat
```

## 4. Combined Runner Behavior

`tests/run_tests.bat`:
- requires `runtimes/.venv` with `pytest`
- auto-detects frontend scripts (`test:unit`, `test:e2e`)
- can bootstrap frontend deps/build unless skipped by env flags
- supports optional live-server mode for `tests/e2e` with:
  - `PARAGRAPH_ENABLE_LIVE_E2E_SERVERS=true`

## 5. Backend Fixture Expectations

`tests/conftest.py` provides isolation helpers for:
- job manager state
- execution/event runtime state
- workflow/resource directories
- provider caches

Use these fixtures instead of creating ad-hoc global state hooks.

## 6. Coverage Priorities

- `/workflows`, `/executions`, `/nodes`, `/providers`, `/configurations` routes
- execution compile/start/poll/events/websocket flow
- provider error-to-HTTP mapping and download polling behavior
- workflow/node contract validation and execution safety checks
- frontend service-layer API contract handling and deterministic UI flows

## 7. Troubleshooting

- Missing backend deps: run `uv sync --extra test` in repo root.
- Missing frontend deps: run `npm install` in `ParaGraph/client`.
- Playwright browser missing: run `npx playwright install chromium` in `ParaGraph/client`.
