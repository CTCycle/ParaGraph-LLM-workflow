from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Protocol

from server.domain.chat_history import (
    ChatHistoryHandle,
    ChatHistoryMessage,
    DEFAULT_CHAT_HISTORY_STORAGE_BACKEND,
)
from server.repositories.workflow import (
    database_chat_history_repository,
    file_chat_history_repository,
    in_memory_chat_history_repository,
)


class ChatHistoryRepository(Protocol):
    def get_messages(
        self, workflow_id: str, execution_session_id: str, node_id: str
    ) -> list[ChatHistoryMessage]: ...

    def append_messages(
        self,
        workflow_id: str,
        execution_session_id: str,
        node_id: str,
        messages: list[ChatHistoryMessage],
    ) -> list[ChatHistoryMessage]: ...

    def clear_session(self, workflow_id: str, execution_session_id: str) -> None: ...

    def set_messages(
        self,
        workflow_id: str,
        execution_session_id: str,
        node_id: str,
        messages: list[ChatHistoryMessage],
    ) -> None: ...


class ChatHistoryService:
    def _repository_for_handle(self, handle: ChatHistoryHandle) -> ChatHistoryRepository:
        if handle.node_type == "CHAT_HISTORY_MEMORY":
            return in_memory_chat_history_repository
        backend = handle.storage_backend or DEFAULT_CHAT_HISTORY_STORAGE_BACKEND
        if backend == "database":
            return database_chat_history_repository
        return file_chat_history_repository

    def _trim_to_limit(
        self, messages: list[ChatHistoryMessage], max_messages: int
    ) -> list[ChatHistoryMessage]:
        if len(messages) <= max_messages:
            return messages
        return messages[-max_messages:]

    def _overwrite_from_trimmed(
        self, handle: ChatHistoryHandle, messages: list[ChatHistoryMessage]
    ) -> None:
        repository = self._repository_for_handle(handle)
        repository.set_messages(
            handle.workflow_id,
            handle.execution_session_id,
            handle.node_id,
            messages,
        )

    def load_messages(self, handle: ChatHistoryHandle) -> list[ChatHistoryMessage]:
        repository = self._repository_for_handle(handle)
        messages = repository.get_messages(
            handle.workflow_id, handle.execution_session_id, handle.node_id
        )
        trimmed = self._trim_to_limit(messages, handle.max_messages)
        if len(trimmed) != len(messages):
            self._overwrite_from_trimmed(handle, trimmed)
        return trimmed

    def format_history_for_prompt(self, handle: ChatHistoryHandle) -> str:
        messages = self.load_messages(handle)
        if not messages:
            return ""
        if handle.keep_prompt_type:
            return handle.separator.join(
                f"{message.role}: {message.content}" for message in messages
            )
        return handle.separator.join(message.content for message in messages)

    def append_exchange(
        self,
        handle: ChatHistoryHandle,
        *,
        system_prompt: str,
        user_prompt: str,
        assistant_output: str,
    ) -> None:
        repository = self._repository_for_handle(handle)
        timestamp = datetime.now(timezone.utc)
        new_messages: list[ChatHistoryMessage] = []
        if system_prompt.strip():
            new_messages.append(
                ChatHistoryMessage(
                    role="system", content=system_prompt.strip(), timestamp=timestamp
                )
            )
        if user_prompt.strip():
            new_messages.append(
                ChatHistoryMessage(
                    role="user", content=user_prompt.strip(), timestamp=timestamp
                )
            )
        if assistant_output.strip():
            new_messages.append(
                ChatHistoryMessage(
                    role="assistant",
                    content=assistant_output.strip(),
                    timestamp=timestamp,
                )
            )
        if not new_messages:
            return
        merged = repository.append_messages(
            handle.workflow_id, handle.execution_session_id, handle.node_id, new_messages
        )
        trimmed = self._trim_to_limit(merged, handle.max_messages)
        if len(trimmed) != len(merged):
            self._overwrite_from_trimmed(handle, trimmed)

    @staticmethod
    def serialize_structured_output(value: object) -> str:
        return json.dumps(value, separators=(",", ":"), ensure_ascii=True, default=str)


chat_history_service = ChatHistoryService()

