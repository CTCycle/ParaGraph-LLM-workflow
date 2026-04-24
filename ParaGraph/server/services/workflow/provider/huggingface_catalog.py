from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
from typing import Any

from huggingface_hub import HfApi
import httpx

from ParaGraph.server.common.utils.logger import logger
from ParaGraph.server.domain.node_catalog import HuggingFaceModelDefinition
from ParaGraph.server.domain.provider import CachedValue, ModelMetadata
from ParaGraph.server.services.workflow.provider.constants import (
    HUGGINGFACE_CACHE_TTL_SECONDS,
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
)
from ParaGraph.server.services.workflow.provider.errors import ProviderApiError
from ParaGraph.server.services.workflow.provider.helpers import (
    _coerce_optional_bool,
    _coerce_optional_text,
    _extract_huggingface_model_size,
    _extract_huggingface_tag_values,
    _huggingface_model_dir_name,
    _huggingface_repo_id_from_dir_name,
    _infer_huggingface_metadata,
    _payload_value,
    _resolve_visibility,
    _safe_int,
)
from ParaGraph.server.domain.configuration import DEFAULT_SESSION_NAME
from ParaGraph.server.domain.node_catalog import (
    HuggingFaceModelCatalogResponse,
    HuggingFaceSortBy,
    ModelVisibilityFilter,
)


class HuggingFaceCatalogMixin:
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
        normalized_visibility: ModelVisibilityFilter = (
            visibility if visibility in {"all", "public", "private", "gated"} else "all"
        )
        normalized_sort: HuggingFaceSortBy = (
            sort if sort in HUGGINGFACE_SORT_FIELD_MAP else "relevance"
        )

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

    def _read_huggingface_metadata(
        self, model_directory: Path
    ) -> dict[str, Any] | None:
        metadata_path = model_directory / HUGGINGFACE_LOCAL_MODEL_METADATA_FILE
        if not metadata_path.exists():
            return None

        try:
            payload = json.loads(metadata_path.read_text(encoding="utf-8"))
        except OSError, json.JSONDecodeError:
            return None

        if isinstance(payload, dict):
            return payload
        return None

    def _read_huggingface_repo_id_from_metadata(
        self, model_directory: Path
    ) -> str | None:
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
        if (
            metadata_downloaded_bytes is not None
            and metadata_downloaded_bytes != validated_bytes
        ):
            return False, repo_id, validated_bytes, expected_total_bytes

        total_bytes = (
            expected_total_bytes
            if expected_total_bytes is not None
            else validated_bytes
        )
        return True, repo_id, validated_bytes, total_bytes

    def _downloaded_huggingface_models(self) -> tuple[ModelMetadata, ...]:
        if not HUGGINGFACE_LOCAL_MODELS_ROOT.exists():
            return ()

        models: list[ModelMetadata] = []
        seen: set[str] = set()
        for item in sorted(
            HUGGINGFACE_LOCAL_MODELS_ROOT.iterdir(), key=lambda path: path.name.lower()
        ):
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
        token_fingerprint = (
            hashlib.sha256(token.encode("utf-8")).hexdigest()[:12] if token else "anon"
        )
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

    def _load_huggingface_cached_response(
        self, cache_key: str, *, refresh: bool
    ) -> HuggingFaceModelCatalogResponse | None:
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

    def _store_huggingface_cached_response(
        self, cache_key: str, payload: HuggingFaceModelCatalogResponse
    ) -> None:
        now = time.monotonic()
        expiry = now + HUGGINGFACE_CACHE_TTL_SECONDS
        with self._cache_lock:
            stale_keys = [
                key
                for key, value in self._huggingface_cache.items()
                if value.expires_at <= now
            ]
            for key in stale_keys:
                self._huggingface_cache.pop(key, None)
            self._huggingface_cache[cache_key] = CachedValue(
                value=payload.model_copy(deep=True), expires_at=expiry
            )

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

        permission_warning = self._detect_huggingface_permission_warning(
            api=api, token=token, search=search, rows=rows
        )
        if permission_warning:
            warning = (
                permission_warning
                if warning is None
                else f"{warning} {permission_warning}"
            )

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
        cache_key = hashlib.sha256((token or "anonymous").encode("utf-8")).hexdigest()[
            :12
        ]
        now = time.monotonic()

        if not refresh:
            with self._cache_lock:
                cached = self._huggingface_filter_tags_cache.get(cache_key)
                if (
                    cached
                    and cached.expires_at > now
                    and isinstance(cached.value, tuple)
                ):
                    cached_tasks, cached_libraries = cached.value
                    if isinstance(cached_tasks, tuple) and isinstance(
                        cached_libraries, tuple
                    ):
                        return cached_tasks, cached_libraries

        tasks = HUGGINGFACE_FALLBACK_TASKS
        libraries = HUGGINGFACE_FALLBACK_LIBRARIES
        try:
            tags_payload = api.get_model_tags()
            if isinstance(tags_payload, dict):
                extracted_tasks = _extract_huggingface_tag_values(
                    tags_payload.get("pipeline_tag")
                )
                extracted_libraries = _extract_huggingface_tag_values(
                    tags_payload.get("library")
                )
                if not extracted_libraries:
                    extracted_libraries = _extract_huggingface_tag_values(
                        tags_payload.get("library_name")
                    )
                if extracted_tasks:
                    tasks = extracted_tasks
                if extracted_libraries:
                    libraries = extracted_libraries
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Hugging Face tag discovery failed; using fallback tags (error_type=%s, request_id=%s).",
                type(exc).__name__,
                cache_key,
                exc_info=True,
            )

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

    def _parse_huggingface_model(
        self, payload: Any
    ) -> HuggingFaceModelDefinition | None:
        repo_id = _coerce_optional_text(
            _payload_value(payload, "id") or _payload_value(payload, "modelId")
        )
        if repo_id is None:
            return None

        author = _coerce_optional_text(_payload_value(payload, "author"))
        task = _coerce_optional_text(
            _payload_value(payload, "pipeline_tag")
            or _payload_value(payload, "pipelineTag")
        )
        library = _coerce_optional_text(
            _payload_value(payload, "library_name")
            or _payload_value(payload, "libraryName")
        )

        if library is None:
            tags = _payload_value(payload, "tags")
            if isinstance(tags, list):
                for item in tags:
                    text = _coerce_optional_text(item)
                    if text in {"transformers", "diffusers", "sentence-transformers"}:
                        library = text
                        break

        private = _coerce_optional_bool(_payload_value(payload, "private"))
        gated = _coerce_optional_bool(_payload_value(payload, "gated"))

        last_modified_raw = _payload_value(payload, "last_modified") or _payload_value(
            payload, "lastModified"
        )
        if isinstance(last_modified_raw, datetime):
            last_modified = last_modified_raw.astimezone(timezone.utc).isoformat()
        else:
            last_modified = _coerce_optional_text(last_modified_raw)

        return HuggingFaceModelDefinition(
            repo_id=repo_id,
            author=author,
            task=task,
            library=library,
            likes=_safe_int(_payload_value(payload, "likes")),
            downloads=_safe_int(_payload_value(payload, "downloads")),
            visibility=_resolve_visibility(private, gated),
            private=private,
            gated=gated,
            last_modified=last_modified,
            url=f"https://huggingface.co/{repo_id}",
            size_bytes=_extract_huggingface_model_size(payload),
        )

    def _visibility_matches(
        self, model_visibility: str, requested_visibility: ModelVisibilityFilter
    ) -> bool:
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


class HuggingFaceCatalogService:
    def __init__(self, provider_service: object) -> None:
        self._provider_service = provider_service

    def list_models(
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
        return self._provider_service._list_huggingface_models_impl(  # noqa: SLF001
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
