from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field, field_validator

DEFAULT_SESSION_NAME = "default"
SESSION_NAME_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._-]{0,119}$"
PROFILE_NAME_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._ -]{0,119}$"
MASKED_API_KEY_VALUE = "__PG_MASKED_API_KEY__"


###############################################################################
class OllamaConfiguration(BaseModel):
    base_url: str = Field(default="http://127.0.0.1:11434", max_length=512)
    chat_model: str = Field(default="llama3.2", max_length=255)
    embedding_model: str = Field(default="nomic-embed-text", max_length=255)

    # -------------------------------------------------------------------------
    @field_validator("base_url", "chat_model", "embedding_model", mode="before")
    @classmethod
    def normalize_required_text(cls, value: Any) -> str:
        text = str(value or "").strip()
        return text


###############################################################################
class AccessKeyConfiguration(BaseModel):
    provider: str = Field(min_length=2, max_length=64)
    api_key: str | None = Field(default=None, max_length=1024)
    base_url: str | None = Field(default=None, max_length=512)
    metadata: dict[str, Any] = Field(default_factory=dict)

    # -------------------------------------------------------------------------
    @field_validator("provider", mode="before")
    @classmethod
    def normalize_provider(cls, value: Any) -> str:
        return str(value or "").strip().lower()

    # -------------------------------------------------------------------------
    @field_validator("api_key", "base_url", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None


###############################################################################
def is_masked_api_key(value: str | None) -> bool:
    if value is None:
        return False
    normalized = value.strip()
    return normalized in {MASKED_API_KEY_VALUE, "********"}


###############################################################################
class AppConfigurationPayload(BaseModel):
    session_name: str = Field(default=DEFAULT_SESSION_NAME, max_length=120)
    access_keys: list[AccessKeyConfiguration] = Field(default_factory=list)
    ollama: OllamaConfiguration = Field(default_factory=OllamaConfiguration)

    # -------------------------------------------------------------------------
    @field_validator("session_name", mode="before")
    @classmethod
    def normalize_session_name(cls, value: Any) -> str:
        text = str(value or "").strip()
        normalized = text or DEFAULT_SESSION_NAME
        if not re.fullmatch(SESSION_NAME_PATTERN, normalized):
            raise ValueError(
                "session_name may include only letters, numbers, dot, underscore, and dash"
            )
        return normalized


###############################################################################
class ConfigurationProfileSummary(BaseModel):
    profile_name: str
    created_at: str
    updated_at: str


###############################################################################
class ConfigurationProfileListResponse(BaseModel):
    session_name: str = Field(default=DEFAULT_SESSION_NAME, max_length=120)
    profiles: list[ConfigurationProfileSummary] = Field(default_factory=list)


###############################################################################
class OllamaPingRequest(BaseModel):
    base_url: str | None = Field(default=None, max_length=512)

    # -------------------------------------------------------------------------
    @field_validator("base_url", mode="before")
    @classmethod
    def normalize_base_url(cls, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None


###############################################################################
class OllamaStatusResponse(BaseModel):
    ok: bool
    message: str
    base_url: str
    model_count: int = 0


###############################################################################
class ProviderPingRequest(BaseModel):
    provider: str = Field(min_length=2, max_length=64)
    base_url: str | None = Field(default=None, max_length=512)
    api_key: str | None = Field(default=None, max_length=1024)

    # -------------------------------------------------------------------------
    @field_validator("provider", mode="before")
    @classmethod
    def normalize_provider(cls, value: Any) -> str:
        return str(value or "").strip().lower()

    # -------------------------------------------------------------------------
    @field_validator("base_url", "api_key", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None


###############################################################################
class ProviderStatusResponse(BaseModel):
    ok: bool
    provider: str
    message: str
    base_url: str
    model_count: int = 0
