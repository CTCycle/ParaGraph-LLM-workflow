from __future__ import annotations

from collections.abc import Callable
from typing import Any

from server.contracts.node_handler_core import VectorStoreParameters
from server.contracts.nodes import (
    DatabaseConnectionCheckRequest,
    DatabaseConnectionCheckResponse,
    DatabaseSchemaRequest,
    DatabaseSchemaResponse,
    VectorStoreConnectionCheckRequest,
    VectorStoreConnectionCheckResponse,
)
from server.repositories.workflow.database import inspect_database_schema
from server.services.configuration import configuration_service
from server.services.workflow.nodes.registry import node_registry
from server.services.workflow.vector_stores import get_vector_store_adapter


###############################################################################
class NodeConnectivityService:
    # -------------------------------------------------------------------------
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

    # -------------------------------------------------------------------------
    def get_database_schema(
        self, request: DatabaseSchemaRequest
    ) -> DatabaseSchemaResponse:
        connection_payload = node_registry.execute(
            request.node_type,
            request.node_version,
            request.parameters,
            {},
        )
        schema = inspect_database_schema(connection_payload["connection"])
        return DatabaseSchemaResponse.model_validate(schema)

    # -------------------------------------------------------------------------
    def check_vector_store_connection(
        self,
        request: VectorStoreConnectionCheckRequest,
        *,
        adapter_resolver: Callable[[str], Any] | None = None,
    ) -> VectorStoreConnectionCheckResponse:
        try:
            parsed = VectorStoreParameters.model_validate(request.parameters)
            resolver = adapter_resolver or get_vector_store_adapter
            adapter = resolver(parsed.provider)
            resolved_api_key = ""
            resolved_endpoint = parsed.endpoint_url
            if parsed.credential_profile:
                access_key = configuration_service.resolve_access_key(
                    profile_name=parsed.credential_profile,
                    provider=parsed.provider,
                )
                resolved_api_key = access_key.api_key or ""
                resolved_endpoint = resolved_endpoint or access_key.base_url or ""
            adapter.validate_connection(
                index_name=parsed.index_name,
                storage_directory=parsed.storage_path,
                namespace=parsed.namespace,
                endpoint_url=resolved_endpoint,
                api_key=resolved_api_key,
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
