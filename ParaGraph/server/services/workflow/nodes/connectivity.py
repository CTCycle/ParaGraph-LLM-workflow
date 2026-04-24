from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ParaGraph.server.domain.node_handler_core import VectorStoreParameters
from ParaGraph.server.domain.nodes import (
    DatabaseConnectionCheckRequest,
    DatabaseConnectionCheckResponse,
    VectorStoreConnectionCheckRequest,
    VectorStoreConnectionCheckResponse,
)
from ParaGraph.server.services.workflow.nodes.registry import node_registry
from ParaGraph.server.services.workflow.vector_stores import get_vector_store_adapter


class NodeConnectivityService:
    def check_database_connection(
        self, request: DatabaseConnectionCheckRequest
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

    def check_vector_store_connection(
        self,
        request: VectorStoreConnectionCheckRequest,
        *,
        adapter_resolver: Callable[[str], Any] = get_vector_store_adapter,
    ) -> VectorStoreConnectionCheckResponse:
        try:
            parsed = VectorStoreParameters.model_validate(request.parameters)
            adapter = adapter_resolver(parsed.provider)
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


node_connectivity_service = NodeConnectivityService()
