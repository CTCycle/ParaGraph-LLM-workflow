from __future__ import annotations

from server.services.workflow.vector_stores.base import (
    VectorStoreAdapter,
    VectorStoreError,
)
from server.services.workflow.vector_stores.chroma import (
    ChromaVectorStoreAdapter,
)
from server.services.workflow.vector_stores.lancedb import (
    LanceDbVectorStoreAdapter,
)
from server.services.workflow.vector_stores.milvus import (
    MilvusVectorStoreAdapter,
)
from server.services.workflow.vector_stores.pinecone import (
    PineconeVectorStoreAdapter,
)
from server.services.workflow.vector_stores.qdrant import (
    QdrantVectorStoreAdapter,
)
from server.services.workflow.vector_stores.weaviate import (
    WeaviateVectorStoreAdapter,
)

###############################################################################
class FaissVectorStoreAdapter(VectorStoreAdapter):
    pass


VECTOR_STORE_ADAPTERS = {
    "faiss": FaissVectorStoreAdapter(),
    "lancedb": LanceDbVectorStoreAdapter(),
    "qdrant": QdrantVectorStoreAdapter(),
    "pinecone": PineconeVectorStoreAdapter(),
    "weaviate": WeaviateVectorStoreAdapter(),
    "milvus": MilvusVectorStoreAdapter(),
    "chroma": ChromaVectorStoreAdapter(),
}

###############################################################################
def get_vector_store_adapter(backend: str) -> VectorStoreAdapter:
    adapter = VECTOR_STORE_ADAPTERS.get(backend.lower().strip())
    if adapter is None:
        raise VectorStoreError(f"Unsupported vector store backend: {backend}")
    return adapter


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
