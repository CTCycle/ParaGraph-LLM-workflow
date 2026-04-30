from __future__ import annotations

from server.domain.configuration import DEFAULT_SESSION_NAME
from server.domain.node_catalog import (
    HuggingFaceModelDownloadCancelResponse,
    HuggingFaceModelDownloadResponse,
    HuggingFaceModelDownloadStatusResponse,
)


class HuggingFaceDownloadService:
    def __init__(self, provider_service: object) -> None:
        self._provider_service = provider_service

    def download_model(
        self,
        *,
        repo_id: str,
        session_name: str = DEFAULT_SESSION_NAME,
    ) -> HuggingFaceModelDownloadResponse:
        return self._provider_service._download_huggingface_model_impl(  # noqa: SLF001
            repo_id=repo_id,
            session_name=session_name,
        )

    def get_download_status(
        self, *, job_id: str
    ) -> HuggingFaceModelDownloadStatusResponse:
        return self._provider_service._get_huggingface_download_status_impl(
            job_id=job_id
        )  # noqa: SLF001

    def cancel_download(self, *, job_id: str) -> HuggingFaceModelDownloadCancelResponse:
        return self._provider_service._cancel_huggingface_download_impl(job_id=job_id)  # noqa: SLF001

