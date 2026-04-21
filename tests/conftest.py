from __future__ import annotations

import time
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ParaGraph.server.app import app
from ParaGraph.server.domain.jobs import JobState
from ParaGraph.server.repositories.workflow import (
    execution_run_repository,
    workflow_repository,
)
from ParaGraph.server.services.jobs import job_manager
from ParaGraph.server.services.runtime.events import execution_event_service
from ParaGraph.server.services.workflow.provider import provider_service


###############################################################################
def clear_job_manager() -> None:
    job_manager.reset_for_tests()


# -----------------------------------------------------------------------------
def clear_execution_state() -> None:
    execution_run_repository.reset_for_tests()
    execution_event_service.reset_for_tests()


# -----------------------------------------------------------------------------
def clear_provider_caches() -> None:
    provider_service.reset_for_tests()


# -----------------------------------------------------------------------------
def register_job_state(
    job_id: str = "job-test", job_type: str = "workflow"
) -> JobState:
    state = JobState(job_id=job_id, job_type=job_type, status="running")
    job_manager.register_job_for_tests(state)
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

    raise AssertionError(
        f"Job {job_id} did not finish within {timeout_s} seconds. Last snapshot: {last_snapshot}"
    )


###############################################################################
@pytest.fixture(autouse=True)
def isolated_job_manager() -> Iterator[None]:
    clear_job_manager()
    yield
    clear_job_manager()


# -----------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def isolated_runtime_state(tmp_path: Path) -> Iterator[None]:
    isolated_root = tmp_path / "workflows"
    isolated_root.mkdir(parents=True, exist_ok=True)
    workflow_repository.configure_storage_for_tests(isolated_root)

    workflow_repository.reset_for_tests()
    clear_execution_state()
    clear_provider_caches()

    try:
        yield
    finally:
        workflow_repository.reset_for_tests()
        clear_execution_state()
        clear_provider_caches()
        workflow_repository.restore_default_storage_for_tests()


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
