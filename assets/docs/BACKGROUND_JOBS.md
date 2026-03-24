# Background Job Management

ParaGraph uses a centralized in-process background job system for long-running work so API requests can return immediately and the UI can poll progress.

## Core Component

- Singleton: `ParaGraph.server.services.jobs.job_manager`
- State model: `ParaGraph.server.domain.jobs.JobState`
- Current execution mode: daemon threads (no process-based runner in current codebase)

## Job Lifecycle

Each job tracks:
- `job_id`: short UUID string (8 chars)
- `job_type`: logical group (`workflow`, `preparation`, `training`, `validation`, `inference`, ...)
- `status`: `pending`, `running`, `completed`, `failed`, `cancelled`
- `progress`: `0.0` to `100.0`
- `result`: merged result payload
- `error`: failure message
- `created_at`, `completed_at`: monotonic timestamps

## Execution Pattern

1. Endpoint calls `job_manager.start_job(job_type=..., runner=..., kwargs=...)`.
2. Job manager stores a `JobState` and starts a daemon thread.
3. Runner optionally receives `job_id` automatically if it accepts that argument.
4. Runner updates progress and partial output through:
   - `job_manager.update_progress(job_id, progress)`
   - `job_manager.update_result(job_id, patch)`
5. Thread finalizes state as `completed`, `failed`, or `cancelled`.

## Cancellation Model

Cancellation is cooperative:
- API calls `job_manager.cancel_job(job_id)`.
- Manager sets `stop_requested=True`.
- Runner must periodically call `job_manager.should_stop(job_id)` and return quickly when requested.

If a runner never checks `should_stop`, cancellation cannot stop it promptly.

## Current Route Usage

The polling contract is consistent across job-backed routers.

- Workflow:
  - start: `POST /workflow/execute`
  - poll: `GET /workflow/jobs/{job_id}`
  - cancel: `DELETE /workflow/jobs/{job_id}`
- Preparation:
  - start: `POST /preparation/dataset/process`
  - poll: `GET /preparation/jobs/{job_id}`
  - cancel: `DELETE /preparation/jobs/{job_id}`
- Training:
  - start: `POST /training/start` and `POST /training/resume`
  - poll: `GET /training/jobs/{job_id}`
  - cancel: `DELETE /training/jobs/{job_id}`
- Validation:
  - start: `POST /validation/run` and `POST /validation/checkpoint`
  - poll: `GET /validation/jobs/{job_id}`
  - cancel: `DELETE /validation/jobs/{job_id}`
- Inference:
  - start: `POST /inference/generate`
  - poll: `GET /inference/jobs/{job_id}`
  - cancel: `DELETE /inference/jobs/{job_id}`
- Hugging Face model download:
  - start: `POST /providers/huggingface/download`
  - poll: `GET /providers/huggingface/download/{job_id}`
  - cancel: `DELETE /providers/huggingface/download/{job_id}`
  - runner behavior: downloads stream by chunk and emit byte-level progress updates; cancellation is checked during chunk iteration for faster stop responses on large files.

## Minimal Runner Template

```python
from typing import Any

from ParaGraph.server.services.jobs import job_manager


def run_task(configuration: dict[str, Any], job_id: str) -> dict[str, Any]:
    for step in range(10):
        if job_manager.should_stop(job_id):
            return {}
        # do work
        job_manager.update_progress(job_id, (step + 1) * 10)
    return {"success": True}
```

## Notes for New Jobs

- Use one `job_type` per concurrency lane when you want `is_job_running(job_type)` guards.
- Return JSON-serializable dict payloads so frontend polling can consume results directly.
- Keep runners synchronous and deterministic where possible; isolate external calls behind service functions for testability.
