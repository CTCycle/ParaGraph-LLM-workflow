from __future__ import annotations

from threading import Lock
from typing import Any

import httpx
from server.contracts.configuration import DEFAULT_SESSION_NAME
from server.contracts.node_catalog import (
    HuggingFaceModelCatalogResponse,
    HuggingFaceSortBy,
    ModelVisibilityFilter,
    OllamaLibraryCatalogResponse,
    OllamaLibraryModelDefinition,
    OllamaModelPullResponse,
    ProviderCapability,
    ProviderCatalogResponse,
    ProviderModelCatalogResponse,
    ProviderModelDefinition,
)
from server.services.workflow.provider.models import (
    CachedValue,
    ModelMetadata,
)
from server.services.configuration import configuration_service
from server.services.llm.providers import (
    LLMError,
    OllamaClient,
    OllamaError,
    OpenAICompatibleLocalClient,
    select_llm_provider,
)
from server.services.workflow.provider.constants import (
    OLLAMA_LIBRARY_URL,
)
from server.services.workflow.provider.errors import ProviderApiError
from server.services.workflow.provider.helpers import (
    CURATED_MODELS,
    PROVIDER_CAPABILITIES,
    _infer_huggingface_metadata,
    _infer_openai_compatible_local_metadata,
    _infer_ollama_metadata,
    _model_basename,
    _normalize_provider,
)
from server.services.workflow.provider.huggingface_catalog import HuggingFaceCatalogMixin
from server.services.workflow.provider.huggingface_downloads import (
    HuggingFaceDownloadMixin,
)
from server.services.workflow.provider.ollama import OllamaLibraryCatalogMixin

###############################################################################
class ProviderService(
    OllamaLibraryCatalogMixin,
    HuggingFaceCatalogMixin,
    HuggingFaceDownloadMixin,
):

    # -------------------------------------------------------------------------
    def __init__(self) -> None:
        self._cache_lock = Lock()
        self._ollama_library_cache: CachedValue | None = None
        self._huggingface_cache: dict[str, CachedValue] = {}
        self._huggingface_filter_tags_cache: dict[str, CachedValue] = {}

    # -------------------------------------------------------------------------
    def reset_for_tests(self) -> None:
        with self._cache_lock:
            self._ollama_library_cache = None
            self._huggingface_cache.clear()
            self._huggingface_filter_tags_cache.clear()

    # -------------------------------------------------------------------------
    def _load_configuration(self, session_name: str = DEFAULT_SESSION_NAME):
        return configuration_service.load_configuration(session_name=session_name)

    # -------------------------------------------------------------------------
    def _get_access_key(self, provider: str, session_name: str = DEFAULT_SESSION_NAME):
        config = self._load_configuration(session_name)
        normalized_provider = _normalize_provider(provider)
        for item in config.access_keys:
            candidate = _normalize_provider(item.provider)
            if candidate == normalized_provider:
                return item
        return None

    # -------------------------------------------------------------------------
    def _ollama_client(self, session_name: str = DEFAULT_SESSION_NAME) -> OllamaClient:
        config = self._load_configuration(session_name)
        return OllamaClient(base_url=config.ollama.base_url)

    # -------------------------------------------------------------------------
    def list_catalog(self) -> ProviderCatalogResponse:
        ordered = [
            "ollama",
            "openai",
            "gemini",
            "claude",
            "deepseek",
            "huggingface",
            "lmstudio",
            "llama",
        ]
        return ProviderCatalogResponse(
            providers=[
                ProviderCapability(
                    provider=PROVIDER_CAPABILITIES[name].name,
                    supports_chat=PROVIDER_CAPABILITIES[name].supports_chat,
                    supports_embeddings=PROVIDER_CAPABILITIES[name].supports_embeddings,
                    supports_structured_output=PROVIDER_CAPABILITIES[
                        name
                    ].supports_structured_output,
                    supports_streaming=PROVIDER_CAPABILITIES[name].supports_streaming,
                    supports_tool_calling=PROVIDER_CAPABILITIES[
                        name
                    ].supports_tool_calling,
                    supports_tool_selection=PROVIDER_CAPABILITIES[
                        name
                    ].supports_tool_selection,
                    supports_native_tool_protocol=PROVIDER_CAPABILITIES[
                        name
                    ].supports_native_tool_protocol,
                )
                for name in ordered
            ]
        )

    # -------------------------------------------------------------------------
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
            raise ValueError(
                f"Provider '{provider}' does not support structured output"
            )
        if embeddings and not metadata.supports_embeddings:
            raise ValueError(f"Provider '{provider}' does not support embeddings")

    # -------------------------------------------------------------------------
    def list_models(
        self, session_name: str = DEFAULT_SESSION_NAME
    ) -> ProviderModelCatalogResponse:
        metadata_rows: list[ModelMetadata] = []
        metadata_rows.extend(self._ollama_models(session_name))
        metadata_rows.extend(CURATED_MODELS.get("ollama", ()))

        for provider in ("openai", "gemini", "claude", "deepseek"):
            metadata_rows.extend(CURATED_MODELS.get(provider, ()))

        metadata_rows.extend(CURATED_MODELS.get("huggingface", ()))
        metadata_rows.extend(self._downloaded_huggingface_models())
        for provider in ("lmstudio", "llama"):
            metadata_rows.extend(
                self._openai_compatible_local_models(provider, session_name)
            )
            metadata_rows.extend(CURATED_MODELS.get(provider, ()))

        deduped: dict[tuple[str, str], ModelMetadata] = {}
        for row in metadata_rows:
            key = (row.provider, row.model)
            if key not in deduped:
                deduped[key] = row

        return ProviderModelCatalogResponse(
            models=[self._to_model_definition(model) for model in deduped.values()]
        )

    # -------------------------------------------------------------------------
    def list_ollama_library_models(
        self,
        *,
        session_name: str = DEFAULT_SESSION_NAME,
        search: str | None = None,
        refresh: bool = False,
    ) -> OllamaLibraryCatalogResponse:
        return self._list_ollama_library_models_impl(
            session_name=session_name,
            search=search,
            refresh=refresh,
        )

    # -------------------------------------------------------------------------
    def pull_ollama_model(
        self,
        *,
        model: str,
        session_name: str = DEFAULT_SESSION_NAME,
    ) -> OllamaModelPullResponse:
        return self._pull_ollama_model_impl(model=model, session_name=session_name)

    # -------------------------------------------------------------------------
    def list_huggingface_models(
        self,
        *,
        session_name: str = DEFAULT_SESSION_NAME,
        search: str | None = None,
        task: str | None = None,
        library: str | None = None,
        author: str | None = None,
        visibility: ModelVisibilityFilter = "all",
        sort: HuggingFaceSortBy = "relevance",
        page: int = 1,
        page_size: int = 20,
        refresh: bool = False,
    ) -> HuggingFaceModelCatalogResponse:
        return self._list_huggingface_models_impl(
            session_name=session_name,
            search=search,
            task=task,
            library=library,
            author=author,
            visibility=visibility,
            sort=sort,
            page=page,
            page_size=page_size,
            refresh=refresh,
        )

    # -------------------------------------------------------------------------
    def _list_ollama_library_models_impl(
        self,
        *,
        session_name: str = DEFAULT_SESSION_NAME,
        search: str | None = None,
        refresh: bool = False,
    ) -> OllamaLibraryCatalogResponse:
        catalog = self._load_ollama_library_catalog(refresh=refresh)
        pulled_models = self._get_pulled_ollama_model_names(session_name)
        search_term = (search or "").strip().lower()

        models: list[OllamaLibraryModelDefinition] = []
        for model_name, description in catalog.models:
            if search_term:
                searchable = f"{model_name} {description or ''}".lower()
                if search_term not in searchable:
                    continue
            is_pulled = (
                model_name in pulled_models
                or _model_basename(model_name) in pulled_models
            )
            models.append(
                OllamaLibraryModelDefinition(
                    model=model_name,
                    description=description,
                    homepage=f"{OLLAMA_LIBRARY_URL}/{model_name}",
                    pulled=is_pulled,
                )
            )

        pulled_count = sum(1 for item in models if item.pulled)
        return OllamaLibraryCatalogResponse(
            models=models,
            total_count=len(models),
            pulled_count=pulled_count,
            refreshed_at=catalog.refreshed_at,
        )

    # -------------------------------------------------------------------------
    def _pull_ollama_model_impl(
        self,
        *,
        model: str,
        session_name: str = DEFAULT_SESSION_NAME,
    ) -> OllamaModelPullResponse:
        normalized_model = model.strip()
        if not normalized_model:
            raise ProviderApiError("Model name is required.", status_code=400)

        try:
            available = self._ollama_client(session_name).check_model_availability(
                normalized_model, auto_pull=True
            )
        except (ValueError, OllamaError) as exc:
            raise ProviderApiError(
                f"Unable to pull Ollama model '{normalized_model}': {exc}",
                status_code=503,
            ) from exc

        if not available:
            raise ProviderApiError(
                f"Ollama did not confirm availability for '{normalized_model}'.",
                status_code=502,
            )

        return OllamaModelPullResponse(
            ok=True,
            model=normalized_model,
            message=f"Model '{normalized_model}' is available in Ollama.",
        )

    # -------------------------------------------------------------------------
    def _ollama_models(
        self, session_name: str = DEFAULT_SESSION_NAME
    ) -> tuple[ModelMetadata, ...]:
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

    # -------------------------------------------------------------------------
    def _to_model_definition(
        self, metadata: ModelMetadata, timeout_s: float | None = None
    ) -> ProviderModelDefinition:
        return ProviderModelDefinition(
            provider=metadata.provider,
            model=metadata.model,
            label=metadata.label,
            supports_image=metadata.supports_image,
            supports_embeddings=metadata.supports_embeddings,
            supports_reasoning=metadata.supports_reasoning,
            supports_structured_output=metadata.supports_structured_output,
            timeout_s=timeout_s,
        )

    # -------------------------------------------------------------------------
    def build_model_definition(
        self,
        provider: str,
        model: str,
        timeout_s: float | None = None,
        session_name: str = DEFAULT_SESSION_NAME,
    ) -> ProviderModelDefinition:
        return self._to_model_definition(
            self.get_model_metadata(provider, model, session_name),
            timeout_s=timeout_s,
        )

    # -------------------------------------------------------------------------
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

        if normalized_provider == "huggingface":
            for item in self._downloaded_huggingface_models():
                if item.model == model:
                    return item

        if normalized_provider in {"lmstudio", "llama"}:
            for item in self._openai_compatible_local_models(
                normalized_provider, session_name
            ):
                if item.model == model:
                    return item

        for item in CURATED_MODELS.get(normalized_provider, ()):  # pragma: no branch
            if item.model == model:
                return item

        if normalized_provider == "huggingface":
            return _infer_huggingface_metadata(model)

        if normalized_provider in {"lmstudio", "llama"}:
            return _infer_openai_compatible_local_metadata(normalized_provider, model)

        raise ValueError(
            f"Unknown model '{model}' for provider '{normalized_provider}'"
        )

    # -------------------------------------------------------------------------
    def validate_model_request(
        self,
        *,
        provider: str,
        model: str,
        structured_output: bool,
        requires_image: bool,
        use_reasoning: bool,
        require_access_key: bool = True,
        session_name: str = DEFAULT_SESSION_NAME,
    ) -> None:
        normalized_provider = _normalize_provider(provider)
        self.assert_capabilities(
            normalized_provider, structured_output=structured_output
        )

        if require_access_key and normalized_provider in {
            "openai",
            "gemini",
            "claude",
            "deepseek",
        }:
            access_key = self._get_access_key(normalized_provider, session_name)
            if access_key is None or not access_key.api_key:
                raise ValueError(
                    f"Provider '{normalized_provider}' requires an access key in Configurations"
                )
        elif require_access_key and normalized_provider == "huggingface":
            if requires_image:
                raise ValueError(
                    "Provider 'huggingface' does not support image input in the current local runtime path"
                )
            is_local_model = model in self._downloaded_huggingface_repo_ids()
            if not is_local_model:
                access_key = self._get_access_key(normalized_provider, session_name)
                if access_key is None or not access_key.api_key:
                    raise ValueError(
                        "Provider 'huggingface' requires an access key in Configurations for remote models"
                    )

        if normalized_provider == "huggingface" and requires_image:
            raise ValueError(
                "Provider 'huggingface' does not support image input in the current local runtime path"
            )

        metadata = self.get_model_metadata(normalized_provider, model, session_name)
        if requires_image and not metadata.supports_image:
            raise ValueError(f"Model '{model}' does not support image input")
        if use_reasoning and not metadata.supports_reasoning:
            raise ValueError(f"Model '{model}' does not support reasoning mode")
        if structured_output and not metadata.supports_structured_output:
            raise ValueError(f"Model '{model}' does not support structured output")

    # -------------------------------------------------------------------------
    def chat(
        self,
        *,
        provider: str,
        model: str,
        messages: list[dict[str, Any]],
        response_format: str | None = None,
        options: dict[str, Any] | None = None,
        timeout_s: float | None = None,
        session_name: str = DEFAULT_SESSION_NAME,
    ) -> str:
        normalized_provider = _normalize_provider(provider)
        kwargs: dict[str, Any] = {}
        if timeout_s is not None:
            if timeout_s <= 0:
                raise ValueError("timeout_s must be greater than zero")
            kwargs["timeout_s"] = timeout_s
        if normalized_provider == "ollama":
            kwargs["base_url"] = self._load_configuration(session_name).ollama.base_url
        elif normalized_provider in {"openai", "gemini", "claude", "deepseek"}:
            access_key = self._get_access_key(normalized_provider, session_name)
            kwargs["api_key"] = access_key.api_key if access_key else None
            kwargs["base_url"] = access_key.base_url if access_key else None
        elif normalized_provider in {"lmstudio", "llama"}:
            access_key = self._get_access_key(normalized_provider, session_name)
            kwargs["api_key"] = access_key.api_key if access_key else None
            kwargs["base_url"] = access_key.base_url if access_key else None
        else:
            raise ValueError(f"Unsupported chat provider: {provider}")

        try:
            client = select_llm_provider(normalized_provider, **kwargs)
            return client.chat(
                model=model, messages=messages, format=response_format, options=options
            )
        except (LLMError, OllamaError) as exc:
            raise ValueError(str(exc)) from exc

    # -------------------------------------------------------------------------
    def supports_tool_selection(self, provider: str, model: str = "") -> bool:
        _ = model
        normalized_provider = _normalize_provider(provider)
        metadata = PROVIDER_CAPABILITIES.get(normalized_provider)
        return bool(metadata and metadata.supports_tool_selection)

    # -------------------------------------------------------------------------
    def supports_native_tool_protocol(self, provider: str, model: str = "") -> bool:
        _ = model
        normalized_provider = _normalize_provider(provider)
        metadata = PROVIDER_CAPABILITIES.get(normalized_provider)
        return bool(metadata and metadata.supports_native_tool_protocol)

    # -------------------------------------------------------------------------
    def supports_native_tools(self, provider: str, model: str = "") -> bool:
        """Compatibility alias for the explicit native protocol capability."""
        return self.supports_native_tool_protocol(provider, model)

    # -------------------------------------------------------------------------
    def supports_structured_output(self, provider: str, model: str = "") -> bool:
        _ = model
        normalized_provider = _normalize_provider(provider)
        metadata = PROVIDER_CAPABILITIES.get(normalized_provider)
        return bool(metadata and metadata.supports_structured_output)

    # -------------------------------------------------------------------------
    def chat_structured(
        self,
        *,
        provider: str,
        model: str,
        messages: list[dict[str, Any]],
        schema: dict[str, Any],
        options: dict[str, Any] | None = None,
        timeout_s: float | None = None,
        session_name: str = DEFAULT_SESSION_NAME,
    ) -> str:
        _ = schema
        return self.chat(
            provider=provider,
            model=model,
            messages=messages,
            response_format="json",
            options=options,
            timeout_s=timeout_s,
            session_name=session_name,
        )

    # -------------------------------------------------------------------------
    def chat_with_tools(
        self,
        *,
        provider: str,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        tool_choice: str = "auto",
        options: dict[str, Any] | None = None,
        timeout_s: float | None = None,
        session_name: str = DEFAULT_SESSION_NAME,
    ) -> dict[str, Any]:
        if not self.supports_native_tool_protocol(provider, model):
            raise ValueError(
                f"Provider '{provider}' does not support a native tool protocol"
            )
        raise NotImplementedError(
            "Native tool protocol adapters are not implemented for this provider"
        )

    # -------------------------------------------------------------------------
    def _ollama_embed(self, *, model: str, text: str, session_name: str) -> list[float]:
        base_url = self._load_configuration(session_name).ollama.base_url.rstrip("/")
        try:
            response = httpx.post(
                f"{base_url}/api/embed",
                json={"model": model, "input": text},
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()
            if isinstance(data, dict):
                embeddings = data.get("embeddings")
                if (
                    isinstance(embeddings, list)
                    and embeddings
                    and isinstance(embeddings[0], list)
                ):
                    return [float(item) for item in embeddings[0]]
            raise ValueError("Invalid Ollama embeddings response")
        except Exception as exc:  # noqa: BLE001
            raise ValueError(str(exc)) from exc

    # -------------------------------------------------------------------------
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
        base_url = (
            access_key.base_url
            if access_key and access_key.base_url
            else "https://api.openai.com/v1"
        ).rstrip("/")
        if not api_key:
            raise ValueError(
                "Provider 'openai' requires an access key in Configurations"
            )
        payload: dict[str, Any] = {"model": model, "input": text}
        if dimensions is not None:
            payload["dimensions"] = dimensions
        response = httpx.post(
            f"{base_url}/embeddings",
            json=payload,
            timeout=30.0,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )
        response.raise_for_status()
        data = response.json()
        items = data.get("data", []) if isinstance(data, dict) else []
        if (
            not items
            or not isinstance(items[0], dict)
            or not isinstance(items[0].get("embedding"), list)
        ):
            raise ValueError("Invalid OpenAI embeddings response")
        return [float(item) for item in items[0]["embedding"]]

    # -------------------------------------------------------------------------
    def _openai_compatible_local_models(
        self, provider: str, session_name: str = DEFAULT_SESSION_NAME
    ) -> tuple[ModelMetadata, ...]:
        access_key = self._get_access_key(provider, session_name)
        base_url = access_key.base_url if access_key else None
        api_key = access_key.api_key if access_key else None
        try:
            names = OpenAICompatibleLocalClient(
                provider=provider,
                base_url=base_url,
                api_key=api_key,
                timeout_s=2.0,
            ).list_models()
        except (ValueError, LLMError):
            names = []

        default_model = None
        if access_key and isinstance(access_key.metadata, dict):
            default_model = access_key.metadata.get("chat_model")
        if not names and isinstance(default_model, str) and default_model.strip():
            names = [default_model.strip()]
        return tuple(
            _infer_openai_compatible_local_metadata(provider, name) for name in names
        )

    # -------------------------------------------------------------------------
    def _openai_compatible_local_embed(
        self,
        *,
        provider: str,
        model: str,
        text: str,
        session_name: str,
        dimensions: int | None,
    ) -> list[float]:
        access_key = self._get_access_key(provider, session_name)
        return OpenAICompatibleLocalClient(
            provider=provider,
            base_url=access_key.base_url if access_key else None,
            api_key=access_key.api_key if access_key else None,
        ).embed(model=model, text=text, dimensions=dimensions)

    # -------------------------------------------------------------------------
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
                vector = self._ollama_embed(
                    model=model, text=text, session_name=session_name
                )
            elif normalized_provider == "openai":
                vector = self._openai_embed(
                    model=model,
                    text=text,
                    session_name=session_name,
                    dimensions=dimensions,
                )
            elif normalized_provider in {"lmstudio", "llama"}:
                vector = self._openai_compatible_local_embed(
                    provider=normalized_provider,
                    model=model,
                    text=text,
                    session_name=session_name,
                    dimensions=dimensions,
                )
            else:
                raise ValueError(f"Unsupported embedding provider: {normalized_provider}")
        except httpx.HTTPError as exc:
            raise ValueError(
                f"{normalized_provider} embeddings request failed: {exc}"
            ) from exc
        if dimensions is not None and len(vector) != dimensions:
            raise ValueError(
                f"Embedding dimension mismatch: expected {dimensions}, got {len(vector)}"
            )
        return vector


provider_service = ProviderService()
