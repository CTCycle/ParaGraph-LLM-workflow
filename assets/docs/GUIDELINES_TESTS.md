# HOW TO TEST

This document describes the current test strategy for the ParaGraph repository.

## Overview

ParaGraph tests are currently Python `pytest` tests focused on deterministic backend coverage. The initial suite covers:
- FastAPI app wiring.
- Workflow API endpoints.
- Workflow executor behavior.
- Background job manager lifecycle behavior.

The suite deliberately avoids live LLM, network, browser, and model-runtime dependencies. External calls must be replaced with fakes or monkeypatches.

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

The batch runner:
- reads `ParaGraph/settings/.env` for host and optional-dependency flags
- validates that `.venv` exists and contains the required test dependencies
- runs the backend pytest suite at `tests/unit`
- forwards any extra CLI arguments to `pytest`

Direct invocation remains available:

```cmd
.\.venv\Scripts\python.exe -m pytest tests/unit -v
```

To run a smaller slice while iterating:

```cmd
tests\run_tests.bat tests/unit/server/routes/test_workflow.py
```

## Prerequisites

- Python 3.14+ environment available in `.venv`.
- Project dependencies installed.
- Test extra installed from `pyproject.toml` (`pytest`, `pytest-playwright`, `psutil`).

If the environment is missing test dependencies, run:

```cmd
uv sync --extra test
```

Or set `OPTIONAL_DEPENDENCIES=true` in `ParaGraph/settings/.env` and rerun `ParaGraph\start_on_windows.bat`.

## Fixture Rules

`tests/conftest.py` provides the shared testing primitives for the current suite:

| Fixture/helper | Scope | Purpose |
|---|---|---|
| `isolated_job_manager` | function, autouse | Clears global job/thread state before and after every test |
| `client` | function | FastAPI `TestClient` bound to `ParaGraph.server.app.app` |
| `job_state_factory` | function | Registers a synthetic running job for direct executor tests |
| `wait_for_job` | function | Polls background jobs until they reach a terminal state |

When adding tests:
- Reuse these fixtures instead of duplicating polling or cleanup logic.
- Keep all job-manager interactions isolated; global state leaks will make the suite flaky.

## Coverage Rules

### API tests

- Use FastAPI `TestClient`.
- Prefer testing real route wiring for stable endpoints such as `/workflow/...`.
- Assert both HTTP status codes and response payload shapes.

### Service tests

- Test workflow validation/execution directly in `tests/unit/server/services/...`.
- Stub `select_llm_provider(...)` or lower-level clients so tests never hit Ollama or cloud APIs.
- Use minimal workflow graphs that still exercise the target behavior.

### Job tests

- Prefer polling via `wait_for_job(...)` instead of fixed sleeps in assertions.
- Cover success, failure, and cancellation behavior for background jobs when adding new job-backed workflows.

## Naming and Layout Rules

- Keep test modules close to the code layer they verify:
  - Route tests in `tests/unit/server/routes/`
  - Service tests in `tests/unit/server/services/`
- Name files `test_<subject>.py`.
- Name tests for observable behavior, not implementation details.

## Current Stable Backend Endpoints

These are the best current candidates for API coverage:
- `/`
- `/workflow/catalog`
- `/workflow/validate`
- `/workflow/execute`
- `/workflow/jobs/{job_id}`

Other routers exist, but some paths are still placeholders or depend on heavier runtime state. Add tests there only when the underlying behavior becomes stable enough to assert deterministically.

## Important Notes

- Use Arrange-Act-Assert.
- Keep tests isolated and deterministic.
- Do not make real HTTP calls to LLM providers.
- Do not require a separately running frontend or backend process for unit/API tests.
- If behavior changes materially, update this file in the same change.

## Troubleshooting

- **`pytest` not found**: install the `test` extra into `.venv`.
- **Import/configuration errors**: ensure tests are run from the repository root so `ParaGraph` imports resolve correctly.
- **Flaky job assertions**: use `wait_for_job(...)` and verify that the test is not leaking state into the shared `job_manager`.
