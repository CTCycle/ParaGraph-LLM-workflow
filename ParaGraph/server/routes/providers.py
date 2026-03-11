from __future__ import annotations

from fastapi import APIRouter, Query

from ParaGraph.server.entities.configuration import DEFAULT_SESSION_NAME
from ParaGraph.server.entities.nodecatalog import ProviderCatalogResponse, ProviderModelCatalogResponse
from ParaGraph.server.services.workflow import provider_service


router = APIRouter(prefix="/providers", tags=["providers"])


@router.get("/catalog", response_model=ProviderCatalogResponse)
def get_provider_catalog() -> ProviderCatalogResponse:
    return provider_service.list_catalog()


@router.get("/models", response_model=ProviderModelCatalogResponse)
def get_provider_models(
    session_name: str = Query(default=DEFAULT_SESSION_NAME, min_length=1, max_length=120),
) -> ProviderModelCatalogResponse:
    return provider_service.list_models(session_name=session_name)
