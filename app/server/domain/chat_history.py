from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


ChatHistoryRole = Literal["system", "user", "assistant"]
ChatHistoryStorageBackend = Literal["file", "database"]

###############################################################################
class ChatHistoryMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: ChatHistoryRole
    content: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

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
