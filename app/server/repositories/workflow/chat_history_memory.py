from __future__ import annotations

import threading

from server.domain.chat_history import ChatHistoryMessage


###############################################################################
class InMemoryChatHistoryRepository:

    # -------------------------------------------------------------------------
    def __init__(self) -> None:
        self._store: dict[tuple[str, str, str], list[ChatHistoryMessage]] = {}
        self._lock = threading.Lock()

    # -------------------------------------------------------------------------
    def get_messages(
        self, workflow_id: str, execution_session_id: str, node_id: str
    ) -> list[ChatHistoryMessage]:
        key = (workflow_id, execution_session_id, node_id)
        with self._lock:
            return [item.model_copy(deep=True) for item in self._store.get(key, [])]

    # -------------------------------------------------------------------------
    def append_messages(
        self,
        workflow_id: str,
        execution_session_id: str,
        node_id: str,
        messages: list[ChatHistoryMessage],
    ) -> list[ChatHistoryMessage]:
        key = (workflow_id, execution_session_id, node_id)
        with self._lock:
            current = self._store.setdefault(key, [])
            current.extend(item.model_copy(deep=True) for item in messages)
            return [item.model_copy(deep=True) for item in current]

    # -------------------------------------------------------------------------
    def set_messages(
        self,
        workflow_id: str,
        execution_session_id: str,
        node_id: str,
        messages: list[ChatHistoryMessage],
    ) -> None:
        key = (workflow_id, execution_session_id, node_id)
        with self._lock:
            self._store[key] = [item.model_copy(deep=True) for item in messages]

    # -------------------------------------------------------------------------
    def clear_session(self, workflow_id: str, execution_session_id: str) -> None:
        with self._lock:
            keys_to_remove = [
                key
                for key in self._store
                if key[0] == workflow_id and key[1] == execution_session_id
            ]
            for key in keys_to_remove:
                del self._store[key]

    # -------------------------------------------------------------------------
    def reset_for_tests(self) -> None:
        with self._lock:
            self._store.clear()


in_memory_chat_history_repository = InMemoryChatHistoryRepository()
