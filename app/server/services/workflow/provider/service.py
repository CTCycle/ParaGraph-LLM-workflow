from __future__ import annotations

import hashlib
from pathlib import Path
import shutil
from threading import Lock
import time
from typing import Any

from huggingface_hub import hf_hub_url
import httpx

from server.common.utils.logger import logger as logger
from server.configurations.startup import get_server_settings
from server.domain.configuration import DEFAULT_SESSION_NAME
from server.domain.node_catalog import (
    HuggingFaceModelCatalogResponse,
    HuggingFaceModelDownloadCancelResponse,
    HuggingFaceModelDownloadResponse,
    HuggingFaceModelDownloadStatusResponse,
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
from server.domain.provider import (
    CachedValue,
    ModelMetadata,
)
from server.services.jobs import job_manager
from server.services.configuration import configuration_service
from server.services.llm.providers import (
    LLMError,
    OllamaClient,
    OllamaError,
    select_llm_provider,
)
from server.services.workflow.provider.constants import (
    HUGGINGFACE_DOWNLOAD_JOB_TYPE,
    HUGGINGFACE_DOWNLOAD_TIMEOUT_SECONDS,
    OLLAMA_LIBRARY_URL,
)
from server.services.workflow.provider.errors import ProviderApiError
from server.services.workflow.provider.helpers import (
    CURATED_MODELS,
    PROVIDER_CAPABILITIES,
    _coerce_optional_text,
    _infer_huggingface_metadata,
    _infer_ollama_metadata,
    _model_basename,
    _normalize_huggingface_repo_id,
    _normalize_provider,
    _payload_value,
    _safe_int,
)
from server.services.workflow.provider.huggingface_catalog import (
    HuggingFaceCatalogMixin,
    HuggingFaceCatalogService,
)
from server.services.workflow.provider.huggingface_downloads import (
    HuggingFaceDownloadService,
)
from server.services.workflow.provider.ollama import (
    OllamaLibraryCatalogMixin,
    OllamaLibraryService,
)

class ProviderService(OllamaLibraryCatalogMixin, HuggingFaceCatalogMixin):
    def __init__(self) -> None:
        self._cache_lock = Lock()
        self._ollama_library_cache: CachedValue | None = None
        self._huggingface_cache: dict[str, CachedValue] = {}
        self._huggingface_filter_tags_cache: dict[str, CachedValue] = {}
        self.ollama_library = OllamaLibraryService(self)
        self.huggingface_catalog = HuggingFaceCatalogService(self)
        self.huggingface_downloads = HuggingFaceDownloadService(self)

    def reset_for_tests(self) -> None:
        with self._cache_lock:
            self._ollama_library_cache = None
            self._huggingface_cache.clear()
            self._huggingface_filter_tags_cache.clear()

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
                    supports_structured_output=PROVIDER_CAPABILITIES[
                        name
                    ].supports_structured_output,
                    supports_streaming=PROVIDER_CAPABILITIES[name].supports_streaming,
                    supports_tool_calling=PROVIDER_CAPABILITIES[
                        name
                    ].supports_tool_calling,
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
            raise ValueError(
                f"Provider '{provider}' does not support structured output"
            )
        if embeddings and not metadata.supports_embeddings:
            raise ValueError(f"Provider '{provider}' does not support embeddings")

    def list_models(
        self, session_name: str = DEFAULT_SESSION_NAME
    ) -> ProviderModelCatalogResponse:
        metadata_rows: list[ModelMetadata] = []
        metadata_rows.extend(self._ollama_models(session_name))
        metadata_rows.extend(CURATED_MODELS.get("ollama", ()))

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
        return self.huggingface_downloads.download_model(
            repo_id=repo_id, session_name=session_name
        )

    def get_huggingface_download_status(
        self, *, job_id: str
    ) -> HuggingFaceModelDownloadStatusResponse:
        return self.huggingface_downloads.get_download_status(job_id=job_id)

    def cancel_huggingface_download(
        self, *, job_id: str
    ) -> HuggingFaceModelDownloadCancelResponse:
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

    def _download_huggingface_model_impl(
        self,
        *,
        repo_id: str,
        session_name: str = DEFAULT_SESSION_NAME,
    ) -> HuggingFaceModelDownloadResponse:
        normalized_repo_id = _normalize_huggingface_repo_id(repo_id)
        destination = self._huggingface_local_model_path(normalized_repo_id)

        is_complete, _, downloaded_bytes, total_bytes = (
            self._is_huggingface_download_complete(
                destination,
                expected_repo_id=normalized_repo_id,
            )
        )
        if is_complete:
            resolved_total = (
                total_bytes if total_bytes is not None else downloaded_bytes
            )
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
                poll_interval=get_server_settings().jobs.polling_interval,
            )

        manifest = self._build_huggingface_download_manifest(
            repo_id=normalized_repo_id, session_name=session_name
        )
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
            poll_interval=get_server_settings().jobs.polling_interval,
        )

    def _get_huggingface_download_status_impl(
        self, *, job_id: str
    ) -> HuggingFaceModelDownloadStatusResponse:
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
            raise ProviderApiError(
                f"Download metadata unavailable for job: {job_id}", status_code=404
            )

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

    def _cancel_huggingface_download_impl(
        self, *, job_id: str
    ) -> HuggingFaceModelDownloadCancelResponse:
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


    def _build_huggingface_download_manifest(
        self, *, repo_id: str, session_name: str
    ) -> dict[str, Any]:
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
            relative_path = _coerce_optional_text(
                _payload_value(sibling, "rfilename")
                or _payload_value(sibling, "filename")
            )
            if not relative_path:
                continue

            size_bytes = _safe_int(_payload_value(sibling, "size"))
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
            file_total_bytes = (
                max(0, expected_size)
                if expected_size is not None and expected_size >= 0
                else None
            )
            last_emit_at = 0.0

            try:
                download_timeout = httpx.Timeout(HUGGINGFACE_DOWNLOAD_TIMEOUT_SECONDS)
                with httpx.stream(
                    "GET",
                    download_url,
                    headers=request_headers,
                    follow_redirects=True,
                    timeout=download_timeout,
                ) as response:
                    response.raise_for_status()
                    if file_total_bytes is None:
                        file_total_bytes = _safe_int(
                            response.headers.get("Content-Length")
                        )

                    with local_path.open("wb") as file_handle:
                        for chunk in response.iter_bytes(chunk_size=1024 * 1024):
                            if job_manager.should_stop(job_id):
                                self._cleanup_huggingface_download_directory(
                                    destination
                                )
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

        resolved_total_bytes = (
            safe_total_bytes if safe_total_bytes is not None else validated_bytes
        )
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

        raise ValueError(
            f"Unknown model '{model}' for provider '{normalized_provider}'"
        )

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
        self.assert_capabilities(
            normalized_provider, structured_output=structured_output
        )

        if normalized_provider in {"openai", "gemini", "claude"}:
            access_key = self._get_access_key(normalized_provider, session_name)
            if access_key is None or not access_key.api_key:
                raise ValueError(
                    f"Provider '{normalized_provider}' requires an access key in Configurations"
                )
        elif normalized_provider == "huggingface":
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
            return client.chat(
                model=model, messages=messages, format=response_format, options=options
            )
        except (LLMError, OllamaError) as exc:
            raise ValueError(str(exc)) from exc

    def _fallback_embedding(
        self, *, provider: str, model: str, text: str, dimensions: int | None
    ) -> list[float]:
        target_dimensions = dimensions or 12
        digest = hashlib.sha256(f"{provider}:{model}:{text}".encode("utf-8")).digest()
        values: list[float] = []
        for index in range(target_dimensions):
            start = (index * 2) % len(digest)
            chunk = int.from_bytes(
                digest[start : start + 2], byteorder="big", signed=False
            )
            values.append(round(chunk / 65535.0, 6))
        return values

    def _ollama_embed(self, *, model: str, text: str, session_name: str) -> list[float]:
        base_url = self._load_configuration(session_name).ollama.base_url.rstrip("/")
        payloads = (
            {"model": model, "input": text},
            {"model": model, "prompt": text},
        )
        last_error: Exception | None = None
        for path, payload in (
            ("/api/embed", payloads[0]),
            ("/api/embeddings", payloads[1]),
        ):
            try:
                response = httpx.post(f"{base_url}{path}", json=payload, timeout=30.0)
                if response.status_code == 404:
                    continue
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
            else:
                vector = self._fallback_embedding(
                    provider=normalized_provider,
                    model=model,
                    text=text,
                    dimensions=dimensions,
                )
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

