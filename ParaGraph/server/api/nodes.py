from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from ParaGraph.server.domain.node_catalog import NodeCatalogResponse, NodeManifest
from ParaGraph.server.domain.nodes import (
    DatabaseConnectionCheckRequest,
    DatabaseConnectionCheckResponse,
    UploadedDirectoryResponse,
    VectorStoreConnectionCheckRequest,
    VectorStoreConnectionCheckResponse,
)
from ParaGraph.server.services.workflow import node_registry
from ParaGraph.server.domain.node_handler_core import VectorStoreParameters
from ParaGraph.server.services.workflow.vector_stores import get_vector_store_adapter
from ParaGraph.server.services.workflow.browser_uploads import browser_upload_service


router = APIRouter(prefix="/nodes", tags=["nodes"])


@router.get("/catalog", response_model=NodeCatalogResponse)
def get_node_catalog() -> NodeCatalogResponse:
    return node_registry.catalog_response()


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


@router.post(
    "/check-database-connection", response_model=DatabaseConnectionCheckResponse
)
def check_database_connection(
    request: DatabaseConnectionCheckRequest,
) -> DatabaseConnectionCheckResponse:
    try:
        node_registry.execute(
            request.node_type,
            request.node_version,
            request.parameters,
            {},
        )
        return DatabaseConnectionCheckResponse(
            ok=True, message="Database connection successful."
        )
    except ValueError as exc:
        return DatabaseConnectionCheckResponse(
            ok=False, message=str(exc) or "Database connection check failed."
        )
    except Exception:  # noqa: BLE001
        return DatabaseConnectionCheckResponse(
            ok=False, message="Database connection check failed."
        )


@router.post(
    "/check-vector-store-connection", response_model=VectorStoreConnectionCheckResponse
)
def check_vector_store_connection(
    request: VectorStoreConnectionCheckRequest,
) -> VectorStoreConnectionCheckResponse:
    try:
        parsed = VectorStoreParameters.model_validate(request.parameters)
        adapter = get_vector_store_adapter(parsed.provider)
        adapter.validate_connection(
            index_name=parsed.index_name,
            storage_directory=parsed.storage_path,
            namespace=parsed.namespace,
            endpoint_url=parsed.endpoint_url,
            api_key=parsed.api_key,
            collection_name=parsed.collection_name,
            database_name=parsed.database_name,
            provider_config=parsed.provider_config,
        )
        return VectorStoreConnectionCheckResponse(
            ok=True, message="Vector store connection successful."
        )
    except ValueError as exc:
        return VectorStoreConnectionCheckResponse(
            ok=False, message=str(exc) or "Vector store connection check failed."
        )
    except Exception:  # noqa: BLE001
        return VectorStoreConnectionCheckResponse(
            ok=False, message="Vector store connection check failed."
        )
