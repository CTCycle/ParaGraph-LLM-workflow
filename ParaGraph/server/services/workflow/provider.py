from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import inspect
from threading import Lock
import time
from typing import Any
from urllib.parse import unquote

from bs4 import BeautifulSoup
import httpx

from ParaGraph.server.entities.configuration import DEFAULT_SESSION_NAME
from ParaGraph.server.entities.nodecatalog import (
    HuggingFaceModelCatalogResponse,
    HuggingFaceModelDefinition,
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
from ParaGraph.server.services.configuration import configuration_service
from ParaGraph.server.services.llm.providers import LLMError, OllamaClient, OllamaError, select_llm_provider


OLLAMA_LIBRARY_URL = "https://ollama.com/library"
OLLAMA_LIBRARY_CACHE_TTL_SECONDS = 300.0
HUGGINGFACE_CACHE_TTL_SECONDS = 45.0
HUGGINGFACE_FILTER_TAGS_CACHE_TTL_SECONDS = 3600.0
HUGGINGFACE_MAX_FETCH_LIMIT = 500
HUGGINGFACE_MAX_PAGE_SIZE = 50

HUGGINGFACE_SORT_FIELD_MAP: dict[HuggingFaceSortBy, str | None] = {
    "relevance": None,
    "downloads": "downloads",
    "likes": "likes",
    "updated": "lastModified",
}

HUGGINGFACE_FALLBACK_TASKS: tuple[str, ...] = (
    "text-generation",
    "text-classification",
    "feature-extraction",
    "question-answering",
    "sentence-similarity",
    "token-classification",
    "summarization",
    "translation",
)

HUGGINGFACE_FALLBACK_LIBRARIES: tuple[str, ...] = (
    "transformers",
    "diffusers",
    "sentence-transformers",
    "gguf",
    "peft",
)


class ProviderApiError(RuntimeError):
    def __init__(self, message: str, *, status_code: int) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class CachedValue:
    value: Any
    expires_at: float


@dataclass(frozen=True)
class OllamaLibraryCachePayload:
    models: tuple[tuple[str, str | None], ...]
    refreshed_at: str


def _safe_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        text = value.strip()
        if text:
            try:
                return int(float(text))
            except ValueError:
                return None
    return None


def _coerce_optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _coerce_optional_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes"}:
            return True
        if normalized in {"false", "0", "no"}:
            return False
        return None
    if isinstance(value, (int, float)):
        return bool(value)
    return None


def _normalize_ollama_library_slug(href: str) -> str | None:
    if not href.startswith("/library/"):
        return None
    raw = href[len("/library/") :].strip()
    if not raw:
        return None
    raw = raw.split("?", 1)[0].split("#", 1)[0]
    segment = raw.split("/", 1)[0].strip()
    if not segment:
        return None
    slug = unquote(segment).strip().lower()
    if not slug or slug in {"library", "search"}:
        return None
    return slug


def _model_basename(model: str) -> str:
    return model.split(":", 1)[0].strip().lower()


def _resolve_visibility(private: bool | None, gated: bool | None) -> str:
    if gated is True:
        return "gated"
    if private is True:
        return "private"
    if private is False:
        return "public"
    return "unknown"

def _extract_huggingface_tag_values(payload: Any) -> tuple[str, ...]:
    values: set[str] = set()

    if isinstance(payload, dict):
        iterable = list(payload.values())
    elif isinstance(payload, list):
        iterable = payload
    else:
        iterable = []

    for item in iterable:
        candidate: str | None = None
        if isinstance(item, str):
            candidate = _coerce_optional_text(item)
        elif isinstance(item, dict):
            for key in ("id", "label", "name", "value"):
                candidate = _coerce_optional_text(item.get(key))
                if candidate:
                    break
        else:
            for attribute in ("id", "label", "name", "value"):
                candidate = _coerce_optional_text(getattr(item, attribute, None))
                if candidate:
                    break

        if candidate:
            values.add(candidate)

    return tuple(sorted(values))


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
    def __init__(self) -> None:
        self._cache_lock = Lock()
        self._ollama_library_cache: CachedValue | None = None
        self._huggingface_cache: dict[str, CachedValue] = {}
        self._huggingface_filter_tags_cache: dict[str, CachedValue] = {}

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

    def list_ollama_library_models(
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
            is_pulled = model_name in pulled_models or _model_basename(model_name) in pulled_models
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

    def pull_ollama_model(
        self,
        *,
        model: str,
        session_name: str = DEFAULT_SESSION_NAME,
    ) -> OllamaModelPullResponse:
        normalized_model = model.strip()
        if not normalized_model:
            raise ProviderApiError("Model name is required.", status_code=400)

        try:
            available = self._ollama_client(session_name).check_model_availability(normalized_model, auto_pull=True)
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
        page_size: int = 25,
        refresh: bool = False,
    ) -> HuggingFaceModelCatalogResponse:
        safe_page = max(1, page)
        safe_page_size = max(1, min(page_size, HUGGINGFACE_MAX_PAGE_SIZE))
        normalized_visibility: ModelVisibilityFilter = visibility if visibility in {"all", "public", "private", "gated"} else "all"
        normalized_sort: HuggingFaceSortBy = sort if sort in HUGGINGFACE_SORT_FIELD_MAP else "relevance"

        cache_key = self._build_huggingface_cache_key(
            session_name=session_name,
            search=search,
            task=task,
            library=library,
            author=author,
            visibility=normalized_visibility,
            sort=normalized_sort,
            page=safe_page,
            page_size=safe_page_size,
        )

        cached = self._load_huggingface_cached_response(cache_key, refresh=refresh)
        if cached is not None:
            return cached

        response = self._fetch_huggingface_models(
            session_name=session_name,
            search=search,
            task=task,
            library=library,
            author=author,
            visibility=normalized_visibility,
            sort=normalized_sort,
            page=safe_page,
            page_size=safe_page_size,
            refresh=refresh,
        )
        self._store_huggingface_cached_response(cache_key, response)
        return response

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

    def _load_ollama_library_catalog(self, *, refresh: bool) -> OllamaLibraryCachePayload:
        now = time.monotonic()
        with self._cache_lock:
            cached = self._ollama_library_cache
            if not refresh and cached and cached.expires_at > now:
                payload = cached.value
                if isinstance(payload, OllamaLibraryCachePayload):
                    return payload

        payload = self._fetch_ollama_library_catalog()
        with self._cache_lock:
            self._ollama_library_cache = CachedValue(
                value=payload,
                expires_at=time.monotonic() + OLLAMA_LIBRARY_CACHE_TTL_SECONDS,
            )
        return payload

    def _fetch_ollama_library_catalog(self) -> OllamaLibraryCachePayload:
        try:
            response = httpx.get(
                OLLAMA_LIBRARY_URL,
                timeout=20.0,
                follow_redirects=True,
                headers={"User-Agent": "ParaGraph/0.1"},
            )
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise ProviderApiError(
                "Timed out while fetching Ollama library models.",
                status_code=504,
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise ProviderApiError(
                f"Ollama library request failed ({exc.response.status_code}).",
                status_code=502,
            ) from exc
        except httpx.RequestError as exc:
            raise ProviderApiError(
                f"Unable to reach Ollama library: {exc}",
                status_code=503,
            ) from exc

        soup = BeautifulSoup(response.text, "html.parser")
        discovered: dict[str, str | None] = {}
        for anchor in soup.select('a[href^="/library/"]'):
            href = str(anchor.get("href") or "")
            slug = _normalize_ollama_library_slug(href)
            if not slug:
                continue
            label_text = anchor.get_text(" ", strip=True)
            description = label_text if label_text and label_text.lower() != slug else None
            discovered.setdefault(slug, description)

        if not discovered:
            raise ProviderApiError(
                "Unable to parse model rows from Ollama library response.",
                status_code=502,
            )

        ordered = tuple((name, discovered[name]) for name in sorted(discovered))
        refreshed_at = datetime.now(timezone.utc).isoformat()
        return OllamaLibraryCachePayload(models=ordered, refreshed_at=refreshed_at)

    def _get_pulled_ollama_model_names(self, session_name: str) -> set[str]:
        try:
            pulled = self._ollama_client(session_name).list_models()
        except (ValueError, OllamaError):
            return set()

        normalized: set[str] = set()
        for item in pulled:
            name = item.strip().lower()
            if not name:
                continue
            normalized.add(name)
            normalized.add(_model_basename(name))
        return normalized

    def _build_huggingface_cache_key(
        self,
        *,
        session_name: str,
        search: str | None,
        task: str | None,
        library: str | None,
        author: str | None,
        visibility: ModelVisibilityFilter,
        sort: HuggingFaceSortBy,
        page: int,
        page_size: int,
    ) -> str:
        token = self._get_huggingface_token(session_name)
        token_fingerprint = hashlib.sha256(token.encode("utf-8")).hexdigest()[:12] if token else "anon"
        return "|".join(
            [
                session_name.strip(),
                token_fingerprint,
                (search or "").strip().lower(),
                (task or "").strip().lower(),
                (library or "").strip().lower(),
                (author or "").strip().lower(),
                visibility,
                sort,
                str(page),
                str(page_size),
            ]
        )

    def _load_huggingface_cached_response(self, cache_key: str, *, refresh: bool) -> HuggingFaceModelCatalogResponse | None:
        if refresh:
            return None

        now = time.monotonic()
        with self._cache_lock:
            cached = self._huggingface_cache.get(cache_key)
            if not cached or cached.expires_at <= now:
                return None
            payload = cached.value
            if not isinstance(payload, HuggingFaceModelCatalogResponse):
                return None
            return payload.model_copy(deep=True)

    def _store_huggingface_cached_response(self, cache_key: str, payload: HuggingFaceModelCatalogResponse) -> None:
        now = time.monotonic()
        expiry = now + HUGGINGFACE_CACHE_TTL_SECONDS
        with self._cache_lock:
            stale_keys = [key for key, value in self._huggingface_cache.items() if value.expires_at <= now]
            for key in stale_keys:
                self._huggingface_cache.pop(key, None)
            self._huggingface_cache[cache_key] = CachedValue(value=payload.model_copy(deep=True), expires_at=expiry)

    def _fetch_huggingface_models(
        self,
        *,
        session_name: str,
        search: str | None,
        task: str | None,
        library: str | None,
        author: str | None,
        visibility: ModelVisibilityFilter,
        sort: HuggingFaceSortBy,
        page: int,
        page_size: int,
        refresh: bool,
    ) -> HuggingFaceModelCatalogResponse:
        api, token = self._resolve_huggingface_api(session_name)

        skip = (page - 1) * page_size
        limit = max(skip + page_size + 1, page_size + 1)
        if visibility == "private":
            limit = max(limit, (skip + page_size + 1) * 2)
        limit = min(limit, HUGGINGFACE_MAX_FETCH_LIMIT)

        kwargs = self._build_huggingface_list_kwargs(
            api,
            token=token,
            search=search,
            task=task,
            library=library,
            author=author,
            visibility=visibility,
            sort=sort,
            limit=limit,
        )

        try:
            iterator = api.list_models(**kwargs)
        except Exception as exc:  # noqa: BLE001
            raise self._translate_huggingface_error(exc) from exc

        rows: list[HuggingFaceModelDefinition] = []
        visible_index = 0
        has_more = False
        for item in iterator:
            parsed = self._parse_huggingface_model(item)
            if parsed is None:
                continue
            if not self._visibility_matches(parsed.visibility, visibility):
                continue

            if visible_index < skip:
                visible_index += 1
                continue

            if len(rows) >= page_size:
                has_more = True
                break

            rows.append(parsed)
            visible_index += 1

        warning: str | None = None
        if visibility in {"private", "gated"} and not token:
            warning = "Configure a Hugging Face token in Configurations to access private or gated models."

        permission_warning = self._detect_huggingface_permission_warning(api=api, token=token, search=search, rows=rows)
        if permission_warning:
            warning = permission_warning if warning is None else f"{warning} {permission_warning}"

        filter_tasks, filter_libraries = self._load_huggingface_filter_tags(
            api=api,
            token=token,
            refresh=refresh,
        )
        available_tasks = set(filter_tasks)
        available_libraries = set(filter_libraries)

        for item in rows:
            if item.task:
                available_tasks.add(item.task)
            if item.library:
                available_libraries.add(item.library)

        normalized_task = _coerce_optional_text(task)
        normalized_library = _coerce_optional_text(library)
        if normalized_task:
            available_tasks.add(normalized_task)
        if normalized_library:
            available_libraries.add(normalized_library)

        return HuggingFaceModelCatalogResponse(
            models=rows,
            page=page,
            page_size=page_size,
            has_more=has_more,
            using_token=bool(token),
            warning=warning,
            available_tasks=sorted(available_tasks),
            available_libraries=sorted(available_libraries),
        )

    def _load_huggingface_filter_tags(
        self,
        *,
        api: Any,
        token: str | None,
        refresh: bool,
    ) -> tuple[tuple[str, ...], tuple[str, ...]]:
        cache_key = hashlib.sha256((token or "anonymous").encode("utf-8")).hexdigest()[:12]
        now = time.monotonic()

        if not refresh:
            with self._cache_lock:
                cached = self._huggingface_filter_tags_cache.get(cache_key)
                if cached and cached.expires_at > now and isinstance(cached.value, tuple):
                    cached_tasks, cached_libraries = cached.value
                    if isinstance(cached_tasks, tuple) and isinstance(cached_libraries, tuple):
                        return cached_tasks, cached_libraries

        tasks = HUGGINGFACE_FALLBACK_TASKS
        libraries = HUGGINGFACE_FALLBACK_LIBRARIES
        try:
            tags_payload = api.get_model_tags()
            if isinstance(tags_payload, dict):
                extracted_tasks = _extract_huggingface_tag_values(tags_payload.get("pipeline_tag"))
                extracted_libraries = _extract_huggingface_tag_values(tags_payload.get("library"))
                if not extracted_libraries:
                    extracted_libraries = _extract_huggingface_tag_values(tags_payload.get("library_name"))
                if extracted_tasks:
                    tasks = extracted_tasks
                if extracted_libraries:
                    libraries = extracted_libraries
        except Exception:
            # Keep deterministic fallback options if tag discovery fails.
            pass

        with self._cache_lock:
            self._huggingface_filter_tags_cache[cache_key] = CachedValue(
                value=(tasks, libraries),
                expires_at=time.monotonic() + HUGGINGFACE_FILTER_TAGS_CACHE_TTL_SECONDS,
            )

        return tasks, libraries

    def _build_huggingface_list_kwargs(
        self,
        api: Any,
        *,
        token: str | None,
        search: str | None,
        task: str | None,
        library: str | None,
        author: str | None,
        visibility: ModelVisibilityFilter,
        sort: HuggingFaceSortBy,
        limit: int,
    ) -> dict[str, Any]:
        signature = inspect.signature(api.list_models)
        parameters = signature.parameters
        kwargs: dict[str, Any] = {}

        normalized_search = _coerce_optional_text(search)
        normalized_task = _coerce_optional_text(task)
        normalized_library = _coerce_optional_text(library)
        normalized_author = _coerce_optional_text(author)

        if normalized_search and "search" in parameters:
            kwargs["search"] = normalized_search
        if normalized_author and "author" in parameters:
            kwargs["author"] = normalized_author

        fallback_filters: list[str] = []
        if normalized_task:
            if "pipeline_tag" in parameters:
                kwargs["pipeline_tag"] = normalized_task
            else:
                fallback_filters.append(normalized_task)

        if normalized_library:
            if "library" in parameters:
                kwargs["library"] = normalized_library
            else:
                fallback_filters.append(normalized_library)

        if fallback_filters and "filter" in parameters:
            kwargs["filter"] = fallback_filters if len(fallback_filters) > 1 else fallback_filters[0]

        sort_field = HUGGINGFACE_SORT_FIELD_MAP.get(sort)
        if sort_field and "sort" in parameters:
            kwargs["sort"] = sort_field
            if "direction" in parameters:
                kwargs["direction"] = -1

        if visibility in {"gated", "public"} and "gated" in parameters:
            kwargs["gated"] = visibility == "gated"

        if "full" in parameters:
            kwargs["full"] = True
        if "limit" in parameters:
            kwargs["limit"] = limit
        if token and "token" in parameters:
            kwargs["token"] = token

        return kwargs

    def _parse_huggingface_model(self, payload: Any) -> HuggingFaceModelDefinition | None:
        if isinstance(payload, dict):
            read = payload.get
        else:
            read = lambda key: getattr(payload, key, None)

        repo_id = _coerce_optional_text(read("id") or read("modelId"))
        if repo_id is None:
            return None

        author = _coerce_optional_text(read("author"))
        task = _coerce_optional_text(read("pipeline_tag") or read("pipelineTag"))
        library = _coerce_optional_text(read("library_name") or read("libraryName"))

        if library is None:
            tags = read("tags")
            if isinstance(tags, list):
                for item in tags:
                    text = _coerce_optional_text(item)
                    if text in {"transformers", "diffusers", "sentence-transformers"}:
                        library = text
                        break

        private = _coerce_optional_bool(read("private"))
        gated = _coerce_optional_bool(read("gated"))

        last_modified_raw = read("last_modified") or read("lastModified")
        if isinstance(last_modified_raw, datetime):
            last_modified = last_modified_raw.astimezone(timezone.utc).isoformat()
        else:
            last_modified = _coerce_optional_text(last_modified_raw)

        return HuggingFaceModelDefinition(
            repo_id=repo_id,
            author=author,
            task=task,
            library=library,
            likes=_safe_int(read("likes")),
            downloads=_safe_int(read("downloads")),
            visibility=_resolve_visibility(private, gated),
            private=private,
            gated=gated,
            last_modified=last_modified,
            url=f"https://huggingface.co/{repo_id}",
        )

    def _visibility_matches(self, model_visibility: str, requested_visibility: ModelVisibilityFilter) -> bool:
        if requested_visibility == "all":
            return True
        return model_visibility == requested_visibility

    def _get_huggingface_token(self, session_name: str) -> str | None:
        access_key = self._get_access_key("huggingface", session_name)
        if access_key is None or not access_key.api_key:
            return None
        token = access_key.api_key.strip()
        return token or None

    def _resolve_huggingface_api(self, session_name: str) -> tuple[Any, str | None]:
        token = self._get_huggingface_token(session_name)
        try:
            from huggingface_hub import HfApi
        except ImportError as exc:
            raise ProviderApiError(
                "Hugging Face integration requires the 'huggingface_hub' dependency.",
                status_code=503,
            ) from exc
        return HfApi(token=token), token

    def _detect_huggingface_permission_warning(
        self,
        *,
        api: Any,
        token: str | None,
        search: str | None,
        rows: list[HuggingFaceModelDefinition],
    ) -> str | None:
        if rows:
            return None

        candidate = (search or "").strip()
        if not candidate or " " in candidate or "/" not in candidate:
            return None

        signature = inspect.signature(api.model_info)
        parameters = signature.parameters
        kwargs: dict[str, Any] = {}
        if token and "token" in parameters:
            kwargs["token"] = token

        try:
            api.model_info(candidate, **kwargs)
            return None
        except Exception as exc:  # noqa: BLE001
            status_code = self._extract_status_code(exc)
            if status_code in {401, 403}:
                return "The requested repository exists but is unavailable with the current Hugging Face permissions."
            if status_code == 429:
                return "Hugging Face rate limit reached while validating repository visibility."
            return None

    def _extract_status_code(self, error: Exception) -> int | None:
        response = getattr(error, "response", None)
        status_code = getattr(response, "status_code", None)
        if isinstance(status_code, int):
            return status_code
        return None

    def _translate_huggingface_error(self, error: Exception) -> ProviderApiError:
        status_code = self._extract_status_code(error)
        if status_code == 401:
            return ProviderApiError(
                "Hugging Face authentication failed. Check the configured token.",
                status_code=401,
            )
        if status_code == 403:
            return ProviderApiError(
                "Hugging Face request was denied. The model may be private or gated.",
                status_code=403,
            )
        if status_code == 429:
            return ProviderApiError(
                "Hugging Face API rate limit reached. Retry shortly.",
                status_code=429,
            )

        if isinstance(error, httpx.TimeoutException):
            return ProviderApiError(
                "Hugging Face request timed out.",
                status_code=504,
            )
        if isinstance(error, httpx.RequestError):
            return ProviderApiError(
                f"Unable to reach Hugging Face: {error}",
                status_code=503,
            )

        return ProviderApiError(
            f"Hugging Face query failed: {error}",
            status_code=502,
        )


provider_service = ProviderService()
