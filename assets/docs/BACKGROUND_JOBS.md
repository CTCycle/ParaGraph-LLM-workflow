# Background Jobs
Last updated: 2026-04-08

ParaGraph uses an in-process thread-based `JobManager` for long-running work.

## 1. Core Components

- Manager: `ParaGraph.server.services.jobs.job_manager`
- State model: `ParaGraph.server.domain.jobs.JobState`
- Execution model: daemon thread per job (`threading.Thread`)

## 2. Job Lifecycle

Each job tracks:
- `job_id` (short UUID)
- `job_type`
- `status` (`pending`, `running`, `completed`, `failed`, `cancelled`)
- `progress` (`0.0` to `100.0`)
- `result` (JSON-serializable dict patches)
- `error`, `created_at`, `completed_at`

Execution flow:
1. `job_manager.start_job(...)`
2. state created as `pending`, then moved to `running`
3. runner executes in thread and optionally receives `job_id`
4. runner updates progress/result via manager APIs
5. manager finalizes terminal state

## 3. Cancellation Model

Cancellation is cooperative:

- API/service requests `job_manager.cancel_job(job_id)`
- manager sets `stop_requested`
- runner must check `job_manager.should_stop(job_id)` regularly

If a runner does not poll `should_stop`, cancellation is delayed.

## 4. Active API Usage

Current public endpoints using this model:

- Workflow execution:
  - start: `POST /executions`
  - poll: `GET /executions/{run_id}`
  - event history: `GET /executions/{run_id}/events`
  - websocket stream: `WS /executions/ws/runs/{run_id}`
  - note: no public cancel endpoint is currently exposed for execution runs.

- Hugging Face downloads:
  - start: `POST /providers/huggingface/download`
  - poll: `GET /providers/huggingface/download/{job_id}`
  - cancel: `DELETE /providers/huggingface/download/{job_id}`

## 5. Minimal Runner Template

```python
from typing import Any

from ParaGraph.server.services.jobs import job_manager


def run_task(payload: dict[str, Any], job_id: str) -> dict[str, Any]:
    for step in range(10):
        if job_manager.should_stop(job_id):
            return {}
        job_manager.update_progress(job_id, (step + 1) * 10)
    return {"ok": True}
```

## 6. Rules for New Jobs

- Keep runner outputs JSON-serializable.
- Keep side effects isolated in service helpers for easier tests.
- Emit meaningful incremental progress.
- Ensure cancellation checks exist in long loops and network chunk iteration.
