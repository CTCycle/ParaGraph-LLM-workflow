from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CachedValue:
    value: Any
    expires_at: float


@dataclass(frozen=True)
class OllamaLibraryCachePayload:
    models: tuple[tuple[str, str | None], ...]
    refreshed_at: str


@dataclass(frozen=True)
class ProviderMetadata:
    name: str
    supports_chat: bool
    supports_embeddings: bool
    supports_structured_output: bool
    supports_streaming: bool
    supports_tool_calling: bool


@dataclass(frozen=True)
class ModelMetadata:
    provider: str
    model: str
    label: str
    supports_image: bool = False
    supports_reasoning: bool = False
    supports_structured_output: bool = True
