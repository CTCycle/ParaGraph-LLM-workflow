from __future__ import annotations

from server.domain.node_handler_ingestion import (
    DirectoryLoaderParameters,
    LoadDocumentsParameters,
    SQLDatabaseParameters,
    SQLFileDatabaseParameters,
)
from server.services.workflow.node_handlers.base import NodeHandler
from server.services.workflow.node_handlers.ingestion.database_connections import (
    _sql_database_executor,
    _sql_file_database_executor,
)
from server.services.workflow.node_handlers.ingestion.documents import (
    _directory_loader_executor,
    _load_documents_executor,
)
from server.services.workflow.node_handlers.ingestion.files import (
    load_file_text,
    resolve_local_path,
)


INGESTION_HANDLERS = {
    "directory_loader": NodeHandler(
        executor=_directory_loader_executor, parameter_model=DirectoryLoaderParameters
    ),
    "load_documents": NodeHandler(
        executor=_load_documents_executor, parameter_model=LoadDocumentsParameters
    ),
    "sql_database": NodeHandler(
        executor=_sql_database_executor, parameter_model=SQLDatabaseParameters
    ),
    "sql_file_database": NodeHandler(
        executor=_sql_file_database_executor, parameter_model=SQLFileDatabaseParameters
    ),
}

__all__ = ["INGESTION_HANDLERS", "load_file_text", "resolve_local_path"]

