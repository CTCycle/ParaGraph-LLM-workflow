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
    with job_manager.lock:
        threads = list(job_manager.threads.values())

    for thread in threads:
        if thread.is_alive():
            thread.join(timeout=1)

    with job_manager.lock:
        job_manager.jobs.clear()
        job_manager.threads.clear()


# -----------------------------------------------------------------------------
def clear_execution_state() -> None:
    with execution_run_repository._lock:  # noqa: SLF001
        execution_run_repository._runs.clear()  # noqa: SLF001

    with execution_event_service._lock:  # noqa: SLF001
        execution_event_service._subscribers.clear()  # noqa: SLF001
        execution_event_service._history.clear()  # noqa: SLF001
        execution_event_service._sequence.clear()  # noqa: SLF001


# -----------------------------------------------------------------------------
def clear_provider_caches() -> None:
    with provider_service._cache_lock:  # noqa: SLF001
        provider_service._ollama_library_cache = None  # noqa: SLF001
        provider_service._huggingface_cache.clear()  # noqa: SLF001
        provider_service._huggingface_filter_tags_cache.clear()  # noqa: SLF001


# -----------------------------------------------------------------------------
def register_job_state(
    job_id: str = "job-test", job_type: str = "workflow"
) -> JobState:
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
    original_root = workflow_repository._root  # noqa: SLF001
    original_index_path = workflow_repository._index_path  # noqa: SLF001

    isolated_root = tmp_path / "workflows"
    isolated_root.mkdir(parents=True, exist_ok=True)
    workflow_repository._root = isolated_root  # noqa: SLF001
    workflow_repository._index_path = isolated_root / "index.json"  # noqa: SLF001

    clear_execution_state()
    clear_provider_caches()

    try:
        yield
    finally:
        clear_execution_state()
        clear_provider_caches()
        workflow_repository._root = original_root  # noqa: SLF001
        workflow_repository._index_path = original_index_path  # noqa: SLF001


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
