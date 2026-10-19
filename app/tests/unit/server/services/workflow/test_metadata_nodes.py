from __future__ import annotations

from server.services.workflow import node_registry

###############################################################################
def test_metadata_node_merges_existing_and_per_record_metadata() -> None:
    result = node_registry.execute(
        "METADATA",
        1,
        {
            "scope": "chunks",
            "merge_strategy": "merge",
            "metadata": {"source": "fixture", "reviewed": True},
            "metadata_by_id": {"chunk-1": {"page_number": 4}},
        },
        {
            "chunks": [
                {
                    "id": "chunk-1",
                    "document_id": "doc-1",
                    "text": "first",
                    "source_uri": "fixture://doc-1",
                    "chunk_index": 0,
                    "token_count": 1,
                    "metadata": {"source": "old", "language": "en"},
                },
                {
                    "id": "chunk-2",
                    "document_id": "doc-2",
                    "text": "second",
                    "source_uri": "fixture://doc-2",
                    "chunk_index": 0,
                    "token_count": 1,
                    "metadata": {"language": "it"},
                },
            ]
        },
    )

    assert result["chunks"][0]["metadata"] == {
        "source": "fixture",
        "language": "en",
        "reviewed": True,
        "page_number": 4,
    }
    assert result["chunks"][1]["metadata"] == {
        "language": "it",
        "source": "fixture",
        "reviewed": True,
    }

###############################################################################
def test_metadata_node_replace_discards_previous_record_metadata() -> None:
    result = node_registry.execute(
        "METADATA",
        1,
        {
            "scope": "chunks",
            "merge_strategy": "replace",
            "metadata": {"source": "replacement"},
        },
        {
            "chunks": [
                {
                    "id": "chunk-1",
                    "document_id": "doc-1",
                    "text": "first",
                    "source_uri": "fixture://doc-1",
                    "chunk_index": 0,
                    "token_count": 1,
                    "metadata": {"old": "value"},
                }
            ]
        },
    )

    assert result["chunks"][0]["metadata"] == {"source": "replacement"}
