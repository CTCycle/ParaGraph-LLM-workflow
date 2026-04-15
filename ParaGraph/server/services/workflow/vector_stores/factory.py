from __future__ import annotations

from ParaGraph.server.services.workflow.vector_stores.base import (
    VECTOR_STORE_ADAPTERS,
    VectorStoreAdapter,
    VectorStoreError,
)


def get_vector_store_adapter(backend: str) -> VectorStoreAdapter:
    normalized = backend.lower().strip()
    adapter = VECTOR_STORE_ADAPTERS.get(normalized)
    if adapter is None:
        raise VectorStoreError(f"Unsupported vector store backend: {backend}")
    return adapter

