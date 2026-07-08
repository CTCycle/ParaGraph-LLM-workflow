from __future__ import annotations

from pathlib import Path
import shutil
import time
from typing import Any

from huggingface_hub import hf_hub_url
import httpx

from server.configurations.startup import get_server_settings
from server.domain.configuration import DEFAULT_SESSION_NAME
from server.domain.node_catalog import (
    HuggingFaceModelDownloadCancelResponse,
    HuggingFaceModelDownloadResponse,
    HuggingFaceModelDownloadStatusResponse,
)
from server.services.jobs import job_manager
from server.services.workflow.provider.constants import (
    HUGGINGFACE_DOWNLOAD_JOB_TYPE,
    HUGGINGFACE_DOWNLOAD_TIMEOUT_SECONDS,
)
from server.services.workflow.provider.errors import ProviderApiError
from server.services.workflow.provider.helpers import (
    _coerce_optional_text,
    _normalize_huggingface_repo_id,
    _payload_value,
    _safe_int,
)

###############################################################################
class HuggingFaceDownloadMixin:

    # -------------------------------------------------------------------------
    def download_huggingface_model(
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

    # -------------------------------------------------------------------------
    def get_huggingface_download_status(
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

    # -------------------------------------------------------------------------
    def cancel_huggingface_download(
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

    # -------------------------------------------------------------------------
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

    # -------------------------------------------------------------------------
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

    # -------------------------------------------------------------------------
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

    # -------------------------------------------------------------------------
    def _reset_huggingface_download_directory(self, destination: Path) -> None:
        if destination.exists():
            shutil.rmtree(destination, ignore_errors=True)
        destination.mkdir(parents=True, exist_ok=True)

    # -------------------------------------------------------------------------
    def _cleanup_huggingface_download_directory(self, destination: Path) -> None:
        if destination.exists():
            shutil.rmtree(destination, ignore_errors=True)

    # -------------------------------------------------------------------------
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
