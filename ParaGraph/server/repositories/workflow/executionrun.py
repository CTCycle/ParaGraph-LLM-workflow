from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any

from ParaGraph.server.entities.execution import ExecutionRunState, ExecutionStepState


class ExecutionRunRepository:
    def __init__(self) -> None:
        self._runs: dict[str, ExecutionRunState] = {}
        self._lock = threading.Lock()

    def create_run(self, run: ExecutionRunState) -> None:
        with self._lock:
            self._runs[run.run_id] = run

    def get_run(self, run_id: str) -> ExecutionRunState | None:
        with self._lock:
            run = self._runs.get(run_id)
            if run is None:
                return None
            return run.model_copy(deep=True)

    def update_run(self, run_id: str, **kwargs: Any) -> ExecutionRunState | None:
        with self._lock:
            run = self._runs.get(run_id)
            if run is None:
                return None
            data = run.model_dump()
            data.update(kwargs)
            data["updated_at"] = datetime.now(timezone.utc)
            updated = ExecutionRunState.model_validate(data)
            self._runs[run_id] = updated
            return updated.model_copy(deep=True)

    def set_steps(self, run_id: str, steps: list[ExecutionStepState]) -> ExecutionRunState | None:
        with self._lock:
            run = self._runs.get(run_id)
            if run is None:
                return None
            data = run.model_dump()
            data["steps"] = [step.model_dump(mode="json") for step in steps]
            data["updated_at"] = datetime.now(timezone.utc)
            updated = ExecutionRunState.model_validate(data)
            self._runs[run_id] = updated
            return updated.model_copy(deep=True)


execution_run_repository = ExecutionRunRepository()