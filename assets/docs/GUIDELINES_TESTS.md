# HOW TO TEST

This document describes the deterministic automated test architecture for ParaGraph.

## Test Matrix

ParaGraph test coverage is split into four suites:
- Backend unit/API/service tests (`pytest`)
- Backend end-to-end API lifecycle tests (`pytest`)
- Frontend unit/component/service tests (`Vitest + React Testing Library`)
- Frontend browser E2E flows (`Playwright` with mocked backend + websocket stubs)

All suites are designed for local deterministic execution:
- no cloud providers
- no model downloads/pulls during tests
- no live external network dependencies

## Directory Layout

```text
tests/
|-- conftest.py
|-- run_tests.bat
|-- unit/
|   `-- server/
|       |-- repositories/
|       |-- routes/
|       `-- services/
`-- e2e/
    `-- server/

ParaGraph/client/
|-- vitest.config.ts
|-- playwright.config.ts
|-- src/**/*.test.ts[x]
`-- tests/e2e/*.spec.ts
```

## Commands

### Backend

```cmd
.\runtimes\.venv\Scripts\python.exe -m pytest tests/unit tests/e2e -v
```

### Frontend unit

```cmd
cd ParaGraph\client
npm run test:unit
```

### Frontend browser E2E

```cmd
cd ParaGraph\client
npm run test:e2e
```

### Combined runner

```cmd
tests\run_tests.bat
```

The runner auto-detects frontend scripts:
- `test:unit`
- `test:e2e`

and executes all available phases cleanly.

## Shared Backend Fixtures

`tests/conftest.py` provides deterministic isolation primitives:
- `isolated_job_manager` (autouse): clears job/thread state per test.
- `isolated_runtime_state` (autouse): isolates workflow repository paths, execution run state, event bus history/subscribers, and provider caches.
- `client`: FastAPI `TestClient`.
- `job_state_factory`: registers synthetic running job state.
- `wait_for_job`: polling helper for background job completion.

## Backend Coverage Expectations

Primary route/service areas under coverage:
- `/executions/compile`, `/executions`, `/executions/{run_id}`, `/executions/{run_id}/events`
- websocket `/executions/ws/runs/{run_id}` replay and live behavior
- `/configurations`, `/configurations/profiles`, `/configurations/ollama/ping`
- `/providers/*` error-to-HTTP mapping
- `/workflows/{workflow_id}/versions` list + not-found behavior
- compiler/executor edge cases and output redaction/event sequencing

## Frontend Unit Coverage Expectations

Key targets:
- `src/app/services/api.ts`
- `src/app/services/workflowApi.ts`
- `src/workflow/hooks/useNodeCatalog.ts`
- `src/pages/NodesPage.tsx`
- `src/pages/ConfigurationsPage.tsx`
- `src/pages/ModelsPage.tsx`

Expected behavior assertions include:
- request error extraction
- polling loops
- websocket payload validation
- upload/download argument guards
- deterministic modal/hook/component interaction flows
- timer-driven model download transitions with mocked service responses

## Frontend Browser E2E Expectations

Playwright suite runs against the local Vite app in mocked-backend mode:
- API route stubs for `/workflows`, `/executions`, `/nodes`, `/providers`, `/configurations`
- deterministic websocket event stub for `/executions/ws/runs/{run_id}`
- no dependency on real backend/cloud services

Covered flows:
- Workflow page: import JSON bundle, run workflow, verify status/output rendering
- Nodes page: import modal validate + success/error import paths
- Configurations/Models pages: smoke interactions with deterministic state transitions

## Troubleshooting

- If backend tests fail on environment setup, verify `.\runtimes\.venv` exists and includes `pytest`.
- If frontend unit tests fail on missing dependencies, run `npm install` in `ParaGraph/client`.
- If Playwright cannot launch browsers, run `npx playwright install chromium` in `ParaGraph/client`.