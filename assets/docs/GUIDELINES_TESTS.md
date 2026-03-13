# HOW TO TEST

This document describes the current automated test strategy for the ParaGraph repository.

## Overview

ParaGraph tests are Python `pytest` tests focused on deterministic backend coverage.
The active suite covers:
- FastAPI app wiring.
- Node manifest APIs.
- Workflow compile and execution APIs.
- Workflow persistence/versioning.
- Background job manager lifecycle behavior.

The suite avoids live LLM, network, browser, and model-runtime dependencies. External calls should be faked or monkeypatched.

## Current Test Suite Structure

```text
tests/
|-- conftest.py
|-- run_tests.bat
`-- unit/
    `-- server/
        |-- test_app.py
        |-- routes/
        |   |-- test_platform.py
        |   `-- test_workflow.py
        `-- services/
            |-- test_jobs.py
            `-- workflow/
                `-- test_executor.py
```

## Quick Start (Windows)

Preferred runner:

```cmd
tests\run_tests.bat
```

Direct invocation:

```cmd
.\runtimes\.venv\Scripts\python.exe -m pytest tests/unit -v
```

Run a smaller slice:

```cmd
tests\run_tests.bat tests/unit/server/routes/test_platform.py
```

## Fixture Rules

`tests/conftest.py` provides shared primitives:
- `isolated_job_manager`: clears global job/thread state before and after every test.
- `client`: FastAPI `TestClient` bound to `ParaGraph.server.app.app`.
- `job_state_factory`: registers a synthetic running job for direct executor tests.
- `wait_for_job`: polls background jobs until they reach a terminal state.

When adding tests:
- Reuse these fixtures instead of duplicating polling/cleanup logic.
- Keep job-manager interactions isolated to avoid flaky global state leaks.
- Avoid writing persistent test artifacts into the real manifest/workflow directories unless the test also cleans them up or redirects the path.

## Coverage Rules

### API tests
- Use FastAPI `TestClient`.
- Assert both HTTP status and response shape.
- Prefer stable manifest/execution endpoints.

### Service tests
- Test workflow validation/execution directly in `tests/unit/server/services/...`.
- Stub provider calls so tests never call real LLM endpoints.
- Use compact workflow graphs that target one behavior at a time.

### Job tests
- Poll using `wait_for_job(...)` instead of fixed sleeps in assertions.
- Cover success, failure, and cancellation behavior for new job-backed workflows.

## Current Stable Endpoint Coverage Targets

- `/`
- `/nodes/catalog`
- `/nodes/import`
- `/nodes/check-database-connection`
- `/executions/compile`
- `/executions`
- `/executions/{run_id}`
- `/executions/{run_id}/events`
- `/workflows`

## Troubleshooting

- `pytest` not found: install the `test` extra into `runtimes/.venv`.
- Import errors: run tests from repo root so `ParaGraph` imports resolve.
- Flaky job assertions: ensure test state is isolated and avoid shared global mutations outside fixtures.
