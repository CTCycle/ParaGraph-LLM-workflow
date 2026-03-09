# HOW TO TEST

This document describes the current automated test strategy for the ParaGraph repository.

## Overview

ParaGraph tests are currently Python `pytest` tests focused on deterministic backend coverage. The active suite covers:
- FastAPI app wiring.
- Workflow API endpoints.
- Workflow executor behavior.
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

The batch runner currently:
- reads `ParaGraph/settings/.env` for host and optional-dependency flags
- validates that `.venv` exists and includes pytest
- runs pytest against `tests/unit`
- forwards extra CLI args to pytest

Direct invocation:

```cmd
.\.venv\Scripts\python.exe -m pytest tests/unit -v
```

Run a smaller slice:

```cmd
tests\run_tests.bat tests/unit/server/routes/test_workflow.py
```

## Prerequisites

- Python 3.14+ environment in `.venv`.
- Project dependencies installed.
- Test extra installed from `pyproject.toml` (currently `pytest`).

Install/refresh test dependencies:

```cmd
uv sync --extra test
```

If `OPTIONAL_DEPENDENCIES=true` is enabled in `.env`, ensure optional packages expected by scripts are also installed.

## Fixture Rules

`tests/conftest.py` provides shared primitives:

| Fixture/helper | Scope | Purpose |
|---|---|---|
| `isolated_job_manager` | function, autouse | Clears global job/thread state before and after every test |
| `client` | function | FastAPI `TestClient` bound to `ParaGraph.server.app.app` |
| `job_state_factory` | function | Registers a synthetic running job for direct executor tests |
| `wait_for_job` | function | Polls background jobs until they reach a terminal state |

When adding tests:
- Reuse these fixtures instead of duplicating polling/cleanup logic.
- Keep job-manager interactions isolated to avoid flaky global state leaks.

## Coverage Rules

### API tests

- Use FastAPI `TestClient`.
- Assert both HTTP status and response shape.
- Prefer stable endpoints for deterministic coverage.

### Service tests

- Test workflow validation/execution directly in `tests/unit/server/services/...`.
- Stub `select_llm_provider(...)` so tests never call real providers.
- Use compact workflow graphs that target one behavior at a time.

### Job tests

- Poll using `wait_for_job(...)` instead of fixed sleeps in assertions.
- Cover success, failure, and cancellation behavior for new job-backed workflows.

## Naming and Layout Rules

- Route tests: `tests/unit/server/routes/`.
- Service tests: `tests/unit/server/services/`.
- File naming: `test_<subject>.py`.
- Test naming: behavior-focused, not implementation-focused.

## Current Stable Endpoint Coverage Targets

- `/`
- `/workflow/catalog`
- `/workflow/validate`
- `/workflow/execute`
- `/workflow/jobs/{job_id}`

Other routers exist, but several paths are still placeholder implementations; add tests there as behavior stabilizes.

## Troubleshooting

- `pytest` not found: install the `test` extra into `.venv`.
- Import errors: run tests from repo root so `ParaGraph` imports resolve.
- Flaky job assertions: ensure test state is isolated and avoid shared global mutations outside fixtures.
