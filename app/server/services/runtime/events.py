from __future__ import annotations

import threading
from collections import defaultdict
from queue import Full, Queue
from typing import Any

from server.contracts.execution import ExecutionEventEnvelope, EventHistoryResponse
from server.repositories.workflow.execution_run import execution_run_repository


###############################################################################
class EventSubscriberQueue(Queue[ExecutionEventEnvelope]):
    """Bounded live queue that tells consumers when durable replay is needed."""

    def __init__(self, maxsize: int) -> None:
        super().__init__(maxsize=maxsize)
        self.overflowed = False

    # -------------------------------------------------------------------------
    def publish(self, event: ExecutionEventEnvelope) -> bool:
        try:
            self.put_nowait(event)
        except Full:
            self.overflowed = True
            return False
        return True


###############################################################################
class EventService:
    """Durable history with process-local live subscriber queues."""

    DEFAULT_SUBSCRIBER_QUEUE_SIZE = 1024
    DEFAULT_HISTORY_PAGE_SIZE = 1000

    # -------------------------------------------------------------------------
    def __init__(self, max_subscriber_queue_size: int | None = None) -> None:
        self._max_subscriber_queue_size = (
            max_subscriber_queue_size
            if max_subscriber_queue_size is not None
            else self.DEFAULT_SUBSCRIBER_QUEUE_SIZE
        )
        if self._max_subscriber_queue_size < 1:
            raise ValueError("max_subscriber_queue_size must be positive")
        self._lock = threading.Lock()
        self._publish_lock = threading.Lock()
        self._subscribers: dict[str, list[EventSubscriberQueue]] = defaultdict(list)

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
        with self._publish_lock:
            event = execution_run_repository.append_event(
                run_id=run_id,
                event_type=event_type,
                payload=payload,
                step_id=step_id,
                request_id=request_id,
            )
            with self._lock:
                subscribers = list(self._subscribers.get(run_id, []))
            for subscriber in subscribers:
                if not subscriber.publish(event):
                    self.unsubscribe(run_id, subscriber)
        return event

    # -------------------------------------------------------------------------
    def subscribe(self, run_id: str) -> EventSubscriberQueue:
        queue = EventSubscriberQueue(self._max_subscriber_queue_size)
        with self._lock:
            self._subscribers[run_id].append(queue)
        return queue

    # -------------------------------------------------------------------------
    def unsubscribe(self, run_id: str, queue: EventSubscriberQueue) -> None:
        with self._lock:
            queues = self._subscribers.get(run_id, [])
            if queue in queues:
                queues.remove(queue)
            if not queues:
                self._subscribers.pop(run_id, None)

    # -------------------------------------------------------------------------
    def get_history(
        self,
        run_id: str,
        *,
        after_sequence: int = 0,
        limit: int | None = None,
    ) -> EventHistoryResponse:
        events = execution_run_repository.get_events(
            run_id, after_sequence=after_sequence, limit=limit
        )
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
