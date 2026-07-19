from __future__ import annotations

from pathlib import Path

import pytest

from server.domain.node_handler_core import VectorStoreParameters
from server.services.workflow.vector_stores import (
    MilvusVectorStoreAdapter,
    PineconeVectorStoreAdapter,
    QdrantVectorStoreAdapter,
    VectorStoreError,
    WeaviateVectorStoreAdapter,
    get_vector_store_adapter,
)
from server.services.workflow.vector_stores.base import (
    VectorStoreConflictError,
    _redacted_provider_config,
    _resolve_runtime_secret,
    reset_vector_secret_registry,
)
from server.services.workflow.vector_stores import base as vector_store_base


###############################################################################
def _point(point_id: str, document_id: str, vector: list[float]) -> dict[str, object]:
    return {
        "id": point_id,
        "chunk_id": f"chunk-{point_id}",
        "document_id": document_id,
        "text": point_id,
        "source_uri": "local",
        "vector": vector,
        "embedding_provider": "test",
        "embedding_model": "embedding-v1",
        "embedding_revision": "r1",
        "normalized": False,
        "metadata": {"kind": "test"},
    }

###############################################################################
def test_pinecone_map_filter_uses_operator_keys() -> None:
    adapter = PineconeVectorStoreAdapter()
    filter_spec = {
        "must": [
            {"field": "source", "op": "eq", "value": "docs"},
            {"field": "rank", "op": "gte", "value": 2},
        ],
        "should": [{"field": "lang", "op": "in", "value": ["en", "it"]}],
        "must_not": [{"field": "tenant", "op": "eq", "value": "blocked"}],
    }

    mapped = adapter._map_filter(filter_spec)

    assert mapped is not None
    assert "$and" in mapped
    assert {"metadata.source": {"$eq": "docs"}} in mapped["$and"]
    assert {"metadata.rank": {"$gte": 2}} in mapped["$and"]
    assert mapped["$or"] == [{"metadata.lang": {"$in": ["en", "it"]}}]
    assert mapped["$nor"] == [{"metadata.tenant": {"$eq": "blocked"}}]

###############################################################################
def test_qdrant_search_rejects_hybrid_mode() -> None:
    adapter = QdrantVectorStoreAdapter()

    try:
        adapter.search(
            store={
                "metadata": {"collection_name": "docs", "provider_config": {}},
                "metric": "cosine",
            },
            query_vector=[0.1, 0.2],
            top_k=3,
            score_threshold=0.0,
            filter_spec=None,
            include_metadata=True,
            search_mode="hybrid",
        )
    except VectorStoreError as exc:
        assert "Hybrid search" in str(exc)
    else:
        raise AssertionError("Expected VectorStoreError")

###############################################################################
def test_weaviate_validate_connection_invokes_collection_exists(monkeypatch) -> None:
    adapter = WeaviateVectorStoreAdapter()
    calls: dict[str, object] = {}

    ###############################################################################
    class FakeCollections:

        # -------------------------------------------------------------------------
        def exists(self, name: str) -> bool:
            calls["collection"] = name
            return True

    ###############################################################################
    class FakeClient:
        collections = FakeCollections()

        # -------------------------------------------------------------------------
        def close(self) -> None:
            calls["closed"] = True

    monkeypatch.setattr(adapter, "_connect", lambda endpoint_url, api_key: FakeClient())

    adapter.validate_connection(
        index_name="docs", endpoint_url="https://cluster", api_key="token"
    )

    assert calls["collection"] == "docs"
    assert calls["closed"] is True

###############################################################################
def test_milvus_filter_expression_combines_groups() -> None:
    adapter = MilvusVectorStoreAdapter()
    expression = adapter._milvus_filter(
        {
            "must": [{"field": "document_id", "op": "eq", "value": "doc-1"}],
            "must_not": [{"field": "chunk_id", "op": "eq", "value": "chunk-9"}],
            "should": [
                {"field": "source_uri", "op": "eq", "value": "a"},
                {"field": "source_uri", "op": "eq", "value": "b"},
            ],
        }
    )

    assert 'document_id == "doc-1"' in expression
    assert 'not (chunk_id == "chunk-9")' in expression
    assert 'source_uri == "a"' in expression
    assert 'source_uri == "b"' in expression

###############################################################################
@pytest.mark.parametrize("provider", ["lancedb", "chroma", "faiss"])
def test_vector_store_parameters_require_storage_path_for_local_providers(
    provider: str,
) -> None:
    with pytest.raises(ValueError, match="storage_path is required"):
        VectorStoreParameters.model_validate(
            {
                "provider": provider,
                "index_name": "docs",
                "storage_path": "",
                "endpoint_url": "",
            }
        )

###############################################################################
def test_faiss_validate_connection_rejects_relative_storage_path() -> None:
    adapter = get_vector_store_adapter("faiss")

    with pytest.raises(
        VectorStoreError, match="storage_directory must be an absolute path"
    ):
        adapter.validate_connection(
            index_name="docs", storage_directory="vectorstores/docs"
        )

###############################################################################
def test_faiss_validate_connection_accepts_absolute_storage_path(
    tmp_path: Path,
) -> None:
    adapter = get_vector_store_adapter("faiss")

    adapter.validate_connection(index_name="docs", storage_directory=str(tmp_path))

###############################################################################
@pytest.mark.parametrize("provider", ["qdrant", "pinecone", "weaviate", "milvus"])
def test_vector_store_parameters_require_endpoint_for_remote_providers(
    provider: str,
) -> None:
    with pytest.raises(ValueError, match="endpoint_url"):
        VectorStoreParameters.model_validate(
            {
                "provider": provider,
                "index_name": "docs",
                "storage_path": "",
                "endpoint_url": "",
            }
        )

###############################################################################
@pytest.mark.parametrize(
    ("backend", "supports_faiss_augmentation"),
    [
        ("faiss", True),
        ("lancedb", False),
        ("qdrant", False),
        ("pinecone", False),
        ("weaviate", False),
        ("milvus", False),
        ("chroma", False),
    ],
)
def test_vector_store_capabilities_matrix(
    backend: str, supports_faiss_augmentation: bool
) -> None:
    capabilities = get_vector_store_adapter(backend).describe_capabilities()
    assert capabilities["backend"] == backend
    assert capabilities["supports_metadata_filtering"] is True
    assert capabilities["supports_hybrid_search"] is False
    assert capabilities["supports_faiss_augmentation"] is supports_faiss_augmentation

###############################################################################
def test_faiss_lifecycle_is_owned_reloadable_and_explicit(tmp_path: Path) -> None:
    adapter = get_vector_store_adapter("faiss")
    store = adapter.write_points(
        index_name="docs",
        storage_directory=str(tmp_path),
        metric="cosine",
        write_mode="overwrite",
        id_conflict_policy="upsert",
        index_type="flat",
        points=[
            _point("one", "doc-a", [1.0, 0.0]),
            _point("two", "doc-a", [0.0, 1.0]),
            _point("three", "doc-b", [0.5, 0.5]),
        ],
    )

    assert adapter.inspect_collection(store=store).count == 3
    deleted = adapter.delete_document(store=store, document_id="doc-a")
    assert deleted.affected_ids == ["one", "two"]
    assert adapter.reload(store=store).metadata["count"] == 1
    removed = adapter.delete_collection(store=store)
    assert removed.affected_ids == ["three"]

###############################################################################
def test_faiss_duplicate_and_compatibility_policies_are_stable(tmp_path: Path) -> None:
    adapter = get_vector_store_adapter("faiss")
    store = adapter.write_points(
        index_name="docs",
        storage_directory=str(tmp_path),
        metric="cosine",
        write_mode="overwrite",
        id_conflict_policy="upsert",
        index_type="flat",
        points=[_point("one", "doc-a", [1.0, 0.0])],
    )

    with pytest.raises(VectorStoreConflictError) as duplicate:
        adapter.write_points(
            index_name="docs",
            storage_directory=str(tmp_path),
            metric="cosine",
            write_mode="append",
            id_conflict_policy="reject",
            index_type="flat",
            points=[_point("one", "doc-a", [0.0, 1.0])],
        )
    assert duplicate.value.conflicts == ["one"]

    incompatible = _point("two", "doc-b", [1.0, 0.0])
    incompatible["embedding_model"] = "embedding-v2"
    with pytest.raises(VectorStoreError, match="embedding_model"):
        adapter.write_points(
            index_name="docs",
            storage_directory=str(tmp_path),
            metric="cosine",
            write_mode="append",
            id_conflict_policy="upsert",
            index_type="flat",
            points=[incompatible],
        )
    assert adapter.reload(store=store).metadata["count"] == 1

###############################################################################
def test_faiss_failed_atomic_write_preserves_last_good_store(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    adapter = get_vector_store_adapter("faiss")
    store = adapter.write_points(
        index_name="docs",
        storage_directory=str(tmp_path),
        metric="cosine",
        write_mode="overwrite",
        id_conflict_policy="upsert",
        index_type="flat",
        points=[_point("one", "doc-a", [1.0, 0.0])],
    )

    def fail_build(*args: object, **kwargs: object) -> object:
        raise RuntimeError("injected index build failure")

    monkeypatch.setattr(vector_store_base, "_build_index", fail_build)
    with pytest.raises(RuntimeError, match="injected index build failure"):
        adapter.write_points(
            index_name="docs",
            storage_directory=str(tmp_path),
            metric="cosine",
            write_mode="overwrite",
            id_conflict_policy="upsert",
            index_type="flat",
            points=[_point("two", "doc-b", [0.0, 1.0])],
        )

    assert adapter.reload(store=store).metadata["count"] == 1
    assert not list(tmp_path.glob(".docs.tmp-*"))

###############################################################################
def test_runtime_vector_secret_handles_are_redacted_and_disposable() -> None:
    safe = _redacted_provider_config(
        {
            "provider": "qdrant",
            "api_key": "sk-sensitive-value",
            "password": "hidden",
        },
        "sk-sensitive-value",
    )

    serialized = str(safe)
    assert "sk-sensitive-value" not in serialized
    assert "hidden" not in serialized
    assert _resolve_runtime_secret(safe) == "sk-sensitive-value"
    reset_vector_secret_registry()
    assert _resolve_runtime_secret(safe) == ""
