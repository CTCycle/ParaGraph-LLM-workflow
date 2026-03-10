from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from ParaGraph.server.entities.nodecatalog import NodeCatalogResponse, NodeManifest
from ParaGraph.server.services.workflow import node_registry


router = APIRouter(prefix="/nodes", tags=["nodes"])


@router.get("/catalog", response_model=NodeCatalogResponse)
def get_node_catalog() -> NodeCatalogResponse:
    return node_registry.catalog_response()


@router.post("/import", response_model=NodeManifest, status_code=status.HTTP_201_CREATED)
def import_node_manifest(manifest: NodeManifest) -> NodeManifest:
    try:
        return node_registry.import_manifest(manifest)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
