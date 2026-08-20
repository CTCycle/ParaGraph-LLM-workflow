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
    supports_tool_selection: bool = False
    supports_native_tool_protocol: bool = False


@dataclass(frozen=True)
class ModelMetadata:
    provider: str
    model: str
    label: str
    supports_image: bool = False
    supports_embeddings: bool = False
    supports_reasoning: bool = False
    supports_structured_output: bool = True


@dataclass(frozen=True)
class HuggingFaceDownloadManifest:
    repo_id: str
    destination_path: str
    session_name: str


@dataclass(frozen=True)
class HuggingFaceDownloadProgress:
    status: str
    progress: float
    downloaded_bytes: int
    total_bytes: int | None
    message: str | None = None


@dataclass(frozen=True)
class HuggingFaceCatalogFilters:
    tasks: tuple[str, ...]
    libraries: tuple[str, ...]


@dataclass(frozen=True)
class HuggingFaceCatalogCachePayload:
    cache_key: str
    using_token: bool
