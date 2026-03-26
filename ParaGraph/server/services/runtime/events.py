from __future__ import annotations

import threading
from collections import defaultdict
from queue import Queue
from typing import Any

from ParaGraph.server.domain.execution import ExecutionEventEnvelope, EventHistoryResponse

###############################################################################
class EventService:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._subscribers: dict[str, list[Queue[ExecutionEventEnvelope]]] = defaultdict(list)
        self._history: dict[str, list[ExecutionEventEnvelope]] = defaultdict(list)
        self._sequence: dict[str, int] = defaultdict(int)

    # -------------------------------------------------------------------------
    def publish(
        self,
        *,
        run_id: str,
        event_type: str,
        payload: dict[str, Any],
        step_id: str | None = None,
    ) -> ExecutionEventEnvelope:
        with self._lock:
            self._sequence[run_id] += 1
            event = ExecutionEventEnvelope(
                event_type=event_type,
                run_id=run_id,
                step_id=step_id,
                sequence=self._sequence[run_id],
                payload=payload,
            )
            self._history[run_id].append(event)
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
            if not queues and run_id in self._subscribers:
                del self._subscribers[run_id]

    # -------------------------------------------------------------------------
    def get_history(self, run_id: str) -> EventHistoryResponse:
        with self._lock:
            events = list(self._history.get(run_id, []))
        return EventHistoryResponse(run_id=run_id, events=events)


execution_event_service = EventService()