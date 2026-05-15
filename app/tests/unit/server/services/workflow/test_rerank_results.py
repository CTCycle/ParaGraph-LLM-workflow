from __future__ import annotations

from server.services.workflow import node_registry


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


def _execute(
    parameters: dict[str, object], *, query: str | None = None
) -> dict[str, object]:
    inputs: dict[str, object] = {"results": _results_payload()}
    if query is not None:
        inputs["query"] = query
    return node_registry.execute("RERANK_RESULTS", 1, parameters, inputs)


def test_rerank_strategy_original_score_preserves_order_by_score() -> None:
    payload = _execute(
        {"strategy": "original_score", "score_mode": "replace", "top_k": 0}
    )
    hits = payload["results"]["hits"]
    assert [hit["id"] for hit in hits] == ["b", "c", "a"]


def test_rerank_strategy_term_overlap() -> None:
    payload = _execute(
        {"strategy": "term_overlap", "score_mode": "replace", "top_k": 0}
    )
    hits = payload["results"]["hits"]
    assert [hit["id"] for hit in hits] == ["c", "b", "a"]


def test_rerank_strategy_exact_phrase() -> None:
    payload = _execute(
        {"strategy": "exact_phrase", "score_mode": "replace", "top_k": 0}
    )
    hits = payload["results"]["hits"]
    assert hits[0]["id"] == "c"
    assert hits[0]["score"] == 1.0


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


def test_rerank_uses_results_query_when_query_input_is_missing() -> None:
    payload = _execute(
        {"strategy": "exact_phrase", "score_mode": "replace", "top_k": 0}, query=""
    )
    hits = payload["results"]["hits"]
    assert hits[0]["id"] == "c"
    assert payload["results"]["query"] == "fast api workflow"


def test_rerank_top_k_zero_and_bounded_truncation() -> None:
    all_hits_payload = _execute(
        {"strategy": "original_score", "score_mode": "replace", "top_k": 0}
    )
    top_two_payload = _execute(
        {"strategy": "original_score", "score_mode": "replace", "top_k": 2}
    )

    assert len(all_hits_payload["results"]["hits"]) == 3
    assert len(top_two_payload["results"]["hits"]) == 2

