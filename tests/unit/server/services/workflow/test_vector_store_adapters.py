from __future__ import annotations

from ParaGraph.server.services.workflow.vector_stores import (
    MilvusVectorStoreAdapter,
    PineconeVectorStoreAdapter,
    QdrantVectorStoreAdapter,
    VectorStoreError,
    WeaviateVectorStoreAdapter,
)


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


def test_qdrant_search_rejects_hybrid_mode() -> None:
    adapter = QdrantVectorStoreAdapter()

    try:
        adapter.search(
            store={"metadata": {"collection_name": "docs", "provider_config": {}}, "metric": "cosine"},
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


def test_weaviate_validate_connection_invokes_collection_exists(monkeypatch) -> None:
    adapter = WeaviateVectorStoreAdapter()
    calls: dict[str, object] = {}

    class FakeCollections:
        def exists(self, name: str) -> bool:
            calls["collection"] = name
            return True

    class FakeClient:
        collections = FakeCollections()

        def close(self) -> None:
            calls["closed"] = True

    monkeypatch.setattr(adapter, "_connect", lambda endpoint_url, api_key: FakeClient())

    adapter.validate_connection(index_name="docs", endpoint_url="https://cluster", api_key="token")

    assert calls["collection"] == "docs"
    assert calls["closed"] is True


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
