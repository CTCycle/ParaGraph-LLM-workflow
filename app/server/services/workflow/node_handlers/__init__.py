from server.services.workflow.node_handlers.core import CORE_HANDLERS
from server.services.workflow.node_handlers.advanced_text import ADVANCED_TEXT_HANDLERS
from server.services.workflow.node_handlers.database import DATABASE_HANDLERS
from server.services.workflow.node_handlers.control import CONTROL_HANDLERS
from server.services.workflow.node_handlers.http import HTTP_HANDLERS
from server.services.workflow.node_handlers.ingestion import (
    INGESTION_HANDLERS,
)
from server.services.workflow.node_handlers.output import OUTPUT_HANDLERS
from server.services.workflow.node_handlers.processing import (
    PROCESSING_HANDLERS,
)
from server.services.workflow.node_handlers.rag import RAG_HANDLERS
from server.services.workflow.node_handlers.structured import STRUCTURED_HANDLERS
from server.domain.node_handler_core import (
    MetadataParameters,
    ToolCallParameters,
    ToolCollectionParameters,
)
from server.services.workflow.node_handlers.base import NodeHandler
from server.services.workflow.node_handlers.core.metadata import _metadata_executor
from server.services.workflow.node_handlers.core.tools import (
    _tool_call_executor,
    _tool_collection_executor,
)

ADDITIONAL_CORE_NODE_HANDLERS = {
    "metadata": NodeHandler(
        executor=_metadata_executor, parameter_model=MetadataParameters
    ),
    "tool_collection": NodeHandler(
        executor=_tool_collection_executor, parameter_model=ToolCollectionParameters
    ),
    "tool_call": NodeHandler(
        executor=_tool_call_executor, parameter_model=ToolCallParameters
    ),
}

NODE_HANDLERS = {
    **CORE_HANDLERS,
    **ADVANCED_TEXT_HANDLERS,
    **ADDITIONAL_CORE_NODE_HANDLERS,
    **DATABASE_HANDLERS,
    **INGESTION_HANDLERS,
    **PROCESSING_HANDLERS,
    **RAG_HANDLERS,
    **HTTP_HANDLERS,
    **CONTROL_HANDLERS,
    **STRUCTURED_HANDLERS,
    **OUTPUT_HANDLERS,
}

__all__ = ["NODE_HANDLERS"]

