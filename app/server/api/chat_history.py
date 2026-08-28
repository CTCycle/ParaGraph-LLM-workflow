from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from server.contracts.chat_history import (
    ChatHistoryHandle,
    ChatHistoryResponse,
    ChatHistoryStorageBackend,
)
from server.services.workflow.chat_history import chat_history_service


router = APIRouter(prefix="/chat-history", tags=["chat-history"])

###############################################################################
@router.get("", response_model=ChatHistoryResponse)
def get_chat_history(
    workflow_id: Annotated[str, Query(min_length=1, max_length=256)],
    execution_session_id: Annotated[str, Query(min_length=1, max_length=256)],
    node_id: Annotated[str, Query(min_length=1, max_length=256)],
    node_type: Annotated[
        str, Query(pattern="^CHAT_HISTORY_(MEMORY|PERSISTED)$")
    ],
    max_messages: Annotated[int, Query(ge=1, le=10_000)] = 20,
    separator: str = "\n",
    keep_prompt_type: bool = True,
    storage_backend: ChatHistoryStorageBackend | None = None,
) -> ChatHistoryResponse:
    handle = ChatHistoryHandle(
        node_type=node_type,  # type: ignore[arg-type]
        workflow_id=workflow_id,
        execution_session_id=execution_session_id,
        node_id=node_id,
        max_messages=max_messages,
        separator=separator,
        keep_prompt_type=keep_prompt_type,
        storage_backend=storage_backend,
    )
    return ChatHistoryResponse(messages=chat_history_service.load_messages(handle))

###############################################################################
@router.post("/reset", response_model=ChatHistoryResponse)
def reset_chat_history(handle: ChatHistoryHandle) -> ChatHistoryResponse:
    chat_history_service.clear_messages(handle)
    return ChatHistoryResponse()
