from __future__ import annotations

import time
from collections.abc import Callable, Iterator

import pytest
from fastapi.testclient import TestClient

from ParaGraph.server.app import app
from ParaGraph.server.entities.jobs import JobState
from ParaGraph.server.services.jobs import job_manager


###############################################################################
def clear_job_manager() -> None:
    with job_manager.lock:
        threads = list(job_manager.threads.values())

    for thread in threads:
        if thread.is_alive():
            thread.join(timeout=1)

    with job_manager.lock:
        job_manager.jobs.clear()
        job_manager.threads.clear()


# -----------------------------------------------------------------------------
def register_job_state(job_id: str = "job-test", job_type: str = "workflow") -> JobState:
    state = JobState(job_id=job_id, job_type=job_type, status="running")
    with job_manager.lock:
        job_manager.jobs[job_id] = state
    return state


# -----------------------------------------------------------------------------
def wait_for_job_completion(job_id: str, timeout_s: float = 2.0) -> dict[str, object]:
    deadline = time.monotonic() + timeout_s
    last_snapshot: dict[str, object] | None = None

    while time.monotonic() < deadline:
        snapshot = job_manager.get_job_status(job_id)
        if snapshot is not None:
            last_snapshot = snapshot
            if str(snapshot["status"]) in {"completed", "failed", "cancelled"}:
                return snapshot
        time.sleep(0.01)

    raise AssertionError(f"Job {job_id} did not finish within {timeout_s} seconds. Last snapshot: {last_snapshot}")


###############################################################################
@pytest.fixture(autouse=True)
def isolated_job_manager() -> Iterator[None]:
    clear_job_manager()
    yield
    clear_job_manager()


# -----------------------------------------------------------------------------
@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


# -----------------------------------------------------------------------------
@pytest.fixture
def job_state_factory() -> Callable[[str, str], JobState]:
    return register_job_state


# -----------------------------------------------------------------------------
@pytest.fixture
def wait_for_job() -> Callable[[str, float], dict[str, object]]:
    return wait_for_job_completion
