from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


ChatHistoryRole = Literal["system", "user", "assistant"]
ChatHistoryStorageBackend = Literal["file", "database"]
DEFAULT_CHAT_HISTORY_STORAGE_BACKEND: ChatHistoryStorageBackend = "file"


###############################################################################
def utc_now() -> datetime:
    return datetime.now(timezone.utc)

###############################################################################
class ChatHistoryMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: ChatHistoryRole
    content: str
    timestamp: datetime = Field(default_factory=utc_now)

###############################################################################
class ChatHistoryHandle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_type: Literal["CHAT_HISTORY_MEMORY", "CHAT_HISTORY_PERSISTED"]
    node_id: str
    workflow_id: str
    execution_session_id: str
    max_messages: int = Field(ge=1)
    separator: str
    keep_prompt_type: bool
    storage_backend: ChatHistoryStorageBackend | None = None
