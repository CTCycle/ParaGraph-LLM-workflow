from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator

DEFAULT_SESSION_NAME = "default"


###############################################################################
class OllamaConfiguration(BaseModel):
    base_url: str = Field(default="http://127.0.0.1:11434", max_length=512)
    chat_model: str = Field(default="llama3.2", max_length=255)
    embedding_model: str = Field(default="nomic-embed-text", max_length=255)

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

    @field_validator("provider", mode="before")
    @classmethod
    def normalize_provider(cls, value: Any) -> str:
        return str(value or "").strip().lower()

    @field_validator("api_key", "base_url", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None


###############################################################################
class AppConfigurationPayload(BaseModel):
    session_name: str = Field(default=DEFAULT_SESSION_NAME, max_length=120)
    access_keys: list[AccessKeyConfiguration] = Field(default_factory=list)
    ollama: OllamaConfiguration = Field(default_factory=OllamaConfiguration)

    @field_validator("session_name", mode="before")
    @classmethod
    def normalize_session_name(cls, value: Any) -> str:
        text = str(value or "").strip()
        return text or DEFAULT_SESSION_NAME
