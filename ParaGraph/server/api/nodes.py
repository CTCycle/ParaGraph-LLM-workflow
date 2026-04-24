from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from ParaGraph.server.domain.node_catalog import NodeCatalogResponse, NodeManifest
from ParaGraph.server.domain.nodes import (
    DatabaseConnectionCheckRequest,
    DatabaseConnectionCheckResponse,
    DatabaseSchemaRequest,
    DatabaseSchemaResponse,
    UploadedDirectoryResponse,
    VectorStoreConnectionCheckRequest,
    VectorStoreConnectionCheckResponse,
)
from ParaGraph.server.services.workflow import node_registry
from ParaGraph.server.services.workflow.nodes import node_connectivity_service
from ParaGraph.server.services.workflow.browser_uploads import browser_upload_service
from ParaGraph.server.services.workflow.database import inspect_database_schema
from ParaGraph.server.services.workflow.vector_stores import get_vector_store_adapter


router = APIRouter(prefix="/nodes", tags=["nodes"])

###############################################################################
@router.get("/catalog", response_model=NodeCatalogResponse)
def get_node_catalog() -> NodeCatalogResponse:
    return node_registry.catalog_response()

###############################################################################
@router.post(
    "/import", response_model=NodeManifest, status_code=status.HTTP_201_CREATED
)
def import_node_manifest(manifest: NodeManifest) -> NodeManifest:
    try:
        return node_registry.import_manifest(manifest)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc


@router.post("/uploads/directory", response_model=UploadedDirectoryResponse)
async def upload_directory(
    files: list[UploadFile] = File(...),
) -> UploadedDirectoryResponse:
    try:
        (
            path,
            file_count,
            staged_files,
        ) = await browser_upload_service.save_uploaded_directory(files)
        return UploadedDirectoryResponse(
            path=path, file_count=file_count, files=staged_files
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc

###############################################################################
@router.post(
    "/check-database-connection", response_model=DatabaseConnectionCheckResponse
)
def check_database_connection(
    request: DatabaseConnectionCheckRequest,
) -> DatabaseConnectionCheckResponse:
    return node_connectivity_service.check_database_connection(request)


@router.post("/database-schema", response_model=DatabaseSchemaResponse)
def get_database_schema(request: DatabaseSchemaRequest) -> DatabaseSchemaResponse:
    try:
        connection_payload = node_registry.execute(
            request.node_type,
            request.node_version,
            request.parameters,
            {},
        )
        schema = inspect_database_schema(connection_payload["connection"])
        return DatabaseSchemaResponse.model_validate(schema)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc


###############################################################################
@router.post(
    "/check-vector-store-connection", response_model=VectorStoreConnectionCheckResponse
)
def check_vector_store_connection(
    request: VectorStoreConnectionCheckRequest,
) -> VectorStoreConnectionCheckResponse:
    return node_connectivity_service.check_vector_store_connection(
        request,
        adapter_resolver=get_vector_store_adapter,
    )
