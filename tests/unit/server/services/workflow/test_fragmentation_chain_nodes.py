from __future__ import annotations

from pathlib import Path

from ParaGraph.server.domain.node_handler_processing import (
    RecursiveSplitChunksParameters,
)
from ParaGraph.server.services.workflow import node_registry


def test_by_delimiter_chunks_loads_deferred_documents_from_file_paths(
    tmp_path: Path,
) -> None:
    source_dir = tmp_path / "docs"
    source_dir.mkdir(parents=True, exist_ok=True)
    source = source_dir / "deferred.txt"
    source.write_text(
        "Deferred loading keeps text on disk. It is split later.", encoding="utf-8"
    )

    documents = node_registry.execute(
        "LOAD_DOCUMENTS", 1, {"folder_path": str(source_dir), "recursive": False}, {}
    )
    chunks = node_registry.execute(
        "BY_DELIMITER_CHUNKS",
        1,
        {
            "delimiter": "period",
            "keep_delimiter": False,
            "drop_empty": True,
            "max_chunk_size": 0,
            "overflow_strategy": "split_further",
        },
        {"documents": documents["documents"]},
    )

    assert len(chunks["chunks"]) == 2
    assert chunks["chunks"][0]["text"] == "Deferred loading keeps text on disk"
    assert chunks["chunks"][1]["text"] == "It is split later"


def test_sentence_window_chunks_groups_sentences_from_upstream_chunks() -> None:
    payload = node_registry.execute(
        "SENTENCE_WINDOW_CHUNKS",
        1,
        {
            "sentences_per_chunk": 2,
            "sentence_overlap": 1,
            "max_chunk_size": 0,
            "overflow_strategy": "split_further",
        },
        {
            "chunks": [
                {
                    "id": "parent-1",
                    "document_id": "doc-1",
                    "text": "One sentence. Two sentence. Three sentence.",
                    "source_uri": "memory://doc-1",
                    "chunk_index": 0,
                    "token_count": 6,
                    "metadata": {},
                }
            ]
        },
    )

    assert [chunk["text"] for chunk in payload["chunks"]] == [
        "One sentence. Two sentence.",
        "Two sentence. Three sentence.",
    ]


def test_recursive_then_merge_small_chunks_supports_chained_fragmentation() -> None:
    recursive = node_registry.execute(
        "RECURSIVE_SPLIT_CHUNKS",
        1,
        {
            "separators": ["\\n\\n", "\\n"],
            "chunk_size": 3,
            "chunk_overlap": 1,
            "unit": "words",
            "fallback_strategy": "force_split",
        },
        {
            "chunks": [
                {
                    "id": "parent-1",
                    "document_id": "doc-1",
                    "text": "alpha beta gamma delta epsilon",
                    "source_uri": "memory://doc-1",
                    "chunk_index": 0,
                    "token_count": 5,
                    "metadata": {"origin": "test"},
                }
            ]
        },
    )

    merged = node_registry.execute(
        "MERGE_SMALL_CHUNKS",
        1,
        {
            "target_chunk_size": 4,
            "unit": "words",
            "max_chunk_size": 0,
            "merge_strategy": "sequential",
            "preserve_boundaries": False,
        },
        {"chunks": recursive["chunks"]},
    )

    assert [chunk["text"] for chunk in merged["chunks"]] == [
        "alpha beta gamma gamma delta epsilon",
    ]
    assert (
        merged["chunks"][0]["metadata"]["fragmentation_strategy"]
        == "merge_small_chunks"
    )
    assert merged["chunks"][0]["metadata"]["merge_input_count"] == 2


def test_recursive_split_chunk_separator_parsing_preserves_whitespace_entries() -> None:
    parsed = RecursiveSplitChunksParameters.model_validate(
        {
            "separators": '["\\n\\n", " "]',
            "chunk_size": 20,
            "chunk_overlap": 0,
            "unit": "words",
            "fallback_strategy": "continue",
        }
    )

    assert parsed.separators == ["\n\n", " "]
