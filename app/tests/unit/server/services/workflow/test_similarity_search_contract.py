from __future__ import annotations

import json
import re
from typing import Any

import pytest

from server.common import path as common_path
from server.contracts.node_handler_core import SimilaritySearchParameters
from server.contracts.node_catalog import VectorStoreCapabilities
from server.services.workflow import node_registry
import server.services.workflow.node_handlers.core.embeddings as embeddings_module

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
