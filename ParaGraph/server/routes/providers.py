from __future__ import annotations

from fastapi import APIRouter

from ParaGraph.server.entities.nodecatalog import ProviderCatalogResponse
from ParaGraph.server.services.workflow import provider_service


router = APIRouter(prefix="/providers", tags=["providers"])


@router.get("/catalog", response_model=ProviderCatalogResponse)
def get_provider_catalog() -> ProviderCatalogResponse:
    return provider_service.list_catalog()
