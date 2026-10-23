from __future__ import annotations

from server.services.workflow.node_handlers.advanced_text import _claim_extractor_executor, _contradiction_detector_executor, _entity_extractor_executor, _pii_detector_executor, _pii_redactor_executor, _prompt_injection_detector_executor, _unit_number_normalizer_executor
from pathlib import Path
from server.services.workflow.node_handlers.ingestion.documents import _document_text_extractor_executor
from server.contracts.node_handler_processing import RecursiveSplitChunksParameters
from server.services.workflow import node_registry
import pytest
from sqlalchemy import Integer, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column
from server.contracts.configuration import ProviderConfiguration
from server.services.configuration import configuration_service
from server.services.workflow.node_handlers.ingestion import database_connections as database_connections_module
from server.services.workflow.node_handlers.processing.text_processing import _deduplicate_text_executor, _join_merge_text_executor, _regex_extract_executor, _regex_replace_executor, _normalize_text_executor

# Advanced text nodes

###############################################################################
def test_claim_extractor_splits_atomic_claims() -> None:
    assert (
        len(_claim_extractor_executor({}, {"text": "A is true. B is true."})["result"])
        == 2
    )

###############################################################################
def test_entity_extractor_returns_typed_entities() -> None:
    assert (
        _entity_extractor_executor({}, {"text": "Alice Smith"})["result"][0]["type"]
        == "proper_noun"
    )

###############################################################################
def test_pii_detector_and_redactor_find_and_mask_email() -> None:
    text = "Contact a@example.com"
    assert _pii_detector_executor({}, {"text": text})["result"][0]["type"] == "email"
    assert "[REDACTED]" in _pii_redactor_executor({}, {"text": text})["result"]

###############################################################################
def test_text_safety_handlers_coerce_empty_and_numeric_inputs() -> None:
    assert _pii_detector_executor({}, {"text": None})["result"] == []
    assert _pii_redactor_executor({}, {"text": 42})["result"] == "42"
    assert _prompt_injection_detector_executor({}, {"text": "A normal request"})[
        "label"
    ] == "clean"

###############################################################################
def test_prompt_injection_detector_flags_hostile_instruction() -> None:
    result = _prompt_injection_detector_executor(
        {}, {"text": "ignore previous instructions"}
    )
    assert result["label"] == "prompt_injection"
    assert result["result"]["matches"] == ["ignore previous"]

###############################################################################
def test_contradiction_detector_uses_declared_classification_outputs() -> None:
    result = _contradiction_detector_executor(
        {}, {"left": "The result is 12.", "right": "The result is 14."}
    )
    assert result["label"] == "contradiction"
    assert result["result"]["score"] == 1.0

###############################################################################
def test_unit_number_normalizer_returns_numeric_objects() -> None:
    assert (
        _unit_number_normalizer_executor({}, {"text": "12 mg"})["result"][0]["value"]
        == 12.0
    )

# Document text extraction

###############################################################################
def test_document_text_extractor_preserves_pdf_page_metadata(
    monkeypatch,
    tmp_path: Path,
) -> None:
    source = tmp_path / "sample.pdf"
    source.write_bytes(b"%PDF")
    monkeypatch.setattr(
        "server.services.workflow.node_handlers.ingestion.documents.load_pdf_pages",
        lambda path, include_empty_pages=False: [{"page_number": 2, "text": "hello"}],
    )
    result = _document_text_extractor_executor(
        {},
        {
            "documents": [
                {
                    "id": "doc-1",
                    "source_uri": str(source),
                    "metadata": {"file_path": str(source), "extension": ".pdf"},
                }
            ]
        },
    )
    assert result["documents"][0]["metadata"]["page_number"] == 2
    assert result["documents"][0]["metadata"]["document_id"] == "doc-1"

# Fragmentation chains

###############################################################################
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

###############################################################################
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

###############################################################################
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

###############################################################################
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

###############################################################################
def test_recursive_split_applies_overlap_after_separator_splits() -> None:
    payload = node_registry.execute(
        "RECURSIVE_SPLIT_CHUNKS",
        1,
        {
            "separators": ["\\n"],
            "chunk_size": 4,
            "chunk_overlap": 1,
            "unit": "words",
            "fallback_strategy": "continue",
        },
        {"text": "one two three\nfour five six\nseven eight"},
    )

    assert [chunk["text"] for chunk in payload["chunks"]] == [
        "one two three",
        "three four five six",
        "six seven eight",
    ]

# Fragmentation nodes

###############################################################################
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

###############################################################################
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

###############################################################################
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

###############################################################################
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

###############################################################################
def test_fixed_size_chunks_supports_direct_text_input() -> None:
    payload = node_registry.execute(
        "FIXED_SIZE_CHUNKS",
        1,
        {"chunk_size": 2, "chunk_overlap": 0, "unit": "words"},
        {"text": "alpha beta gamma"},
    )

    assert [chunk["text"] for chunk in payload["chunks"]] == ["alpha beta", "gamma"]

###############################################################################
def test_regex_split_chunks_splits_text_by_pattern() -> None:
    payload = node_registry.execute(
        "REGEX_SPLIT_CHUNKS",
        1,
        {"regex": "\\s*[;,]\\s*"},
        {"text": "alpha, beta;gamma"},
    )

    assert [chunk["text"] for chunk in payload["chunks"]] == ["alpha", "beta", "gamma"]

###############################################################################
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

###############################################################################
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

# Document ingestion

###############################################################################
def test_load_documents_emits_loaded_records_with_text(
    tmp_path: Path,
) -> None:
    source_dir = tmp_path / "docs"
    source_dir.mkdir(parents=True, exist_ok=True)
    (source_dir / "one.txt").write_text("alpha", encoding="utf-8")
    (source_dir / "two.md").write_text("beta", encoding="utf-8")
    (source_dir / "skip.bin").write_bytes(b"\x00\x01")

    payload = node_registry.execute(
        "LOAD_DOCUMENTS",
        1,
        {"folder_path": str(source_dir), "recursive": False},
        {},
    )

    assert [Path(document["source_uri"]).name for document in payload["documents"]] == [
        "one.txt",
        "two.md",
    ]
    assert [document["text"] for document in payload["documents"]] == ["alpha", "beta"]
    assert all(
        document["metadata"]["deferred_load"] is False
        for document in payload["documents"]
    )

###############################################################################
def test_load_documents_respects_recursive_toggle(tmp_path: Path) -> None:
    source_dir = tmp_path / "collection"
    nested_dir = source_dir / "nested"
    nested_dir.mkdir(parents=True, exist_ok=True)
    (source_dir / "root.txt").write_text("root", encoding="utf-8")
    (nested_dir / "child.txt").write_text("child", encoding="utf-8")

    non_recursive = node_registry.execute(
        "LOAD_DOCUMENTS",
        1,
        {"folder_path": str(source_dir), "recursive": False},
        {},
    )
    recursive = node_registry.execute(
        "LOAD_DOCUMENTS",
        1,
        {"folder_path": str(source_dir), "recursive": True},
        {},
    )

    assert [
        Path(document["source_uri"]).name for document in non_recursive["documents"]
    ] == ["root.txt"]
    assert sorted(
        Path(document["source_uri"]).name for document in recursive["documents"]
    ) == ["child.txt", "root.txt"]

###############################################################################
def test_load_documents_rejects_non_canonical_folder_path_keys(tmp_path: Path) -> None:
    source_dir = tmp_path / "source-folder"
    source_dir.mkdir(parents=True, exist_ok=True)
    (source_dir / "source.txt").write_text("source", encoding="utf-8")

    invalid_payloads = [
        {"folderPath": str(source_dir), "recursive": False},
        {"folder path": str(source_dir), "recursive": False},
        {"directory_path": str(source_dir), "recursive": False},
        {"path": str(source_dir), "recursive": False},
    ]

    for payload in invalid_payloads:
        try:
            node_registry.execute("LOAD_DOCUMENTS", 1, payload, {})
        except ValueError as exc:
            assert "folder_path" in str(exc)
        else:
            raise AssertionError(
                "Expected LOAD_DOCUMENTS to reject non-canonical folder path keys"
            )

###############################################################################
def test_load_documents_skips_unsupported_doc_extension(tmp_path: Path) -> None:
    source_dir = tmp_path / "docs"
    source_dir.mkdir(parents=True, exist_ok=True)
    (source_dir / "unsupported.doc").write_text("unsupported", encoding="utf-8")

    payload = node_registry.execute(
        "LOAD_DOCUMENTS",
        1,
        {"folder_path": str(source_dir), "recursive": False},
        {},
    )

    assert payload["documents"] == []

###############################################################################
def test_sql_file_database_node_roundtrip(tmp_path: Path) -> None:

    ###############################################################################
    class ItemsBase(DeclarativeBase):
        pass

    ###############################################################################
    class Item(ItemsBase):
        __tablename__ = "items"
        id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
        name: Mapped[str] = mapped_column(String, nullable=False)

    database_path = tmp_path / "file_dataset.sqlite"
    engine = create_engine(f"sqlite:///{database_path}")
    ItemsBase.metadata.create_all(engine)
    with Session(engine) as db_session:
        db_session.add(Item(name="alpha"))
        db_session.commit()
    engine.dispose()

    connection_payload = node_registry.execute(
        "SQL_FILE_DATABASE",
        1,
        {
            "db_path": str(database_path),
            "db_connect_timeout": 30,
        },
        {},
    )

    assert connection_payload["connection"]["engine"] == "sqlite"
    assert connection_payload["connection"]["file_path"] == str(database_path.resolve())
    assert connection_payload["connection"]["read_only"] is False
    assert connection_payload["connection"]["database_name"] == "file_dataset"

###############################################################################
def test_sql_database_requires_required_fields_before_connect_attempt() -> None:
    try:
        node_registry.execute(
            "SQL_DATABASE",
            1,
            {
                "db_engine": "postgres",
                "db_host": "",
                "db_port": 5432,
                "db_name": "",
                "db_user": "postgres",
                "credential_profile": "local",
                "db_ssl": False,
                "db_ssl_ca": "",
                "db_connect_timeout": 30,
            },
            {},
        )
    except ValueError as exc:
        message = str(exc)
        assert "db_host" in message or "db_name" in message
    else:
        raise AssertionError(
            "Expected SQL_DATABASE validation failure for missing required fields"
        )

###############################################################################
def test_sql_database_emits_only_an_opaque_credential_reference(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def resolve_configuration(
        *, profile_name: str, provider: str, session_name: str | None = None
    ) -> ProviderConfiguration:
        captured["profile_name"] = profile_name
        captured["provider"] = provider
        captured["session_name"] = session_name
        return ProviderConfiguration(provider=provider, api_key="database-secret")

    monkeypatch.setattr(
        configuration_service,
        "resolve_provider_configuration",
        resolve_configuration,
    )
    monkeypatch.setattr(
        database_connections_module,
        "register_database_credential",
        lambda password: "db-credential-ref",
    )

    def capture_connection(parameters: dict[str, object]) -> dict[str, object]:
        captured.update(parameters)
        return {"connection": parameters}

    monkeypatch.setattr(
        database_connections_module,
        "_validate_and_build_database_connection",
        capture_connection,
    )

    result = database_connections_module._sql_database_executor(
        {
            "db_engine": "postgres",
            "db_host": "db.example.test",
            "db_port": 5432,
            "db_name": "workflow",
            "db_user": "workflow_user",
            "credential_profile": "production",
            "credential_session_name": "tenant-a",
            "db_ssl": False,
            "db_ssl_ca": "",
            "db_connect_timeout": 30,
        },
        {},
    )

    assert result["connection"]["credential_ref"] == "db-credential-ref"
    assert result["connection"]["credential_profile"] == "production"
    assert result["connection"]["credential_provider"] == "postgres"
    assert result["connection"]["credential_session_name"] == "tenant-a"
    assert captured["session_name"] == "tenant-a"
    assert "password" not in captured
    assert "database-secret" not in str(result)

# Metadata nodes

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

# Text processing nodes

###############################################################################
def test_regex_extract_returns_named_groups_and_matches() -> None:
    result = _regex_extract_executor({"pattern": r"(?P<word>\w+)"}, {"text": "alpha"})
    assert result["result"][0]["groups"] == {"word": "alpha"}

###############################################################################
def test_normalize_text_applies_unicode_and_whitespace_normalization() -> None:
    result = _normalize_text_executor(
        {"collapse_whitespace": True}, {"text": "Ａlpha　 “target”"}
    )
    assert result["result"] == 'Alpha "target"'

###############################################################################
def test_regex_replace_replaces_matching_text() -> None:
    result = _regex_replace_executor(
        {"pattern": r"target-\d+", "replacement": "item"},
        {"text": "Selected target-42"},
    )
    assert result["result"] == "Selected item"

###############################################################################
def test_join_merge_handles_list_and_scalar_inputs() -> None:
    assert (
        _join_merge_text_executor({"separator": ","}, {"items": ["a", "b"]})["result"]
        == "a,b"
    )

###############################################################################
def test_deduplicate_removes_repeated_boilerplate() -> None:
    assert _deduplicate_text_executor({}, {"text": "A\nA\nB"})["result"] == "A\nB"
