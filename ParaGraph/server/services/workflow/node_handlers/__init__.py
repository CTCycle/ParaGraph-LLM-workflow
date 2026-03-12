from ParaGraph.server.services.workflow.node_handlers.core import CORE_HANDLERS
from ParaGraph.server.services.workflow.node_handlers.ingestion import INGESTION_HANDLERS
from ParaGraph.server.services.workflow.node_handlers.output import OUTPUT_HANDLERS
from ParaGraph.server.services.workflow.node_handlers.processing import PROCESSING_HANDLERS
from ParaGraph.server.services.workflow.node_handlers.rag import RAG_HANDLERS

NODE_HANDLERS = {
    **CORE_HANDLERS,
    **INGESTION_HANDLERS,
    **PROCESSING_HANDLERS,
    **RAG_HANDLERS,
    **OUTPUT_HANDLERS,
}

__all__ = ["NODE_HANDLERS"]
