from __future__ import annotations

from fastapi import APIRouter

from ParaGraph.server.entities.nodecatalog import NodeCatalogResponse
from ParaGraph.server.services.workflow import node_registry


router = APIRouter(prefix="/nodes", tags=["nodes"])


@router.get("/catalog", response_model=NodeCatalogResponse)
def get_node_catalog() -> NodeCatalogResponse:
    return node_registry.catalog_response()
