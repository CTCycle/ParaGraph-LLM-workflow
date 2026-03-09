from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from ParaGraph.server.services.jobs import job_manager


###############################################################################
def test_start_job_injects_job_id_and_merges_results(
    wait_for_job: Callable[[str, float], dict[str, object]],
) -> None:
    observed: dict[str, str] = {}

    def runner(*, job_id: str) -> dict[str, Any]:
        observed["job_id"] = job_id
        job_manager.update_result(job_id, {"stage": "running"})
        return {"success": True}

    job_id = job_manager.start_job(job_type="unit", runner=runner)
    payload = wait_for_job(job_id)

    assert observed["job_id"] == job_id
    assert payload["status"] == "completed"
    assert payload["progress"] == 100.0
    assert payload["result"] == {"stage": "running", "success": True}


# -----------------------------------------------------------------------------
def test_cancel_job_marks_running_job_cancelled(
    wait_for_job: Callable[[str, float], dict[str, object]],
) -> None:
    def runner(*, job_id: str) -> dict[str, Any]:
        while not job_manager.should_stop(job_id):
            time.sleep(0.01)
        return {"success": False}

    job_id = job_manager.start_job(job_type="unit", runner=runner)

    assert job_manager.cancel_job(job_id) is True

    payload = wait_for_job(job_id)

    assert payload["status"] == "cancelled"
    assert payload["result"] is None


# -----------------------------------------------------------------------------
def test_cancel_job_returns_false_for_unknown_job() -> None:
    assert job_manager.cancel_job("missing-job") is False
