from __future__ import annotations

import inspect
import threading
import uuid
from collections.abc import Callable
from time import monotonic
from typing import Any

from server.common.utils.logger import logger
from server.domain.jobs import JobState


###############################################################################
class JobManager:
    def __init__(self) -> None:
        self._jobs: dict[str, JobState] = {}
        self._threads: dict[str, threading.Thread] = {}
        self._lock = threading.Lock()

    # -------------------------------------------------------------------------
    def start_job(
        self,
        job_type: str,
        runner: Callable[..., dict[str, Any]],
        args: tuple[Any, ...] = (),
        kwargs: dict[str, Any] | None = None,
    ) -> str:
        job_id = str(uuid.uuid4())[:8]
        state = JobState(job_id=job_id, job_type=job_type, status="pending")
        runner_kwargs = kwargs.copy() if kwargs else {}

        if self._runner_accepts_job_id(runner):
            runner_kwargs["job_id"] = job_id

        with self._lock:
            self._jobs[job_id] = state

        thread = threading.Thread(
            target=self._run_job,
            args=(job_id, runner, args, runner_kwargs),
            daemon=True,
        )
        with self._lock:
            self._threads[job_id] = thread

        state.update(status="running")
        thread.start()
        logger.info("Started job %s (type=%s)", job_id, job_type)
        return job_id

    # -------------------------------------------------------------------------
    def get_job_status(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            state = self._jobs.get(job_id)
        if state is None:
            return None
        return state.snapshot()

    # -------------------------------------------------------------------------
    def cancel_job(self, job_id: str) -> bool:
        with self._lock:
            state = self._jobs.get(job_id)
        if state is None:
            return False
        if state.status not in ("pending", "running"):
            return False
        if state.status == "pending":
            state.update(
                stop_requested=True, status="cancelled", completed_at=monotonic()
            )
            return True
        state.update(stop_requested=True)
        return True

    # -------------------------------------------------------------------------
    def is_job_running(self, job_type: str | None = None) -> bool:
        with self._lock:
            for state in self._jobs.values():
                if state.status in ("pending", "running"):
                    if job_type is None or state.job_type == job_type:
                        return True
        return False

    # -------------------------------------------------------------------------
    def should_stop(self, job_id: str) -> bool:
        with self._lock:
            state = self._jobs.get(job_id)
        if state is None:
            return True
        return state.stop_requested

    # -------------------------------------------------------------------------
    def update_progress(self, job_id: str, progress: float) -> None:
        with self._lock:
            state = self._jobs.get(job_id)
        if state:
            state.update(progress=min(100.0, max(0.0, progress)))

    # -------------------------------------------------------------------------
    def update_result(self, job_id: str, patch: dict[str, Any]) -> None:
        with self._lock:
            state = self._jobs.get(job_id)
        if state is None:
            return
        with state.lock:
            existing = state.result or {}
            state.result = {**existing, **patch}

    # -------------------------------------------------------------------------
    def _run_job(
        self,
        job_id: str,
        runner: Callable[..., dict[str, Any]],
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> None:
        with self._lock:
            state = self._jobs.get(job_id)
        if state is None:
            return
        try:
            result = runner(*args, **kwargs)
            if state.stop_requested:
                state.update(status="cancelled", completed_at=monotonic())
                return
            with state.lock:
                merged = {**(state.result or {}), **(result or {})}
            state.update(
                status="completed",
                result=merged if merged else None,
                progress=100.0,
                completed_at=monotonic(),
            )
        except Exception as exc:  # noqa: BLE001
            if state.stop_requested:
                state.update(status="cancelled", completed_at=monotonic())
                return
            state.update(status="failed", error=str(exc), completed_at=monotonic())

    # -------------------------------------------------------------------------
    def _runner_accepts_job_id(self, runner: Callable[..., dict[str, Any]]) -> bool:
        try:
            signature = inspect.signature(runner)
        except TypeError, ValueError:
            return False
        for param in signature.parameters.values():
            if param.kind == param.VAR_KEYWORD:
                return True
        return "job_id" in signature.parameters

    # -------------------------------------------------------------------------
    def register_job_for_tests(self, state: JobState) -> None:
        with self._lock:
            self._jobs[state.job_id] = state

    # -------------------------------------------------------------------------
    def reset_for_tests(self) -> None:
        with self._lock:
            threads = list(self._threads.values())

        for thread in threads:
            if thread.is_alive():
                thread.join(timeout=1)

        with self._lock:
            self._jobs.clear()
            self._threads.clear()


###############################################################################
job_manager = JobManager()
