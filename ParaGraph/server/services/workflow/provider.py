from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Any

import httpx

from ParaGraph.server.entities.configuration import DEFAULT_SESSION_NAME
from ParaGraph.server.entities.nodecatalog import (
    ProviderCapability,
    ProviderCatalogResponse,
    ProviderModelCatalogResponse,
    ProviderModelDefinition,
)
from ParaGraph.server.services.configuration import configuration_service
from ParaGraph.server.services.llm.providers import LLMError, OllamaClient, OllamaError, select_llm_provider


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
    "gemini": ProviderMetadata(
        name="gemini",
        supports_chat=True,
        supports_embeddings=True,
        supports_structured_output=True,
        supports_streaming=True,
        supports_tool_calling=True,
    ),
    "claude": ProviderMetadata(
        name="claude",
        supports_chat=True,
        supports_embeddings=False,
        supports_structured_output=True,
        supports_streaming=True,
        supports_tool_calling=True,
    ),
    "huggingface": ProviderMetadata(
        name="huggingface",
        supports_chat=True,
        supports_embeddings=True,
        supports_structured_output=True,
        supports_streaming=False,
        supports_tool_calling=False,
    ),
}


CURATED_MODELS: dict[str, tuple[ModelMetadata, ...]] = {
    "openai": (
        ModelMetadata(provider="openai", model="gpt-5.4", label="GPT-5.4", supports_image=True, supports_reasoning=True),
        ModelMetadata(provider="openai", model="gpt-5-mini", label="GPT-5 mini", supports_image=True, supports_reasoning=True),
        ModelMetadata(provider="openai", model="gpt-5-nano", label="GPT-5 nano", supports_image=True, supports_reasoning=True),
        ModelMetadata(provider="openai", model="gpt-4.1", label="GPT-4.1", supports_image=True),
    ),
    "gemini": (
        ModelMetadata(provider="gemini", model="gemini-3-pro-preview", label="Gemini 3 Pro Preview", supports_image=True, supports_reasoning=True),
        ModelMetadata(provider="gemini", model="gemini-3-flash-preview", label="Gemini 3 Flash Preview", supports_image=True, supports_reasoning=True),
        ModelMetadata(provider="gemini", model="gemini-2.5-pro", label="Gemini 2.5 Pro", supports_image=True, supports_reasoning=True),
        ModelMetadata(provider="gemini", model="gemini-2.5-flash", label="Gemini 2.5 Flash", supports_image=True, supports_reasoning=True),
        ModelMetadata(provider="gemini", model="gemini-2.5-flash-lite", label="Gemini 2.5 Flash-Lite", supports_image=True, supports_reasoning=True),
    ),
    "claude": (
        ModelMetadata(provider="claude", model="claude-opus-4-1-20250805", label="Claude Opus 4.1", supports_image=True, supports_reasoning=True),
        ModelMetadata(provider="claude", model="claude-sonnet-4-20250514", label="Claude Sonnet 4", supports_image=True, supports_reasoning=True),
        ModelMetadata(provider="claude", model="claude-3-7-sonnet-latest", label="Claude Sonnet 3.7", supports_image=True, supports_reasoning=True),
        ModelMetadata(provider="claude", model="claude-3-5-haiku-latest", label="Claude Haiku 3.5", supports_image=True),
    ),
    "huggingface": (
        ModelMetadata(provider="huggingface", model="meta-llama/Llama-3.2-3B-Instruct", label="Llama 3.2 3B Instruct"),
        ModelMetadata(provider="huggingface", model="Qwen/Qwen2.5-7B-Instruct", label="Qwen 2.5 7B Instruct"),
        ModelMetadata(provider="huggingface", model="deepseek-ai/DeepSeek-R1-Distill-Qwen-7B", label="DeepSeek R1 Distill Qwen 7B", supports_reasoning=True),
    ),
}


def _normalize_provider(provider: str) -> str:
    normalized = provider.lower().strip()
    if normalized == "anthropic":
        return "claude"
    return normalized


def _infer_ollama_metadata(model_name: str) -> ModelMetadata:
    normalized = model_name.lower()
    supports_image = any(token in normalized for token in ("llava", "vision", "bakllava", "moondream"))
    supports_reasoning = any(token in normalized for token in ("deepseek-r1", "qwq", "reason", "qwen3"))
    return ModelMetadata(
        provider="ollama",
        model=model_name,
        label=model_name,
        supports_image=supports_image,
        supports_reasoning=supports_reasoning,
        supports_structured_output=True,
    )


class ProviderService:
    def _load_configuration(self, session_name: str = DEFAULT_SESSION_NAME):
        return configuration_service.load_configuration(session_name=session_name)

    def _get_access_key(self, provider: str, session_name: str = DEFAULT_SESSION_NAME):
        config = self._load_configuration(session_name)
        normalized_provider = _normalize_provider(provider)
        for item in config.access_keys:
            candidate = _normalize_provider(item.provider)
            if candidate == normalized_provider:
                return item
        return None

    def _ollama_client(self, session_name: str = DEFAULT_SESSION_NAME) -> OllamaClient:
        config = self._load_configuration(session_name)
        return OllamaClient(base_url=config.ollama.base_url)

    def list_catalog(self) -> ProviderCatalogResponse:
        ordered = ["ollama", "openai", "gemini", "claude", "huggingface"]
        return ProviderCatalogResponse(
            providers=[
                ProviderCapability(
                    provider=PROVIDER_CAPABILITIES[name].name,
                    supports_chat=PROVIDER_CAPABILITIES[name].supports_chat,
                    supports_embeddings=PROVIDER_CAPABILITIES[name].supports_embeddings,
                    supports_structured_output=PROVIDER_CAPABILITIES[name].supports_structured_output,
                    supports_streaming=PROVIDER_CAPABILITIES[name].supports_streaming,
                    supports_tool_calling=PROVIDER_CAPABILITIES[name].supports_tool_calling,
                )
                for name in ordered
            ]
        )

    def assert_capabilities(
        self,
        provider: str,
        *,
        structured_output: bool = False,
        embeddings: bool = False,
    ) -> None:
        metadata = PROVIDER_CAPABILITIES.get(_normalize_provider(provider))
        if metadata is None:
            raise ValueError(f"Unsupported provider: {provider}")
        if structured_output and not metadata.supports_structured_output:
            raise ValueError(f"Provider '{provider}' does not support structured output")
        if embeddings and not metadata.supports_embeddings:
            raise ValueError(f"Provider '{provider}' does not support embeddings")

    def list_models(self, session_name: str = DEFAULT_SESSION_NAME) -> ProviderModelCatalogResponse:
        models: list[ProviderModelDefinition] = []
        for model in self._ollama_models(session_name):
            models.append(self._to_model_definition(model))
        for provider in ("openai", "gemini", "claude", "huggingface"):
            for model in CURATED_MODELS.get(provider, ()):  # pragma: no branch
                models.append(self._to_model_definition(model))
        return ProviderModelCatalogResponse(models=models)

    def _ollama_models(self, session_name: str = DEFAULT_SESSION_NAME) -> tuple[ModelMetadata, ...]:
        try:
            names = self._ollama_client(session_name).list_models()
        except ValueError:
            names = []
        except OllamaError:
            names = []

        if not names:
            config = self._load_configuration(session_name)
            fallback = config.ollama.chat_model.strip()
            if fallback:
                names = [fallback]
        return tuple(_infer_ollama_metadata(name) for name in names)

    def _to_model_definition(self, metadata: ModelMetadata) -> ProviderModelDefinition:
        return ProviderModelDefinition(
            provider=metadata.provider,
            model=metadata.model,
            label=metadata.label,
            supports_image=metadata.supports_image,
            supports_reasoning=metadata.supports_reasoning,
            supports_structured_output=metadata.supports_structured_output,
        )

    def build_model_definition(
        self,
        provider: str,
        model: str,
        session_name: str = DEFAULT_SESSION_NAME,
    ) -> ProviderModelDefinition:
        return self._to_model_definition(self.get_model_metadata(provider, model, session_name))

    def get_model_metadata(
        self,
        provider: str,
        model: str,
        session_name: str = DEFAULT_SESSION_NAME,
    ) -> ModelMetadata:
        normalized_provider = _normalize_provider(provider)
        if normalized_provider == "ollama":
            for item in self._ollama_models(session_name):
                if item.model == model:
                    return item
            return _infer_ollama_metadata(model)

        for item in CURATED_MODELS.get(normalized_provider, ()):  # pragma: no branch
            if item.model == model:
                return item
        raise ValueError(f"Unknown model '{model}' for provider '{normalized_provider}'")

    def validate_model_request(
        self,
        *,
        provider: str,
        model: str,
        structured_output: bool,
        requires_image: bool,
        use_reasoning: bool,
        session_name: str = DEFAULT_SESSION_NAME,
    ) -> None:
        normalized_provider = _normalize_provider(provider)
        self.assert_capabilities(normalized_provider, structured_output=structured_output)

        if normalized_provider in {"openai", "gemini", "claude", "huggingface"}:
            access_key = self._get_access_key(normalized_provider, session_name)
            if access_key is None or not access_key.api_key:
                raise ValueError(f"Provider '{normalized_provider}' requires an access key in Configurations")

        metadata = self.get_model_metadata(normalized_provider, model, session_name)
        if requires_image and not metadata.supports_image:
            raise ValueError(f"Model '{model}' does not support image input")
        if use_reasoning and not metadata.supports_reasoning:
            raise ValueError(f"Model '{model}' does not support reasoning mode")
        if structured_output and not metadata.supports_structured_output:
            raise ValueError(f"Model '{model}' does not support structured output")

    def chat(
        self,
        *,
        provider: str,
        model: str,
        messages: list[dict[str, Any]],
        response_format: str | None = None,
        options: dict[str, Any] | None = None,
        session_name: str = DEFAULT_SESSION_NAME,
    ) -> str:
        normalized_provider = _normalize_provider(provider)
        kwargs: dict[str, Any] = {}
        if normalized_provider == "ollama":
            kwargs["base_url"] = self._load_configuration(session_name).ollama.base_url
        elif normalized_provider in {"openai", "gemini", "claude"}:
            access_key = self._get_access_key(normalized_provider, session_name)
            kwargs["api_key"] = access_key.api_key if access_key else None
            kwargs["base_url"] = access_key.base_url if access_key else None
        else:
            raise ValueError(f"Unsupported chat provider: {provider}")

        try:
            client = select_llm_provider(normalized_provider, **kwargs)
            return client.chat(model=model, messages=messages, format=response_format, options=options)
        except (LLMError, OllamaError) as exc:
            raise ValueError(str(exc)) from exc

    def _fallback_embedding(self, *, provider: str, model: str, text: str, dimensions: int | None) -> list[float]:
        target_dimensions = dimensions or 12
        digest = hashlib.sha256(f"{provider}:{model}:{text}".encode("utf-8")).digest()
        values: list[float] = []
        for index in range(target_dimensions):
            start = (index * 2) % len(digest)
            chunk = int.from_bytes(digest[start:start + 2], byteorder="big", signed=False)
            values.append(round(chunk / 65535.0, 6))
        return values

    def _ollama_embed(self, *, model: str, text: str, session_name: str) -> list[float]:
        base_url = self._load_configuration(session_name).ollama.base_url.rstrip("/")
        payloads = (
            {"model": model, "input": text},
            {"model": model, "prompt": text},
        )
        last_error: Exception | None = None
        for path, payload in (("/api/embed", payloads[0]), ("/api/embeddings", payloads[1])):
            try:
                response = httpx.post(f"{base_url}{path}", json=payload, timeout=30.0)
                if response.status_code == 404:
                    continue
                response.raise_for_status()
                data = response.json()
                if isinstance(data, dict):
                    embeddings = data.get("embeddings")
                    if isinstance(embeddings, list) and embeddings and isinstance(embeddings[0], list):
                        return [float(item) for item in embeddings[0]]
                    embedding = data.get("embedding")
                    if isinstance(embedding, list):
                        return [float(item) for item in embedding]
                raise ValueError("Invalid Ollama embeddings response")
            except Exception as exc:  # noqa: BLE001
                last_error = exc
        raise ValueError(str(last_error or "Unable to generate Ollama embeddings"))

    def _openai_embed(
        self,
        *,
        model: str,
        text: str,
        session_name: str,
        dimensions: int | None,
    ) -> list[float]:
        access_key = self._get_access_key("openai", session_name)
        api_key = access_key.api_key if access_key else None
        base_url = (access_key.base_url if access_key and access_key.base_url else "https://api.openai.com/v1").rstrip("/")
        if not api_key:
            raise ValueError("Provider 'openai' requires an access key in Configurations")
        payload: dict[str, Any] = {"model": model, "input": text}
        if dimensions is not None:
            payload["dimensions"] = dimensions
        response = httpx.post(
            f"{base_url}/embeddings",
            json=payload,
            timeout=30.0,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        )
        response.raise_for_status()
        data = response.json()
        items = data.get("data", []) if isinstance(data, dict) else []
        if not items or not isinstance(items[0], dict) or not isinstance(items[0].get("embedding"), list):
            raise ValueError("Invalid OpenAI embeddings response")
        return [float(item) for item in items[0]["embedding"]]

    def embed_text(
        self,
        *,
        provider: str,
        model: str,
        text: str,
        dimensions: int | None = None,
        session_name: str = DEFAULT_SESSION_NAME,
    ) -> list[float]:
        normalized_provider = _normalize_provider(provider)
        self.assert_capabilities(normalized_provider, embeddings=True)
        try:
            if normalized_provider == "ollama":
                vector = self._ollama_embed(model=model, text=text, session_name=session_name)
            elif normalized_provider == "openai":
                vector = self._openai_embed(model=model, text=text, session_name=session_name, dimensions=dimensions)
            else:
                vector = self._fallback_embedding(provider=normalized_provider, model=model, text=text, dimensions=dimensions)
        except httpx.HTTPError as exc:
            raise ValueError(f"{normalized_provider} embeddings request failed: {exc}") from exc
        if dimensions is not None and len(vector) != dimensions:
            raise ValueError(f"Embedding dimension mismatch: expected {dimensions}, got {len(vector)}")
        return vector


provider_service = ProviderService()


