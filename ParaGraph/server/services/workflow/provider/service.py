from __future__ import annotations

from datetime import datetime, timezone
import json
import hashlib
from pathlib import Path
import re
import shutil
from threading import Lock
import time
from typing import Any
from urllib.parse import unquote

from bs4 import BeautifulSoup
from huggingface_hub import HfApi, hf_hub_url
import httpx

from ParaGraph.server.configurations.server import server_settings
from ParaGraph.server.domain.configuration import DEFAULT_SESSION_NAME
from ParaGraph.server.domain.node_catalog import (
    HuggingFaceModelCatalogResponse,
    HuggingFaceModelDownloadCancelResponse,
    HuggingFaceModelDownloadResponse,
    HuggingFaceModelDownloadStatusResponse,
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
from ParaGraph.server.domain.provider import (
    CachedValue,
    ModelMetadata,
    OllamaLibraryCachePayload,
    ProviderMetadata,
)
from ParaGraph.server.services.jobs import job_manager
from ParaGraph.server.services.configuration import configuration_service
from ParaGraph.server.services.llm.providers import LLMError, OllamaClient, OllamaError, select_llm_provider
from ParaGraph.server.services.workflow.provider.constants import (
    HUGGINGFACE_CACHE_TTL_SECONDS,
    HUGGINGFACE_DOWNLOAD_JOB_TYPE,
    HUGGINGFACE_FALLBACK_LIBRARIES,
    HUGGINGFACE_FALLBACK_TASKS,
    HUGGINGFACE_FILTER_TAGS_CACHE_TTL_SECONDS,
    HUGGINGFACE_LOCAL_MODEL_METADATA_FILE,
    HUGGINGFACE_LOCAL_MODELS_ROOT,
    HUGGINGFACE_MAX_FETCH_LIMIT,
    HUGGINGFACE_MAX_PAGE_SIZE,
    HUGGINGFACE_MODEL_LIST_EXPAND_FIELDS,
    HUGGINGFACE_REPO_ID_PATTERN,
    HUGGINGFACE_SORT_FIELD_MAP,
    OLLAMA_LIBRARY_CACHE_TTL_SECONDS,
    OLLAMA_LIBRARY_URL,
)
from ParaGraph.server.services.workflow.provider.errors import ProviderApiError
from ParaGraph.server.services.workflow.provider.huggingface_catalog import HuggingFaceCatalogService
from ParaGraph.server.services.workflow.provider.huggingface_downloads import HuggingFaceDownloadService
from ParaGraph.server.services.workflow.provider.ollama import OllamaLibraryService


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


def _normalize_huggingface_repo_id(repo_id: str) -> str:
    normalized = repo_id.strip().strip("/")
    if not normalized or not HUGGINGFACE_REPO_ID_PATTERN.fullmatch(normalized):
        raise ProviderApiError(
            "Invalid Hugging Face repository id. Use the format 'namespace/model'.",
            status_code=400,
        )
    return normalized


def _huggingface_model_dir_name(repo_id: str) -> str:
    return repo_id.replace("/", "--")


def _huggingface_repo_id_from_dir_name(value: str) -> str | None:
    if "--" not in value:
        return None
    candidate = value.replace("--", "/")
    if not HUGGINGFACE_REPO_ID_PATTERN.fullmatch(candidate):
        return None
    return candidate


def _resolve_visibility(private: bool | None, gated: bool | None) -> str:
    if gated is True:
        return "gated"
    if private is True:
        return "private"
    if private is False:
        return "public"
    return "unknown"


def _extract_huggingface_model_size(payload: Any) -> int | None:
    if isinstance(payload, dict):
        read = payload.get
    else:
        read = lambda key: getattr(payload, key, None)

    for key in ("size", "model_size", "total_size", "usedStorage"):
        candidate = _safe_int(read(key))
        if candidate is not None and candidate >= 0:
            return candidate

    safetensors = read("safetensors")
    if isinstance(safetensors, dict):
        total = _safe_int(safetensors.get("total") or safetensors.get("total_size") or safetensors.get("size"))
        if total is not None and total >= 0:
            return total

    siblings = read("siblings")
    if isinstance(siblings, list) and siblings:
        total_bytes = 0
        found_size = False
        for sibling in siblings:
            if isinstance(sibling, dict):
                size_value = _safe_int(sibling.get("size"))
            else:
                size_value = _safe_int(getattr(sibling, "size", None))
            if size_value is None or size_value < 0:
                continue
            found_size = True
            total_bytes += size_value
        if found_size:
            return total_bytes

    return None


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


def _infer_huggingface_metadata(repo_id: str) -> ModelMetadata:
    normalized = repo_id.lower()
    supports_image = any(token in normalized for token in ("vision", "vl", "llava", "pixtral", "moondream"))
    supports_reasoning = any(token in normalized for token in ("reason", "r1", "r2", "qwq", "o1", "o3"))
    return ModelMetadata(
        provider="huggingface",
        model=repo_id,
        label=repo_id,
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
        self.ollama_library = OllamaLibraryService(self)
        self.huggingface_catalog = HuggingFaceCatalogService(self)
        self.huggingface_downloads = HuggingFaceDownloadService(self)

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
        metadata_rows: list[ModelMetadata] = []
        metadata_rows.extend(self._ollama_models(session_name))

        for provider in ("openai", "gemini", "claude"):
            metadata_rows.extend(CURATED_MODELS.get(provider, ()))

        metadata_rows.extend(CURATED_MODELS.get("huggingface", ()))
        metadata_rows.extend(self._downloaded_huggingface_models())

        deduped: dict[tuple[str, str], ModelMetadata] = {}
        for row in metadata_rows:
            key = (row.provider, row.model)
            if key not in deduped:
                deduped[key] = row

        return ProviderModelCatalogResponse(
            models=[self._to_model_definition(model) for model in deduped.values()]
        )

    def list_ollama_library_models(
        self,
        *,
        session_name: str = DEFAULT_SESSION_NAME,
        search: str | None = None,
        refresh: bool = False,
    ) -> OllamaLibraryCatalogResponse:
        return self.ollama_library.list_models(
            session_name=session_name,
            search=search,
            refresh=refresh,
        )

    def pull_ollama_model(
        self,
        *,
        model: str,
        session_name: str = DEFAULT_SESSION_NAME,
    ) -> OllamaModelPullResponse:
        return self.ollama_library.pull_model(model=model, session_name=session_name)

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
        return self.huggingface_catalog.list_models(
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

    def download_huggingface_model(
        self,
        *,
        repo_id: str,
        session_name: str = DEFAULT_SESSION_NAME,
    ) -> HuggingFaceModelDownloadResponse:
        return self.huggingface_downloads.download_model(repo_id=repo_id, session_name=session_name)

    def get_huggingface_download_status(self, *, job_id: str) -> HuggingFaceModelDownloadStatusResponse:
        return self.huggingface_downloads.get_download_status(job_id=job_id)

    def cancel_huggingface_download(self, *, job_id: str) -> HuggingFaceModelDownloadCancelResponse:
        return self.huggingface_downloads.cancel_download(job_id=job_id)

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

    def _download_huggingface_model_impl(
        self,
        *,
        repo_id: str,
        session_name: str = DEFAULT_SESSION_NAME,
    ) -> HuggingFaceModelDownloadResponse:
        normalized_repo_id = _normalize_huggingface_repo_id(repo_id)
        destination = self._huggingface_local_model_path(normalized_repo_id)

        is_complete, _, downloaded_bytes, total_bytes = self._is_huggingface_download_complete(
            destination,
            expected_repo_id=normalized_repo_id,
        )
        if is_complete:
            resolved_total = total_bytes if total_bytes is not None else downloaded_bytes
            return HuggingFaceModelDownloadResponse(
                ok=True,
                repo_id=normalized_repo_id,
                message=f"Hugging Face model '{normalized_repo_id}' is already downloaded.",
                destination_path=str(destination),
                already_downloaded=True,
                job_id=None,
                status="completed",
                progress=100.0,
                downloaded_bytes=downloaded_bytes,
                total_bytes=resolved_total,
                poll_interval=server_settings.jobs.polling_interval,
            )

        manifest = self._build_huggingface_download_manifest(repo_id=normalized_repo_id, session_name=session_name)
        manifest_total_bytes = _safe_int(manifest.get("total_bytes"))
        manifest_files = manifest.get("files")
        if not isinstance(manifest_files, list) or not manifest_files:
            raise ProviderApiError(
                f"Hugging Face repository '{normalized_repo_id}' has no downloadable files.",
                status_code=502,
            )

        self._reset_huggingface_download_directory(destination)
        self._write_huggingface_model_metadata(
            normalized_repo_id,
            destination,
            complete=False,
            files=manifest_files,
            total_bytes=manifest_total_bytes,
            downloaded_bytes=0,
            revision=_coerce_optional_text(manifest.get("revision")),
        )

        job_id = job_manager.start_job(
            job_type=HUGGINGFACE_DOWNLOAD_JOB_TYPE,
            runner=self._run_huggingface_download_job,
            kwargs={
                "repo_id": normalized_repo_id,
                "token": _coerce_optional_text(manifest.get("token")),
                "destination_path": str(destination),
                "files": manifest_files,
                "total_bytes": manifest_total_bytes,
                "revision": _coerce_optional_text(manifest.get("revision")),
            },
        )

        job_manager.update_result(
            job_id,
            {
                "repo_id": normalized_repo_id,
                "destination_path": str(destination),
                "downloaded_bytes": 0,
                "total_bytes": manifest_total_bytes,
                "message": f"Starting download for '{normalized_repo_id}'.",
            },
        )

        return HuggingFaceModelDownloadResponse(
            ok=True,
            repo_id=normalized_repo_id,
            message=f"Started download for Hugging Face model '{normalized_repo_id}'.",
            destination_path=str(destination),
            already_downloaded=False,
            job_id=job_id,
            status="running",
            progress=0.0,
            downloaded_bytes=0,
            total_bytes=manifest_total_bytes,
            poll_interval=server_settings.jobs.polling_interval,
        )

    def _get_huggingface_download_status_impl(self, *, job_id: str) -> HuggingFaceModelDownloadStatusResponse:
        payload = job_manager.get_job_status(job_id)
        if payload is None:
            raise ProviderApiError(f"Download job not found: {job_id}", status_code=404)

        if payload.get("job_type") != HUGGINGFACE_DOWNLOAD_JOB_TYPE:
            raise ProviderApiError(f"Download job not found: {job_id}", status_code=404)

        status = str(payload.get("status") or "failed")
        if status not in {"pending", "running", "completed", "failed", "cancelled"}:
            status = "failed"

        result_payload = payload.get("result")
        result = result_payload if isinstance(result_payload, dict) else {}

        repo_id = _coerce_optional_text(result.get("repo_id"))
        if not repo_id:
            raise ProviderApiError(f"Download metadata unavailable for job: {job_id}", status_code=404)

        destination_path = _coerce_optional_text(result.get("destination_path"))
        if destination_path is None:
            destination_path = str(self._huggingface_local_model_path(repo_id))

        downloaded_bytes = max(0, _safe_int(result.get("downloaded_bytes")) or 0)
        total_bytes = _safe_int(result.get("total_bytes"))

        raw_progress = payload.get("progress")
        if isinstance(raw_progress, (int, float)):
            progress = min(100.0, max(0.0, float(raw_progress)))
        else:
            progress = 0.0

        message = _coerce_optional_text(result.get("message"))
        error = _coerce_optional_text(payload.get("error"))

        return HuggingFaceModelDownloadStatusResponse(
            job_id=job_id,
            repo_id=repo_id,
            destination_path=destination_path,
            status=status,
            progress=progress,
            message=message,
            downloaded_bytes=downloaded_bytes,
            total_bytes=total_bytes,
            error=error,
        )

    def _cancel_huggingface_download_impl(self, *, job_id: str) -> HuggingFaceModelDownloadCancelResponse:
        status = self.get_huggingface_download_status(job_id=job_id)
        success = job_manager.cancel_job(job_id)
        if not success:
            raise ProviderApiError(
                f"Download job '{job_id}' cannot be cancelled.",
                status_code=409,
            )

        return HuggingFaceModelDownloadCancelResponse(
            ok=True,
            job_id=job_id,
            repo_id=status.repo_id,
            message=f"Cancellation requested for '{status.repo_id}'.",
        )

    def _list_huggingface_models_impl(
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

    def _build_huggingface_download_manifest(self, *, repo_id: str, session_name: str) -> dict[str, Any]:
        api, token = self._resolve_huggingface_api(session_name)
        model_info_kwargs: dict[str, Any] = {"files_metadata": True}
        if token:
            model_info_kwargs["token"] = token

        try:
            info = api.model_info(repo_id, **model_info_kwargs)
        except Exception as exc:  # noqa: BLE001
            raise self._translate_huggingface_error(exc) from exc

        siblings = getattr(info, "siblings", None)
        manifest_files: list[dict[str, Any]] = []
        total_known_bytes = 0
        has_unknown_size = False

        for sibling in siblings or []:
            if isinstance(sibling, dict):
                read = sibling.get
            else:
                read = lambda key: getattr(sibling, key, None)

            relative_path = _coerce_optional_text(read("rfilename") or read("filename"))
            if not relative_path:
                continue

            size_bytes = _safe_int(read("size"))
            if size_bytes is None:
                has_unknown_size = True
            else:
                total_known_bytes += max(0, size_bytes)

            manifest_files.append({"path": relative_path, "size": size_bytes})

        if not manifest_files:
            raise ProviderApiError(
                f"Hugging Face repository '{repo_id}' has no downloadable files.",
                status_code=502,
            )

        revision = _coerce_optional_text(getattr(info, "sha", None))
        total_bytes = total_known_bytes if not has_unknown_size else None
        return {
            "repo_id": repo_id,
            "files": manifest_files,
            "total_bytes": total_bytes,
            "revision": revision,
            "token": token,
        }

    def _run_huggingface_download_job(
        self,
        *,
        repo_id: str,
        token: str | None,
        destination_path: str,
        files: list[dict[str, Any]],
        total_bytes: int | None,
        revision: str | None,
        job_id: str,
    ) -> dict[str, Any]:
        destination = Path(destination_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.mkdir(parents=True, exist_ok=True)

        downloaded_bytes = 0
        safe_total_bytes = _safe_int(total_bytes)
        total_files = len(files)

        for index, file_info in enumerate(files):
            if job_manager.should_stop(job_id):
                self._cleanup_huggingface_download_directory(destination)
                job_manager.update_result(
                    job_id,
                    {
                        "repo_id": repo_id,
                        "destination_path": destination_path,
                        "downloaded_bytes": downloaded_bytes,
                        "total_bytes": safe_total_bytes,
                        "message": f"Download cancelled for '{repo_id}'.",
                    },
                )
                return {}

            relative_path = _coerce_optional_text(file_info.get("path"))
            if not relative_path:
                continue

            expected_size = _safe_int(file_info.get("size"))
            local_path = destination / relative_path
            local_path.parent.mkdir(parents=True, exist_ok=True)

            try:
                download_url = hf_hub_url(
                    repo_id=repo_id,
                    filename=relative_path,
                    repo_type="model",
                    revision=revision,
                )
            except Exception as exc:  # noqa: BLE001
                raise self._translate_huggingface_error(exc) from exc

            request_headers: dict[str, str] = {}
            if token:
                request_headers["Authorization"] = f"Bearer {token}"

            file_downloaded_bytes = 0
            file_total_bytes = max(0, expected_size) if expected_size is not None and expected_size >= 0 else None
            last_emit_at = 0.0

            try:
                with httpx.stream("GET", download_url, headers=request_headers, follow_redirects=True, timeout=None) as response:
                    response.raise_for_status()
                    if file_total_bytes is None:
                        file_total_bytes = _safe_int(response.headers.get("Content-Length"))

                    with local_path.open("wb") as file_handle:
                        for chunk in response.iter_bytes(chunk_size=1024 * 1024):
                            if job_manager.should_stop(job_id):
                                self._cleanup_huggingface_download_directory(destination)
                                job_manager.update_result(
                                    job_id,
                                    {
                                        "repo_id": repo_id,
                                        "destination_path": destination_path,
                                        "downloaded_bytes": downloaded_bytes,
                                        "total_bytes": safe_total_bytes,
                                        "message": f"Download cancelled for '{repo_id}'.",
                                    },
                                )
                                return {}

                            if not chunk:
                                continue

                            file_handle.write(chunk)
                            chunk_bytes = len(chunk)
                            file_downloaded_bytes += chunk_bytes
                            downloaded_bytes += chunk_bytes

                            now = time.monotonic()
                            if now - last_emit_at < 0.25:
                                continue

                            file_progress = (
                                file_downloaded_bytes / file_total_bytes
                                if file_total_bytes is not None and file_total_bytes > 0
                                else 0.0
                            )
                            progress = self._calculate_huggingface_download_progress(
                                downloaded_bytes=downloaded_bytes,
                                total_bytes=safe_total_bytes,
                                completed_files=index,
                                total_files=total_files,
                                active_file_progress=file_progress,
                            )
                            job_manager.update_result(
                                job_id,
                                {
                                    "repo_id": repo_id,
                                    "destination_path": destination_path,
                                    "downloaded_bytes": downloaded_bytes,
                                    "total_bytes": safe_total_bytes,
                                    "message": f"Downloading '{repo_id}' ({index + 1}/{total_files} files).",
                                },
                            )
                            job_manager.update_progress(job_id, progress)
                            last_emit_at = now
            except httpx.HTTPError as exc:
                raise self._translate_huggingface_error(exc) from exc
            except OSError as exc:
                raise ProviderApiError(
                    f"Unable to save Hugging Face model '{repo_id}': {exc}",
                    status_code=500,
                ) from exc

            progress = self._calculate_huggingface_download_progress(
                downloaded_bytes=downloaded_bytes,
                total_bytes=safe_total_bytes,
                completed_files=index + 1,
                total_files=total_files,
            )
            job_manager.update_result(
                job_id,
                {
                    "repo_id": repo_id,
                    "destination_path": destination_path,
                    "downloaded_bytes": downloaded_bytes,
                    "total_bytes": safe_total_bytes,
                    "message": f"Downloading '{repo_id}' ({index + 1}/{total_files} files).",
                },
            )
            job_manager.update_progress(job_id, progress)

        if job_manager.should_stop(job_id):
            self._cleanup_huggingface_download_directory(destination)
            job_manager.update_result(
                job_id,
                {
                    "repo_id": repo_id,
                    "destination_path": destination_path,
                    "downloaded_bytes": downloaded_bytes,
                    "total_bytes": safe_total_bytes,
                    "message": f"Download cancelled for '{repo_id}'.",
                },
            )
            return {}

        complete, validated_bytes = self._validate_huggingface_download_files(
            destination,
            files=files,
            expected_total_bytes=safe_total_bytes,
        )
        if not complete:
            raise ProviderApiError(
                f"Downloaded files for '{repo_id}' did not pass integrity validation.",
                status_code=500,
            )

        resolved_total_bytes = safe_total_bytes if safe_total_bytes is not None else validated_bytes
        self._write_huggingface_model_metadata(
            repo_id,
            destination,
            complete=True,
            files=files,
            total_bytes=resolved_total_bytes,
            downloaded_bytes=validated_bytes,
            revision=revision,
        )

        with self._cache_lock:
            self._huggingface_cache.clear()

        message = f"Downloaded Hugging Face model '{repo_id}' to local storage."
        job_manager.update_result(
            job_id,
            {
                "repo_id": repo_id,
                "destination_path": destination_path,
                "downloaded_bytes": validated_bytes,
                "total_bytes": resolved_total_bytes,
                "message": message,
            },
        )

        return {
            "repo_id": repo_id,
            "destination_path": destination_path,
            "downloaded_bytes": validated_bytes,
            "total_bytes": resolved_total_bytes,
            "message": message,
        }

    def _calculate_huggingface_download_progress(
        self,
        *,
        downloaded_bytes: int,
        total_bytes: int | None,
        completed_files: int,
        total_files: int,
        active_file_progress: float = 0.0,
    ) -> float:
        if total_bytes is not None and total_bytes > 0:
            ratio = downloaded_bytes / total_bytes
            return min(99.5, max(0.0, ratio * 100.0))

        if total_files <= 0:
            return 0.0

        bounded_active_file_progress = min(1.0, max(0.0, active_file_progress))
        ratio = (completed_files + bounded_active_file_progress) / total_files
        return min(99.5, max(0.0, ratio * 100.0))

    def _reset_huggingface_download_directory(self, destination: Path) -> None:
        if destination.exists():
            shutil.rmtree(destination, ignore_errors=True)
        destination.mkdir(parents=True, exist_ok=True)

    def _cleanup_huggingface_download_directory(self, destination: Path) -> None:
        if destination.exists():
            shutil.rmtree(destination, ignore_errors=True)

    def _validate_huggingface_download_files(
        self,
        destination: Path,
        *,
        files: list[dict[str, Any]],
        expected_total_bytes: int | None,
    ) -> tuple[bool, int]:
        total_bytes = 0
        for file_info in files:
            relative_path = _coerce_optional_text(file_info.get("path"))
            if not relative_path:
                continue

            local_path = destination / relative_path
            if not local_path.is_file():
                return False, total_bytes

            try:
                size_on_disk = local_path.stat().st_size
            except OSError:
                return False, total_bytes

            expected_size = _safe_int(file_info.get("size"))
            if expected_size is not None and size_on_disk != max(0, expected_size):
                return False, total_bytes

            total_bytes += max(0, size_on_disk)

        if expected_total_bytes is not None and total_bytes < expected_total_bytes:
            return False, total_bytes

        return True, total_bytes

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

    def _to_model_definition(self, metadata: ModelMetadata, timeout_s: float | None = None) -> ProviderModelDefinition:
        return ProviderModelDefinition(
            provider=metadata.provider,
            model=metadata.model,
            label=metadata.label,
            supports_image=metadata.supports_image,
            supports_reasoning=metadata.supports_reasoning,
            supports_structured_output=metadata.supports_structured_output,
            timeout_s=timeout_s,
        )

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

        for item in CURATED_MODELS.get(normalized_provider, ()):  # pragma: no branch
            if item.model == model:
                return item

        if normalized_provider == "huggingface":
            return _infer_huggingface_metadata(model)

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

        if normalized_provider in {"openai", "gemini", "claude"}:
            access_key = self._get_access_key(normalized_provider, session_name)
            if access_key is None or not access_key.api_key:
                raise ValueError(f"Provider '{normalized_provider}' requires an access key in Configurations")
        elif normalized_provider == "huggingface":
            is_local_model = model in self._downloaded_huggingface_repo_ids()
            if not is_local_model:
                access_key = self._get_access_key(normalized_provider, session_name)
                if access_key is None or not access_key.api_key:
                    raise ValueError("Provider 'huggingface' requires an access key in Configurations for remote models")

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

    def _huggingface_local_model_path(self, repo_id: str) -> Path:
        return HUGGINGFACE_LOCAL_MODELS_ROOT / _huggingface_model_dir_name(repo_id)

    def _write_huggingface_model_metadata(
        self,
        repo_id: str,
        destination: Path,
        *,
        complete: bool,
        files: list[dict[str, Any]] | None = None,
        total_bytes: int | None = None,
        downloaded_bytes: int | None = None,
        revision: str | None = None,
    ) -> None:
        payload: dict[str, Any] = {
            "repo_id": repo_id,
            "downloaded_at": datetime.now(timezone.utc).isoformat(),
            "complete": complete,
        }
        if revision:
            payload["revision"] = revision
        if files is not None:
            normalized_files: list[dict[str, Any]] = []
            for item in files:
                path_value = _coerce_optional_text(item.get("path"))
                if not path_value:
                    continue
                normalized_files.append(
                    {
                        "path": path_value,
                        "size": _safe_int(item.get("size")),
                    }
                )
            payload["files"] = normalized_files
        if total_bytes is not None:
            payload["total_bytes"] = max(0, total_bytes)
        if downloaded_bytes is not None:
            payload["downloaded_bytes"] = max(0, downloaded_bytes)

        destination.mkdir(parents=True, exist_ok=True)
        metadata_path = destination / HUGGINGFACE_LOCAL_MODEL_METADATA_FILE
        metadata_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _read_huggingface_metadata(self, model_directory: Path) -> dict[str, Any] | None:
        metadata_path = model_directory / HUGGINGFACE_LOCAL_MODEL_METADATA_FILE
        if not metadata_path.exists():
            return None

        try:
            payload = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

        if isinstance(payload, dict):
            return payload
        return None

    def _read_huggingface_repo_id_from_metadata(self, model_directory: Path) -> str | None:
        payload = self._read_huggingface_metadata(model_directory)
        if isinstance(payload, dict):
            candidate = _coerce_optional_text(payload.get("repo_id"))
            if candidate and HUGGINGFACE_REPO_ID_PATTERN.fullmatch(candidate):
                return candidate

        fallback = _huggingface_repo_id_from_dir_name(model_directory.name)
        return fallback

    def _is_huggingface_download_complete(
        self,
        model_directory: Path,
        *,
        expected_repo_id: str | None = None,
    ) -> tuple[bool, str | None, int, int | None]:
        payload = self._read_huggingface_metadata(model_directory)
        repo_id = self._read_huggingface_repo_id_from_metadata(model_directory)

        if expected_repo_id is not None and repo_id != expected_repo_id:
            return False, repo_id, 0, None

        if not isinstance(payload, dict):
            return False, repo_id, 0, None

        if payload.get("complete") is not True:
            return False, repo_id, 0, None

        files_payload = payload.get("files")
        files = files_payload if isinstance(files_payload, list) else []
        if not files:
            return False, repo_id, 0, None

        expected_total_bytes = _safe_int(payload.get("total_bytes"))
        valid, validated_bytes = self._validate_huggingface_download_files(
            model_directory,
            files=files,
            expected_total_bytes=expected_total_bytes,
        )
        if not valid:
            return False, repo_id, 0, expected_total_bytes

        metadata_downloaded_bytes = _safe_int(payload.get("downloaded_bytes"))
        if metadata_downloaded_bytes is not None and metadata_downloaded_bytes != validated_bytes:
            return False, repo_id, validated_bytes, expected_total_bytes

        total_bytes = expected_total_bytes if expected_total_bytes is not None else validated_bytes
        return True, repo_id, validated_bytes, total_bytes

    def _downloaded_huggingface_models(self) -> tuple[ModelMetadata, ...]:
        if not HUGGINGFACE_LOCAL_MODELS_ROOT.exists():
            return ()

        models: list[ModelMetadata] = []
        seen: set[str] = set()
        for item in sorted(HUGGINGFACE_LOCAL_MODELS_ROOT.iterdir(), key=lambda path: path.name.lower()):
            if not item.is_dir():
                continue

            is_complete, repo_id, _, _ = self._is_huggingface_download_complete(item)
            if not is_complete or not repo_id or repo_id in seen:
                continue

            seen.add(repo_id)
            models.append(_infer_huggingface_metadata(repo_id))

        return tuple(models)

    def _downloaded_huggingface_repo_ids(self) -> set[str]:
        return {item.model for item in self._downloaded_huggingface_models()}

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
        downloaded_repo_ids = self._downloaded_huggingface_repo_ids()
        visible_index = 0
        has_more = False
        for item in iterator:
            parsed = self._parse_huggingface_model(item)
            if parsed is None:
                continue
            parsed.downloaded = parsed.repo_id in downloaded_repo_ids
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
        _ = api
        kwargs: dict[str, Any] = {}
        normalized_search = _coerce_optional_text(search)
        normalized_task = _coerce_optional_text(task)
        normalized_library = _coerce_optional_text(library)
        normalized_author = _coerce_optional_text(author)

        if normalized_search:
            kwargs["search"] = normalized_search
        if normalized_author:
            kwargs["author"] = normalized_author

        if normalized_task:
            kwargs["pipeline_tag"] = normalized_task

        if normalized_library:
            kwargs["library"] = normalized_library

        sort_field = HUGGINGFACE_SORT_FIELD_MAP.get(sort)
        if sort_field:
            kwargs["sort"] = sort_field
            kwargs["direction"] = -1

        if visibility in {"gated", "public"}:
            kwargs["gated"] = visibility == "gated"

        kwargs["expand"] = list(HUGGINGFACE_MODEL_LIST_EXPAND_FIELDS)
        kwargs["limit"] = limit
        if token:
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
            size_bytes=_extract_huggingface_model_size(payload),
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

        try:
            if token:
                api.model_info(candidate, token=token)
            else:
                api.model_info(candidate)
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
        if status_code == 404:
            return ProviderApiError(
                "Hugging Face repository was not found.",
                status_code=404,
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



