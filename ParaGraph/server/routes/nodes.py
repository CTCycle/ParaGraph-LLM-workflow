from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

from ParaGraph.server.entities.nodecatalog import NodeCatalogResponse, NodeManifest
from ParaGraph.server.services.workflow import node_registry
from ParaGraph.server.services.workflow.browser_uploads import save_uploaded_directory


class UploadedDirectoryResponse(BaseModel):
    path: str
    file_count: int
    files: list[str] = Field(default_factory=list)


class DatabaseConnectionCheckRequest(BaseModel):
    node_type: Literal["SQL_DATABASE", "SQL_FILE_DATABASE"]
    node_version: int = Field(default=1, ge=1)
    parameters: dict[str, Any] = Field(default_factory=dict)


class DatabaseConnectionCheckResponse(BaseModel):
    ok: bool
    message: str


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


@router.post("/uploads/directory", response_model=UploadedDirectoryResponse)
async def upload_directory(files: list[UploadFile] = File(...)) -> UploadedDirectoryResponse:
    try:
        path, file_count, staged_files = await save_uploaded_directory(files)
        return UploadedDirectoryResponse(path=path, file_count=file_count, files=staged_files)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.post("/check-database-connection", response_model=DatabaseConnectionCheckResponse)
def check_database_connection(request: DatabaseConnectionCheckRequest) -> DatabaseConnectionCheckResponse:
    try:
        node_registry.execute(
            request.node_type,
            request.node_version,
            request.parameters,
            {},
        )
        return DatabaseConnectionCheckResponse(ok=True, message="Database connection successful.")
    except ValueError as exc:
        return DatabaseConnectionCheckResponse(ok=False, message=str(exc) or "Database connection check failed.")
    except Exception:  # noqa: BLE001
        return DatabaseConnectionCheckResponse(ok=False, message="Database connection check failed.")

