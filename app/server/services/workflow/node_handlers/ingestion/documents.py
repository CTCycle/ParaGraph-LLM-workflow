from __future__ import annotations

from typing import Any
from uuid import NAMESPACE_URL, uuid5

from server.contracts.node_handler_ingestion import (
    DocumentTextExtractorParameters,
    LOAD_DOCUMENTS_SUPPORTED_EXTENSIONS,
    LoadDocumentsParameters,
)
from server.services.workflow.node_handlers.ingestion.files import (
    load_docx_paragraphs,
    load_file_text,
    load_pdf_pages,
    resolve_local_path,
)


###############################################################################
def _make_document_id(source_uri: str) -> str:
    return str(uuid5(NAMESPACE_URL, source_uri))


###############################################################################
def _build_document(
    source_uri: str, text_content: str, mime_type: str, metadata: dict[str, Any]
) -> dict[str, Any]:
    return {
        "id": _make_document_id(source_uri),
        "text": text_content.strip(),
        "source_uri": source_uri,
        "mime_type": mime_type,
        "metadata": metadata,
    }


###############################################################################
def _load_documents_executor(
    parameters: dict[str, Any], inputs: dict[str, Any]
) -> dict[str, Any]:
    _ = inputs
    parsed = LoadDocumentsParameters.model_validate(parameters)
    directory = resolve_local_path(parsed.folder_path)
    if not directory.exists() or not directory.is_dir():
        raise ValueError(f"Directory not found: {directory}")

    paths = directory.rglob("*") if parsed.recursive else directory.glob("*")
    documents: list[dict[str, Any]] = []
    for path in sorted(paths):
        if not path.is_file():
            continue
        extension = path.suffix.lower()
        if extension not in LOAD_DOCUMENTS_SUPPORTED_EXTENSIONS:
            continue
        resolved = str(path.resolve())
        text_content, mime_type = load_file_text(path)
        documents.append(
            _build_document(
                resolved,
                text_content,
                mime_type,
                {
                    "extension": extension,
                    "file_name": path.name,
                    "relative_path": str(path.relative_to(directory)),
                    "size_bytes": path.stat().st_size,
                    "deferred_load": False,
                    "file_path": resolved,
                },
            )
        )
    return {"documents": documents}


###############################################################################
def _document_text_extractor_executor(
    parameters: dict[str, Any], inputs: dict[str, Any]
) -> dict[str, Any]:
    parsed = DocumentTextExtractorParameters.model_validate(parameters)
    raw_documents = inputs.get("documents")
    documents = raw_documents if isinstance(raw_documents, list) else [raw_documents]
    extracted: list[dict[str, Any]] = []
    for document in documents:
        if not isinstance(document, dict):
            continue
        source_uri = str(document.get("source_uri", "")).strip()
        metadata = (
            dict(document.get("metadata", {}))
            if isinstance(document.get("metadata"), dict)
            else {}
        )
        document_id = str(document["id"])
        path_candidate = str(metadata.get("file_path") or source_uri).strip()
        suffix = str(metadata.get("extension") or "").lower()
        if path_candidate:
            path = resolve_local_path(path_candidate)
            suffix = suffix or path.suffix.lower()
            if path.exists() and path.is_file() and suffix == ".pdf":
                for page in load_pdf_pages(
                    path, include_empty_pages=parsed.include_empty_pages
                ):
                    extracted.append(
                        {
                            **document,
                            "text": page["text"],
                            "metadata": {
                                **metadata,
                                "page_number": page["page_number"],
                                "source": source_uri,
                                "document_id": document_id,
                            },
                        }
                    )
                continue
            if path.exists() and path.is_file() and suffix == ".docx":
                for paragraph in load_docx_paragraphs(path):
                    extracted.append(
                        {
                            **document,
                            "text": paragraph["text"],
                            "metadata": {
                                **metadata,
                                "paragraph_index": paragraph["paragraph_index"],
                                "source": source_uri,
                                "document_id": document_id,
                            },
                        }
                    )
                continue
        extracted.append(
            {
                **document,
                "metadata": {
                    **metadata,
                    "source": source_uri,
                    "document_id": document_id,
                },
            }
        )
    return {"documents": extracted}


__all__ = [
    "_document_text_extractor_executor",
    "_load_documents_executor",
]
