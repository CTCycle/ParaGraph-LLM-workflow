from __future__ import annotations

import mimetypes
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from server.domain.node_handler_ingestion import (
    LOAD_DOCUMENTS_SUPPORTED_EXTENSIONS,
    LoadDocumentsParameters,
    SUPPORTED_DOCUMENT_EXTENSIONS,
)
from server.services.workflow.node_handlers.common import coerce_bool, coerce_text
from server.services.workflow.node_handlers.ingestion.files import (
    load_file_text,
    resolve_local_path,
)


def _make_document_id(source_uri: str) -> str:
    return str(uuid5(NAMESPACE_URL, source_uri))


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


def _directory_loader_executor(
    parameters: dict[str, Any], inputs: dict[str, Any]
) -> dict[str, Any]:
    _ = inputs
    directory = resolve_local_path(
        coerce_text(parameters.get("directory_path")).strip()
    )
    if not directory.exists() or not directory.is_dir():
        raise ValueError(f"Directory not found: {directory}")

    recursive = coerce_bool(parameters.get("recursive", True))
    include_extensions = parameters.get("include_extensions") or sorted(
        SUPPORTED_DOCUMENT_EXTENSIONS
    )
    if not isinstance(include_extensions, list):
        raise ValueError("include_extensions must be an array")
    extensions = {str(item).lower() for item in include_extensions}
    paths = directory.rglob("*") if recursive else directory.glob("*")

    documents: list[dict[str, Any]] = []
    for path in sorted(paths):
        if not path.is_file() or path.suffix.lower() not in extensions:
            continue
        text_content, mime_type = load_file_text(path)
        documents.append(
            _build_document(
                str(path.resolve()),
                text_content,
                mime_type,
                {
                    "extension": path.suffix.lower(),
                    "file_name": path.name,
                    "relative_path": str(path.relative_to(directory)),
                    "size_bytes": path.stat().st_size,
                },
            )
        )
    return {"documents": documents}


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
        documents.append(
            _build_document(
                resolved,
                "",
                mimetypes.guess_type(resolved)[0] or "text/plain",
                {
                    "extension": extension,
                    "file_name": path.name,
                    "relative_path": str(path.relative_to(directory)),
                    "size_bytes": path.stat().st_size,
                    "deferred_load": True,
                    "file_path": resolved,
                },
            )
        )
    return {"documents": documents}


__all__ = ["_directory_loader_executor", "_load_documents_executor"]
