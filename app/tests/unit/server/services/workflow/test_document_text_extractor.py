from __future__ import annotations

from pathlib import Path

from server.services.workflow.node_handlers.ingestion.documents import (
    _document_text_extractor_executor,
)


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
