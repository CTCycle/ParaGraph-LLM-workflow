from __future__ import annotations

import threading
from collections import defaultdict
from queue import Queue
from typing import Any

from server.domain.execution import ExecutionEventEnvelope, EventHistoryResponse
from server.repositories.workflow.execution_run import execution_run_repository

###############################################################################
class EventService:
    """Durable history with process-local live subscriber queues."""

    # -------------------------------------------------------------------------
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._subscribers: dict[str, list[Queue[ExecutionEventEnvelope]]] = defaultdict(
            list
        )

    # -------------------------------------------------------------------------
    def publish(
        self,
        *,
        run_id: str,
        event_type: str,
        payload: dict[str, Any],
        step_id: str | None = None,
        request_id: str | None = None,
    ) -> ExecutionEventEnvelope:
        event = execution_run_repository.append_event(
            run_id=run_id,
            event_type=event_type,
            payload=payload,
            step_id=step_id,
            request_id=request_id,
        )
        with self._lock:
            subscribers = list(self._subscribers.get(run_id, []))
        for queue in subscribers:
            queue.put(event)
        return event

    # -------------------------------------------------------------------------
    def subscribe(self, run_id: str) -> Queue[ExecutionEventEnvelope]:
        queue: Queue[ExecutionEventEnvelope] = Queue()
        with self._lock:
            self._subscribers[run_id].append(queue)
        return queue

    # -------------------------------------------------------------------------
    def unsubscribe(self, run_id: str, queue: Queue[ExecutionEventEnvelope]) -> None:
        with self._lock:
            queues = self._subscribers.get(run_id, [])
            if queue in queues:
                queues.remove(queue)
            if not queues:
                self._subscribers.pop(run_id, None)

    # -------------------------------------------------------------------------
    def get_history(self, run_id: str) -> EventHistoryResponse:
        events = execution_run_repository.get_events(run_id)
        return EventHistoryResponse(
            run_id=run_id,
            request_id=events[0].request_id if events else None,
            events=events,
        )

    # -------------------------------------------------------------------------
    def reset_for_tests(self) -> None:
        with self._lock:
            self._subscribers.clear()
        execution_run_repository.reset_for_tests()


execution_event_service = EventService()
