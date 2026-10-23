from __future__ import annotations

from server.services.workflow.node_handlers.rag import _citation_formatter_executor, _context_builder_executor, _html_to_text_executor
from server.services.workflow import node_registry
from server.contracts.workflow_model import WorkflowDefinition
from server.services.workflow.compiler import compiler_service
import json
import re
from typing import Any
import pytest
from server.common import path as common_path
from server.contracts.node_handler_core import SimilaritySearchParameters
from server.contracts.node_catalog import VectorStoreCapabilities
import server.services.workflow.node_handlers.core.embeddings as embeddings_module
from pathlib import Path
from server.contracts.node_handler_core import VectorStoreParameters
from server.services.workflow.vector_stores import MilvusVectorStoreAdapter, PineconeVectorStoreAdapter, QdrantVectorStoreAdapter, VectorStoreError, WeaviateVectorStoreAdapter, get_vector_store_adapter
from server.services.workflow.vector_stores.base import VectorStoreConflictError, _score_from_metric, _redacted_provider_config, _resolve_runtime_secret, reset_vector_secret_registry
from server.services.workflow.vector_stores import base as vector_store_base

# RAG nodes

###############################################################################
def test_html_to_text_strips_script_style_nav() -> None:
    result = _html_to_text_executor(
        {}, {"html": "<script>x</script><nav>n</nav><p>Hello</p>"}
    )
    assert "x" not in result["result"]
    assert "n" not in result["result"]
    assert "Hello" in result["result"]

###############################################################################
def test_context_builder_respects_token_budget() -> None:
    result = _context_builder_executor(
        {"token_budget": 2}, {"chunks": [{"text": "one two three"}]}
    )
    assert result["result"] == "one two"

###############################################################################
def test_context_builder_accepts_manifest_inputs_and_coerces_malformed_values() -> None:
    result = _context_builder_executor(
        {"token_budget": 3},
        {"value": [None, {"content": "one two three"}, {"text": "four"}]},
    )
    assert result["result"] == "one two three"

    text_input_result = _context_builder_executor(
        {"token_budget": 1}, {"text": "four five"}
    )
    assert text_input_result["result"] == "four"

    empty_result = _context_builder_executor({}, {"value": None})
    assert empty_result["result"] == ""

###############################################################################
def test_html_to_text_coerces_none_and_recovers_malformed_markup() -> None:
    assert _html_to_text_executor({}, {"text": None})["result"] == ""
    assert (
        _html_to_text_executor({}, {"text": "<p>Readable <strong>text"})["result"]
        == "Readable text"
    )

###############################################################################
def test_citation_formatter_reads_retrieval_results_from_manifest_value_input() -> None:
    result = _citation_formatter_executor(
        {},
        {
            "value": {
                "query": "alpha target",
                "hits": [
                    {
                        "metadata": {
                            "source": "paper.pdf",
                            "page_number": 4,
                            "chunk_id": "chunk-1",
                        }
                    }
                ],
            }
        },
    )

    assert result["result"] == [
        {
            "source": "paper.pdf",
            "page": None,
            "page_number": 4,
            "line": None,
            "chunk_id": "chunk-1",
        }
    ]

# Rerank results

###############################################################################
def _results_payload() -> dict[str, object]:
    return {
        "query": "fast api workflow",
        "hits": [
            {
                "id": "a",
                "chunk_id": "a",
                "document_id": "doc-a",
                "text": "FastAPI workflow guide with retrieval notes",
                "source_uri": "a",
                "score": 0.2,
                "metadata": {"source": "docs", "lang": "en"},
            },
            {
                "id": "b",
                "chunk_id": "b",
                "document_id": "doc-b",
                "text": "Workflow orchestration and API integration",
                "source_uri": "b",
                "score": 0.8,
                "metadata": {"source": "blog", "lang": "en"},
            },
            {
                "id": "c",
                "chunk_id": "c",
                "document_id": "doc-c",
                "text": "fast api workflow exact phrase appears here",
                "source_uri": "c",
                "score": 0.5,
                "metadata": {"source": "docs", "lang": "it"},
            },
        ],
    }

###############################################################################
def _execute(
    parameters: dict[str, object], *, query: str | None = None
) -> dict[str, object]:
    inputs: dict[str, object] = {"results": _results_payload()}
    if query is not None:
        inputs["query"] = query
    return node_registry.execute("RERANK_RESULTS", 1, parameters, inputs)

###############################################################################
def test_rerank_strategy_original_score_preserves_order_by_score() -> None:
    payload = _execute(
        {"strategy": "original_score", "score_mode": "replace", "top_k": 0}
    )
    hits = payload["results"]["hits"]
    assert [hit["id"] for hit in hits] == ["b", "c", "a"]

###############################################################################
def test_rerank_strategy_term_overlap() -> None:
    payload = _execute(
        {"strategy": "term_overlap", "score_mode": "replace", "top_k": 0}
    )
    hits = payload["results"]["hits"]
    assert [hit["id"] for hit in hits] == ["c", "b", "a"]

###############################################################################
def test_rerank_strategy_exact_phrase() -> None:
    payload = _execute(
        {"strategy": "exact_phrase", "score_mode": "replace", "top_k": 0}
    )
    hits = payload["results"]["hits"]
    assert hits[0]["id"] == "c"
    assert hits[0]["score"] == 1.0

###############################################################################
def test_rerank_strategy_metadata_match() -> None:
    payload = _execute(
        {
            "strategy": "metadata_match",
            "score_mode": "replace",
            "metadata_field": "source",
            "metadata_value": "docs",
            "top_k": 0,
        }
    )
    hits = payload["results"]["hits"]
    assert [hit["id"] for hit in hits[:2]] == ["a", "c"]

###############################################################################
def test_rerank_strategy_weighted_composite() -> None:
    payload = _execute(
        {
            "strategy": "weighted_composite",
            "score_mode": "replace",
            "original_score_weight": 0.1,
            "term_overlap_weight": 0.8,
            "phrase_boost": 1.2,
            "metadata_boost": 0.3,
            "metadata_field": "source",
            "metadata_value": "docs",
            "top_k": 0,
        }
    )
    hits = payload["results"]["hits"]
    assert hits[0]["id"] == "c"

###############################################################################
def test_rerank_score_mode_replace_vs_boost() -> None:
    replace_payload = _execute(
        {"strategy": "term_overlap", "score_mode": "replace", "top_k": 0}
    )
    boost_payload = _execute(
        {"strategy": "term_overlap", "score_mode": "boost", "top_k": 0}
    )

    replace_scores = {
        hit["id"]: hit["score"] for hit in replace_payload["results"]["hits"]
    }
    boost_scores = {hit["id"]: hit["score"] for hit in boost_payload["results"]["hits"]}

    assert boost_scores["a"] > replace_scores["a"]
    assert boost_scores["b"] > replace_scores["b"]
    assert boost_scores["c"] > replace_scores["c"]

###############################################################################
def test_rerank_metadata_match_uses_exact_case_insensitive_equality() -> None:
    payload = _execute(
        {
            "strategy": "metadata_match",
            "score_mode": "replace",
            "metadata_field": "lang",
            "metadata_value": "EN",
            "top_k": 0,
        }
    )
    hits = payload["results"]["hits"]
    assert [hit["id"] for hit in hits[:2]] == ["a", "b"]
    assert hits[2]["id"] == "c"

###############################################################################
def test_rerank_preserves_stable_order_on_exact_ties() -> None:
    payload = _execute(
        {
            "strategy": "metadata_match",
            "score_mode": "replace",
            "metadata_field": "missing",
            "metadata_value": "value",
            "top_k": 0,
        }
    )
    hits = payload["results"]["hits"]
    assert [hit["id"] for hit in hits] == ["a", "b", "c"]

###############################################################################
def test_rerank_uses_results_query_when_query_input_is_missing() -> None:
    payload = _execute(
        {"strategy": "exact_phrase", "score_mode": "replace", "top_k": 0}, query=""
    )
    hits = payload["results"]["hits"]
    assert hits[0]["id"] == "c"
    assert payload["results"]["query"] == "fast api workflow"

###############################################################################
def test_rerank_top_k_zero_and_bounded_truncation() -> None:
    all_hits_payload = _execute(
        {"strategy": "original_score", "score_mode": "replace", "top_k": 0}
    )
    top_two_payload = _execute(
        {"strategy": "original_score", "score_mode": "replace", "top_k": 2}
    )

    assert len(all_hits_payload["results"]["hits"]) == 3
    assert len(top_two_payload["results"]["hits"]) == 2

# Similarity search compiler

###############################################################################
def _build_similarity_workflow(
    *,
    search_mode: str,
    search_engine: str,
    similarity_strategy: str,
    distance_metric: str,
) -> WorkflowDefinition:
    return WorkflowDefinition.model_validate(
        {
            "schema_version": 2,
            "nodes": [
                {
                    "node_id": "prompt_query",
                    "node_type": "PROMPT",
                    "node_version": 1,
                    "parameters": {"prompt_text": "hello"},
                },
                {
                    "node_id": "embed_query",
                    "node_type": "TEXT_EMBEDDING",
                    "node_version": 1,
                    "parameters": {
                        "provider": "openai",
                        "model_name": "text-embedding-3-small",
                    },
                },
                {
                    "node_id": "store_vectors",
                    "node_type": "VECTOR_STORE",
                    "node_version": 2,
                    "parameters": {
                        "provider": "chroma",
                        "index_name": "docs",
                        "distance_metric": distance_metric,
                        "write_mode": "overwrite",
                        "storage_path": "vectorstores/test",
                    },
                },
                {
                    "node_id": "similarity",
                    "node_type": "SIMILARITY_SEARCH",
                    "node_version": 1,
                    "parameters": {
                        "search_mode": search_mode,
                        "search_engine": search_engine,
                        "similarity_strategy": similarity_strategy,
                    },
                },
            ],
            "connections": [
                {
                    "from_node": "prompt_query",
                    "from_output": "text",
                    "to_node": "embed_query",
                    "to_input": "text",
                },
                {
                    "from_node": "embed_query",
                    "from_output": "vectors",
                    "to_node": "store_vectors",
                    "to_input": "vectors",
                },
                {
                    "from_node": "prompt_query",
                    "from_output": "text",
                    "to_node": "similarity",
                    "to_input": "query",
                },
                {
                    "from_node": "embed_query",
                    "from_controller": "embedding",
                    "to_node": "similarity",
                    "to_controller": "embedding",
                    "connection_type": "controller",
                },
                {
                    "from_node": "store_vectors",
                    "from_controller": "store",
                    "to_node": "similarity",
                    "to_controller": "store",
                    "connection_type": "controller",
                },
            ],
            "metadata": {},
        }
    )

###############################################################################
def test_compiler_reports_similarity_backend_incompatibilities() -> None:
    definition = _build_similarity_workflow(
        search_mode="hybrid",
        search_engine="faiss_augmented",
        similarity_strategy="dot",
        distance_metric="cosine",
    )

    compiled = compiler_service.compile(definition)

    assert compiled.valid is False
    codes = {item.code for item in compiled.diagnostics}
    assert "similarity_metric_mismatch" in codes
    assert "unsupported_similarity_mode" in codes
    assert "unsupported_similarity_engine" in codes

# Similarity search contracts

###############################################################################
def _read_parameter_options_from_doc(parameter_name: str) -> list[str]:
    doc_path = (
        common_path.REPOSITORY_ROOT
        / "assets"
        / "docs"
        / "nodes"
        / "processing_and_retrieval.md"
    )
    content = doc_path.read_text(encoding="utf-8")
    pattern = re.compile(
        rf"- `{re.escape(parameter_name)}`\s*\n\s*-\s*(?:options:\s*)?([^\n]+)",
        flags=re.MULTILINE,
    )
    match = pattern.search(content)
    if match is None:
        raise AssertionError(
            f"Missing options declaration in processing_and_retrieval.md for parameter '{parameter_name}'"
        )
    return re.findall(r"`([^`]+)`", match.group(1))

###############################################################################
def _manifest_parameter_options(parameter_name: str) -> list[str]:
    manifest_path = common_path.RESOURCES_ROOT / "nodes" / "similarity_search_v1.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    parameter = next(
        item for item in manifest["parameters"] if item["name"] == parameter_name
    )
    return [str(item) for item in parameter.get("constraints", {}).get("options", [])]

###############################################################################
def test_similarity_contract_matrix_doc_matches_manifest_options() -> None:
    assert _manifest_parameter_options(
        "search_mode"
    ) == _read_parameter_options_from_doc("search_mode")
    assert _manifest_parameter_options(
        "search_engine"
    ) == _read_parameter_options_from_doc("search_engine")
    assert _manifest_parameter_options(
        "similarity_strategy"
    ) == _read_parameter_options_from_doc("similarity_strategy")

###############################################################################
def test_similarity_search_parameters_validate_search_engine_rules() -> None:
    parsed = SimilaritySearchParameters.model_validate(
        {
            "search_mode": "vector",
            "search_engine": "native",
            "similarity_strategy": "cosine",
            "top_k": 5,
            "vector_weight": 0.5,
            "keyword_weight": 0.5,
        }
    )
    assert parsed.search_engine == "native"

    with pytest.raises(ValueError, match="search_engine must be one of"):
        SimilaritySearchParameters.model_validate({"search_engine": "invalid"})

    with pytest.raises(
        ValueError,
        match="faiss_augmented search_engine currently supports search_mode='vector' only",
    ):
        SimilaritySearchParameters.model_validate(
            {
                "search_mode": "hybrid",
                "search_engine": "faiss_augmented",
                "vector_weight": 0.6,
                "keyword_weight": 0.4,
            }
        )

###############################################################################
class _FakeAdapter:

    # -------------------------------------------------------------------------
    def __init__(
        self,
        *,
        backend: str = "chroma",
        supports_hybrid_search: bool = False,
        supports_faiss_augmentation: bool = False,
    ) -> None:
        self.backend = backend
        self.supports_hybrid_search = supports_hybrid_search
        self.supports_faiss_augmentation = supports_faiss_augmentation
        self.last_search_kwargs: dict[str, Any] | None = None

    # -------------------------------------------------------------------------
    def describe_capabilities(self) -> VectorStoreCapabilities:
        return VectorStoreCapabilities(
            backend=self.backend,
            supported_metrics=["cosine", "l2", "dot"],
            supported_search_modes=(
                ["vector", "hybrid"] if self.supports_hybrid_search else ["vector"]
            ),
            supported_search_engines=(
                ["native", "faiss_augmented"]
                if self.supports_faiss_augmentation
                else ["native"]
            ),
            supports_metadata_filtering=True,
            supported_filter_operators=[
                "eq",
                "in",
                "exists",
                "contains",
                "gt",
                "gte",
                "lt",
                "lte",
            ],
            supports_filter_groups=True,
            supports_minimum_should_match=True,
            supported_operations=["search"],
            score_semantics_by_metric={
                "cosine": "normalized_similarity",
                "l2": "normalized_similarity",
                "dot": "native_similarity",
            },
        )

    # -------------------------------------------------------------------------
    def search(self, **kwargs: Any) -> list[dict[str, Any]]:
        self.last_search_kwargs = kwargs
        return [
            {
                "id": "hit-1",
                "chunk_id": "chunk-1",
                "document_id": "doc-1",
                "text": "result",
                "source_uri": "memory://doc-1",
                "score": 0.91,
                "metadata": {"tenant": "default"},
            }
        ]

###############################################################################
def _valid_store_payload(*, backend: str, metric: str = "cosine") -> dict[str, Any]:
    return {
        "backend": backend,
        "index_name": "docs",
        "artifact_path": "",
        "metric": metric,
        "dimension": 2,
        "embedding_provider": "openai",
        "embedding_model": "text-embedding-3-small",
        "metadata": {},
    }

###############################################################################
def test_similarity_search_executor_rejects_unsupported_backend_modes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = _FakeAdapter(
        backend="chroma",
        supports_hybrid_search=False,
        supports_faiss_augmentation=False,
    )
    monkeypatch.setattr(
        embeddings_module, "get_vector_store_adapter", lambda backend: adapter
    )
    monkeypatch.setattr(
        embeddings_module, "_embed_text_for_text_embedding_node", lambda **_: [0.2, 0.4]
    )

    with pytest.raises(ValueError, match="does not support hybrid mode"):
        node_registry.execute(
            "SIMILARITY_SEARCH",
            1,
            {"search_mode": "hybrid", "search_engine": "native"},
            {"query": "hello"},
            controllers={
                "embedding": {"provider": "openai", "model": "text-embedding-3-small"},
                "store": _valid_store_payload(backend="chroma"),
            },
        )

    with pytest.raises(ValueError, match="does not support faiss_augmented engine"):
        node_registry.execute(
            "SIMILARITY_SEARCH",
            1,
            {"search_mode": "vector", "search_engine": "faiss_augmented"},
            {"query": "hello"},
            controllers={
                "embedding": {"provider": "openai", "model": "text-embedding-3-small"},
                "store": _valid_store_payload(backend="chroma"),
            },
        )

###############################################################################
def test_similarity_search_executor_validates_store_payload_and_uses_native_search_engine(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = _FakeAdapter(
        backend="faiss", supports_hybrid_search=False, supports_faiss_augmentation=True
    )
    monkeypatch.setattr(
        embeddings_module, "get_vector_store_adapter", lambda backend: adapter
    )
    monkeypatch.setattr(
        embeddings_module, "_embed_text_for_text_embedding_node", lambda **_: [0.3, 0.7]
    )

    with pytest.raises(ValueError, match="VectorStoreHandle"):
        node_registry.execute(
            "SIMILARITY_SEARCH",
            1,
            {"search_mode": "vector", "search_engine": "native"},
            {"query": "hello"},
            controllers={
                "embedding": {"provider": "openai", "model": "text-embedding-3-small"},
                "store": {"backend": "faiss"},
            },
        )

    payload = node_registry.execute(
        "SIMILARITY_SEARCH",
        1,
        {
            "search_mode": "vector",
            "search_engine": "faiss_augmented",
            "similarity_strategy": "cosine",
        },
        {"query": "hello"},
        controllers={
            "embedding": {"provider": "openai", "model": "text-embedding-3-small"},
            "store": _valid_store_payload(backend="faiss"),
        },
    )

    assert payload["results"]["query"] == "hello"
    assert adapter.last_search_kwargs is not None
    assert adapter.last_search_kwargs["search_engine"] == "native"

# Vector store adapter behavior

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
        assert "hybrid mode" in str(exc)
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
    ("backend", "supports_faiss_augmented"),
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
    backend: str, supports_faiss_augmented: bool
) -> None:
    capabilities = get_vector_store_adapter(backend).describe_capabilities()
    assert isinstance(capabilities, VectorStoreCapabilities)
    assert capabilities.backend == backend
    assert capabilities.supports_metadata_filtering is True
    assert capabilities.supported_search_modes == ["vector"]
    assert (
        "faiss_augmented" in capabilities.supported_search_engines
    ) is supports_faiss_augmented

###############################################################################
def test_vector_capabilities_fail_closed_for_unsupported_filters_and_namespaces() -> (
    None
):
    pinecone = get_vector_store_adapter("pinecone")

    with pytest.raises(VectorStoreError, match="minimum_should_match"):
        pinecone._map_filter(
            {
                "should": [
                    {"field": "language", "op": "eq", "value": "en"},
                    {"field": "tenant", "op": "eq", "value": "default"},
                ],
                "minimum_should_match": 2,
            }
        )

    with pytest.raises(VectorStoreError, match="does not support namespaces"):
        get_vector_store_adapter("qdrant").validate_connection(
            index_name="docs", namespace="tenant-a", endpoint_url="https://qdrant"
        )

###############################################################################
def test_score_contract_is_explicit_for_distance_and_dot_metrics() -> None:
    assert _score_from_metric("cosine", -1.0, raw_semantics="cosine_similarity") == 0.0
    assert _score_from_metric("cosine", 0.25, raw_semantics="distance") == 0.75
    assert _score_from_metric("l2", 3.0, raw_semantics="distance") == 0.25
    assert _score_from_metric("dot", 3.0, raw_semantics="similarity") == 3.0

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
def test_faiss_search_returns_explicit_score_semantics(tmp_path: Path) -> None:
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
        ],
    )

    hits = adapter.search(
        store=store,
        query_vector=[1.0, 0.0],
        top_k=2,
        score_threshold=0.0,
        filter_spec=None,
        include_metadata=True,
    )

    assert hits[0].id == "one"
    assert hits[0].score == 1.0
    assert hits[0].score_semantics == "normalized_similarity"

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
