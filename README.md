# ParaGraph LLM Workflow

ParaGraph is a local-first workflow builder for deterministic LLM orchestration.
It includes:
- FastAPI backend (`ParaGraph/server`)
- React + TypeScript frontend (`ParaGraph/client`)
- Manifest-driven workflow compilation/execution
- Runtime polling and websocket event streaming

## Project Layout

```text
ParaGraph/
- client/                     # React + TypeScript + Vite
- server/                     # FastAPI backend (api/domain/services/repositories)
- resources/                  # local runtime state (nodes/workflows/models/artifacts/logs)
- settings/                   # .env and runtime settings
- start_on_windows.bat        # local launcher

tests/
- conftest.py
- run_tests.bat               # orchestration runner
- unit/server/...             # backend unit/API/service coverage
- e2e/server/...              # backend API lifecycle E2E coverage
```

## Active API Surface

### Workflows
- `/workflows`
- `/workflows/{workflow_id}`
- `/workflows/{workflow_id}/versions`

### Executions
- `/executions/compile`
- `/executions`
- `/executions/{run_id}`
- `/executions/{run_id}/events`
- websocket `/executions/ws/runs/{run_id}`

### Nodes and Providers
- `/nodes/catalog`
- `/nodes/import`
- `/nodes/uploads/directory`
- `/nodes/check-database-connection`
- `/providers/models`
- `/providers/ollama/library`
- `/providers/ollama/pull`
- `/providers/huggingface/models`
- `/providers/huggingface/download`
- `/providers/huggingface/download/{job_id}`

### Configurations
- `/configurations`
- `/configurations/profiles`
- `/configurations/profiles/{profile_name}`
- `/configurations/ollama/ping`

## Testing

### Backend (pytest)

```cmd
.\runtimes\.venv\Scripts\python.exe -m pytest tests/unit tests/e2e -v
```

Coverage includes:
- compiler and execution edge cases (duplicate links, multiplicity, missing ports/controllers)
- run retrieval and route error mapping behavior
- provider API error-to-HTTP mapping
- configuration profile and ping flows
- workflow version list + not-found behavior
- execution event sequencing and redaction
- end-to-end compile -> start -> poll -> outputs -> history -> websocket replay

### Frontend unit (Vitest + RTL)

```cmd
cd ParaGraph\client
npm run test:unit
```

Coverage includes:
- `src/app/services/api.ts`
- `src/app/services/workflowApi.ts`
- `useNodeCatalog` hook
- Nodes import modal validation/import interactions
- Configurations load/save modal interactions
- Models download state transitions (mock timers + mocked fetch/service calls)

### Frontend browser E2E (Playwright)

```cmd
cd ParaGraph\client
npm run test:e2e
```

Characteristics:
- local-only deterministic mock-backend mode (route stubs)
- deterministic websocket stub for execution events
- no cloud providers or live external network dependencies
- covers Workflow import/run/output rendering, Nodes import modal flows, and Configurations/Models smoke flows

### Full orchestration runner

```cmd
tests\run_tests.bat
```

`tests/run_tests.bat` runs available suites in order:
- backend pytest
- frontend unit (`test:unit` if present)
- frontend e2e (`test:e2e` if present)

## Runtime Notes

- Keep `VITE_API_BASE_URL` relative (default: `/api`).
- Backend and frontend are intended to run fully local in development.
- Runtime artifacts are stored under `ParaGraph/resources`.