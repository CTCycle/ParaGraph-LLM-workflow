from __future__ import annotations

from ParaGraph.server.services.workflow.vector_stores.base import (
    ChromaVectorStoreAdapter,
    LanceDbVectorStoreAdapter,
    MilvusVectorStoreAdapter,
    PineconeVectorStoreAdapter,
    QdrantVectorStoreAdapter,
    VectorStoreAdapter,
    VectorStoreError,
    WeaviateVectorStoreAdapter,
    get_vector_store_adapter,
)


class FaissVectorStoreAdapter(VectorStoreAdapter):
    pass

__all__ = [
    "ChromaVectorStoreAdapter",
    "FaissVectorStoreAdapter",
    "LanceDbVectorStoreAdapter",
    "MilvusVectorStoreAdapter",
    "PineconeVectorStoreAdapter",
    "QdrantVectorStoreAdapter",
    "VectorStoreAdapter",
    "VectorStoreError",
    "WeaviateVectorStoreAdapter",
    "get_vector_store_adapter",
]
