from __future__ import annotations

from pathlib import Path

import pytest

from server.services.workflow import node_registry


def test_fixed_size_chunks_splits_deferred_documents_by_words(tmp_path: Path) -> None:
    source_dir = tmp_path / "docs"
    source_dir.mkdir(parents=True, exist_ok=True)
    (source_dir / "sample.txt").write_text(
        "one two three four five six", encoding="utf-8"
    )

    documents = node_registry.execute(
        "LOAD_DOCUMENTS",
        1,
        {"folder_path": str(source_dir), "recursive": False},
        {},
    )
    payload = node_registry.execute(
        "FIXED_SIZE_CHUNKS",
        1,
        {"chunk_size": 3, "chunk_overlap": 1, "unit": "words"},
        {"documents": documents["documents"]},
    )

    assert [chunk["text"] for chunk in payload["chunks"]] == [
        "one two three",
        "three four five",
        "five six",
    ]
    assert all(
        chunk["metadata"]["fragmentation_unit"] == "words"
        for chunk in payload["chunks"]
    )


def test_fixed_size_chunks_supports_chained_chunk_fragmentation_by_characters() -> None:
    payload = node_registry.execute(
        "FIXED_SIZE_CHUNKS",
        1,
        {"chunk_size": 4, "chunk_overlap": 1, "unit": "characters"},
        {
            "chunks": [
                {
                    "id": "parent-1",
                    "document_id": "doc-1",
                    "text": "ABCDEFGHIJ",
                    "source_uri": "memory://doc-1",
                    "chunk_index": 0,
                    "token_count": 1,
                    "metadata": {"origin": "test"},
                }
            ]
        },
    )

    assert [chunk["text"] for chunk in payload["chunks"]] == ["ABCD", "DEFG", "GHIJ"]
    assert all(chunk["document_id"] == "doc-1" for chunk in payload["chunks"])
    assert all(
        chunk["metadata"]["fragmentation_parent_chunk_id"] == "parent-1"
        for chunk in payload["chunks"]
    )


def test_fixed_size_chunks_rejects_invalid_overlap() -> None:
    with pytest.raises(
        ValueError, match="chunk_overlap must be smaller than chunk_size"
    ):
        node_registry.execute(
            "FIXED_SIZE_CHUNKS",
            1,
            {"chunk_size": 5, "chunk_overlap": 5, "unit": "words"},
            {
                "chunks": [
                    {
                        "id": "x",
                        "document_id": "d",
                        "text": "alpha beta",
                        "source_uri": "",
                        "chunk_index": 0,
                        "token_count": 2,
                        "metadata": {},
                    }
                ]
            },
        )


def test_fixed_size_chunks_requires_non_empty_input() -> None:
    with pytest.raises(
        ValueError, match="requires at least one document, chunk, or text input"
    ):
        node_registry.execute(
            "FIXED_SIZE_CHUNKS",
            1,
            {"chunk_size": 5, "chunk_overlap": 1, "unit": "words"},
            {},
        )


def test_fixed_size_chunks_supports_direct_text_input() -> None:
    payload = node_registry.execute(
        "FIXED_SIZE_CHUNKS",
        1,
        {"chunk_size": 2, "chunk_overlap": 0, "unit": "words"},
        {"text": "alpha beta gamma"},
    )

    assert [chunk["text"] for chunk in payload["chunks"]] == ["alpha beta", "gamma"]


def test_regex_split_chunks_splits_text_by_pattern() -> None:
    payload = node_registry.execute(
        "REGEX_SPLIT_CHUNKS",
        1,
        {"regex": "\\s*[;,]\\s*"},
        {"text": "alpha, beta;gamma"},
    )

    assert [chunk["text"] for chunk in payload["chunks"]] == ["alpha", "beta", "gamma"]


def test_regex_split_chunks_rejects_invalid_regex() -> None:
    with pytest.raises(
        ValueError, match="Invalid regex pattern for REGEX_SPLIT_CHUNKS"
    ):
        node_registry.execute(
            "REGEX_SPLIT_CHUNKS",
            1,
            {"regex": "["},
            {"text": "alpha beta"},
        )


def test_regex_split_chunks_requires_non_empty_input() -> None:
    with pytest.raises(
        ValueError, match="requires at least one document, chunk, or text input"
    ):
        node_registry.execute(
            "REGEX_SPLIT_CHUNKS",
            1,
            {"regex": "\\s+"},
            {},
        )

