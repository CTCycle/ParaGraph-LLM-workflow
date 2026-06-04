from __future__ import annotations

from fastapi import APIRouter, HTTPException, Path, Query

from server.domain.configuration import DEFAULT_SESSION_NAME, SESSION_NAME_PATTERN
from server.domain.jobs import JOB_ID_PATTERN
from server.domain.node_catalog import (
    HuggingFaceModelCatalogResponse,
    HuggingFaceModelDownloadCancelResponse,
    HuggingFaceModelDownloadRequest,
    HuggingFaceModelDownloadResponse,
    HuggingFaceModelDownloadStatusResponse,
    HuggingFaceSortBy,
    ModelVisibilityFilter,
    OllamaLibraryCatalogResponse,
    OllamaModelPullRequest,
    OllamaModelPullResponse,
    ProviderCatalogResponse,
    ProviderModelCatalogResponse,
)
from server.services.workflow import provider_service
from server.services.workflow.provider import ProviderApiError


router = APIRouter(prefix="/providers", tags=["providers"])


@router.get("/catalog", response_model=ProviderCatalogResponse)
def get_provider_catalog() -> ProviderCatalogResponse:
    return provider_service.list_catalog()


@router.get("/models", response_model=ProviderModelCatalogResponse)
def get_provider_models(
    session_name: str = Query(
        default=DEFAULT_SESSION_NAME,
        min_length=1,
        max_length=120,
        pattern=SESSION_NAME_PATTERN,
    ),
) -> ProviderModelCatalogResponse:
    return provider_service.list_models(session_name=session_name)


@router.get("/ollama/library", response_model=OllamaLibraryCatalogResponse)
def get_ollama_library_models(
    session_name: str = Query(
        default=DEFAULT_SESSION_NAME,
        min_length=1,
        max_length=120,
        pattern=SESSION_NAME_PATTERN,
    ),
    search: str | None = Query(default=None, max_length=120),
    refresh: bool = Query(default=False),
) -> OllamaLibraryCatalogResponse:
    try:
        return provider_service.list_ollama_library_models(
            session_name=session_name,
            search=search,
            refresh=refresh,
        )
    except ProviderApiError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post("/ollama/pull", response_model=OllamaModelPullResponse)
def pull_ollama_model(
    payload: OllamaModelPullRequest,
    session_name: str = Query(
        default=DEFAULT_SESSION_NAME,
        min_length=1,
        max_length=120,
        pattern=SESSION_NAME_PATTERN,
    ),
) -> OllamaModelPullResponse:
    try:
        return provider_service.pull_ollama_model(
            model=payload.model, session_name=session_name
        )
    except ProviderApiError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.get("/huggingface/models", response_model=HuggingFaceModelCatalogResponse)
def get_huggingface_models(
    session_name: str = Query(
        default=DEFAULT_SESSION_NAME,
        min_length=1,
        max_length=120,
        pattern=SESSION_NAME_PATTERN,
    ),
    search: str | None = Query(default=None, max_length=180),
    task: str | None = Query(default=None, max_length=120),
    library: str | None = Query(default=None, max_length=120),
    author: str | None = Query(default=None, max_length=120),
    visibility: ModelVisibilityFilter = Query(default="all"),
    sort: HuggingFaceSortBy = Query(default="relevance"),
    page: int = Query(default=1, ge=1, le=10_000),
    page_size: int = Query(default=25, ge=1, le=50),
    refresh: bool = Query(default=False),
) -> HuggingFaceModelCatalogResponse:
    try:
        return provider_service.list_huggingface_models(
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
    except ProviderApiError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post("/huggingface/download", response_model=HuggingFaceModelDownloadResponse)
def download_huggingface_model(
    payload: HuggingFaceModelDownloadRequest,
    session_name: str = Query(
        default=DEFAULT_SESSION_NAME,
        min_length=1,
        max_length=120,
        pattern=SESSION_NAME_PATTERN,
    ),
) -> HuggingFaceModelDownloadResponse:
    try:
        return provider_service.download_huggingface_model(
            repo_id=payload.repo_id, session_name=session_name
        )
    except ProviderApiError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.get(
    "/huggingface/download/{job_id}",
    response_model=HuggingFaceModelDownloadStatusResponse,
)
def get_huggingface_download_status(
    job_id: str = Path(..., min_length=1, max_length=128, pattern=JOB_ID_PATTERN),
) -> HuggingFaceModelDownloadStatusResponse:
    try:
        return provider_service.get_huggingface_download_status(job_id=job_id)
    except ProviderApiError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.delete(
    "/huggingface/download/{job_id}",
    response_model=HuggingFaceModelDownloadCancelResponse,
)
def cancel_huggingface_download(
    job_id: str = Path(..., min_length=1, max_length=128, pattern=JOB_ID_PATTERN),
) -> HuggingFaceModelDownloadCancelResponse:
    try:
        return provider_service.cancel_huggingface_download(job_id=job_id)
    except ProviderApiError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
