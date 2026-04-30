from server.services.workflow.node_handlers.core import CORE_HANDLERS
from server.services.workflow.node_handlers.database import DATABASE_HANDLERS
from server.services.workflow.node_handlers.ingestion import (
    INGESTION_HANDLERS,
)
from server.services.workflow.node_handlers.output import OUTPUT_HANDLERS
from server.services.workflow.node_handlers.processing import (
    PROCESSING_HANDLERS,
)

NODE_HANDLERS = {
    **CORE_HANDLERS,
    **DATABASE_HANDLERS,
    **INGESTION_HANDLERS,
    **PROCESSING_HANDLERS,
    **OUTPUT_HANDLERS,
}

__all__ = ["NODE_HANDLERS"]

