from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from ParaGraph.server.entities.nodecatalog import ProviderCapability, ProviderCatalogResponse
from ParaGraph.server.services.llm.providers import LLMError, OllamaError, select_llm_provider


class ChatProviderAdapter(Protocol):
    def chat(
        self,
        *,
        provider: str,
        model: str,
        messages: list[dict[str, Any]],
        response_format: str | None,
        options: dict[str, Any] | None,
    ) -> str: ...


@dataclass(frozen=True)
class ProviderMetadata:
    name: str
    supports_chat: bool
    supports_embeddings: bool
    supports_structured_output: bool
    supports_streaming: bool
    supports_tool_calling: bool


PROVIDER_CAPABILITIES = {
    "ollama": ProviderMetadata(
        name="ollama",
        supports_chat=True,
        supports_embeddings=True,
        supports_structured_output=True,
        supports_streaming=True,
        supports_tool_calling=False,
    ),
    "openai": ProviderMetadata(
        name="openai",
        supports_chat=True,
        supports_embeddings=True,
        supports_structured_output=True,
        supports_streaming=True,
        supports_tool_calling=True,
    ),
    "anthropic": ProviderMetadata(
        name="anthropic",
        supports_chat=True,
        supports_embeddings=False,
        supports_structured_output=True,
        supports_streaming=True,
        supports_tool_calling=True,
    ),
    "gemini": ProviderMetadata(
        name="gemini",
        supports_chat=True,
        supports_embeddings=True,
        supports_structured_output=False,
        supports_streaming=True,
        supports_tool_calling=True,
    ),
    "huggingface": ProviderMetadata(
        name="huggingface",
        supports_chat=True,
        supports_embeddings=True,
        supports_structured_output=False,
        supports_streaming=False,
        supports_tool_calling=False,
    ),
}


class ProviderService:
    def list_catalog(self) -> ProviderCatalogResponse:
        return ProviderCatalogResponse(
            providers=[
                ProviderCapability(
                    provider=metadata.name,
                    supports_chat=metadata.supports_chat,
                    supports_embeddings=metadata.supports_embeddings,
                    supports_structured_output=metadata.supports_structured_output,
                    supports_streaming=metadata.supports_streaming,
                    supports_tool_calling=metadata.supports_tool_calling,
                )
                for metadata in PROVIDER_CAPABILITIES.values()
            ]
        )

    def assert_capabilities(self, provider: str, *, structured_output: bool) -> None:
        metadata = PROVIDER_CAPABILITIES.get(provider)
        if metadata is None:
            raise ValueError(f"Unsupported provider: {provider}")
        if structured_output and not metadata.supports_structured_output:
            raise ValueError(f"Provider '{provider}' does not support structured output")

    def chat(
        self,
        *,
        provider: str,
        model: str,
        messages: list[dict[str, Any]],
        response_format: str | None = None,
        options: dict[str, Any] | None = None,
    ) -> str:
        normalized_provider = provider.lower().strip()
        try:
            client = select_llm_provider(normalized_provider)
            return client.chat(model=model, messages=messages, format=response_format, options=options)
        except (LLMError, OllamaError) as exc:
            raise ValueError(str(exc)) from exc


provider_service = ProviderService()
