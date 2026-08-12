from __future__ import annotations

from server.domain.node_handler_ingestion import (
    DocumentTextExtractorParameters,
    LoadDocumentsParameters,
    SQLDatabaseParameters,
    SQLFileDatabaseParameters,
)
from server.domain.node_handler import NodeHandler
from server.services.workflow.node_handlers.ingestion.database_connections import (
    _sql_database_executor,
    _sql_file_database_executor,
)
from server.services.workflow.node_handlers.ingestion.documents import (
    _document_text_extractor_executor,
    _load_documents_executor,
)
from server.services.workflow.node_handlers.ingestion.files import (
    load_file_text,
    resolve_local_path,
)


INGESTION_HANDLERS = {
    "load_documents": NodeHandler(
        executor=_load_documents_executor, parameter_model=LoadDocumentsParameters
    ),
    "document_text_extractor": NodeHandler(
        executor=_document_text_extractor_executor,
        parameter_model=DocumentTextExtractorParameters,
    ),
    "sql_database": NodeHandler(
        executor=_sql_database_executor, parameter_model=SQLDatabaseParameters
    ),
    "sql_file_database": NodeHandler(
        executor=_sql_file_database_executor, parameter_model=SQLFileDatabaseParameters
    ),
}

__all__ = ["INGESTION_HANDLERS", "load_file_text", "resolve_local_path"]
