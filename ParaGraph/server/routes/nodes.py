from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from ParaGraph.server.entities.nodecatalog import NodeCatalogResponse, NodeManifest
from ParaGraph.server.services.workflow import node_registry
from ParaGraph.server.services.workflow.path_picker import pick_directory, pick_files


class PickedPathsResponse(BaseModel):
    paths: list[str] = Field(default_factory=list)


class PickedDirectoryResponse(BaseModel):
    path: str | None = None


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


@router.get("/dialog/files", response_model=PickedPathsResponse)
def browse_files(multiple: bool = Query(default=False)) -> PickedPathsResponse:
    try:
        return PickedPathsResponse(paths=pick_files(multiple=multiple))
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc


@router.get("/dialog/directory", response_model=PickedDirectoryResponse)
def browse_directory() -> PickedDirectoryResponse:
    try:
        return PickedDirectoryResponse(path=pick_directory())
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
