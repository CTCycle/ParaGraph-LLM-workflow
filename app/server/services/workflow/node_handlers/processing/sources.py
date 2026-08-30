from __future__ import annotations

from collections.abc import Iterable, Iterator
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from server.services.workflow.node_handlers.ingestion import (
    load_file_text,
    resolve_local_path,
)


###############################################################################
def _hydrate_document_text(document: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    metadata = (
        dict(document.get("metadata", {}))
        if isinstance(document.get("metadata"), dict)
        else {}
    )
    text = str(document.get("text", ""))
    if text.strip():
        return text, metadata

    source_uri = str(document.get("source_uri", "")).strip()
    path_candidate = str(metadata.get("file_path") or source_uri).strip()
    if not path_candidate:
        return text, metadata

    try:
        path = resolve_local_path(path_candidate)
    except Exception:  # noqa: BLE001
        return text, metadata
    if not path.exists() or not path.is_file():
        return text, metadata

    try:
        loaded_text, _mime_type = load_file_text(path)
    except Exception as exc:  # noqa: BLE001
        metadata["deferred_load_error"] = str(exc)
        return text, metadata

    metadata["deferred_load"] = False
    metadata["loaded_from_path"] = str(path)
    metadata["loaded_extension"] = path.suffix.lower()
    return loaded_text, metadata


###############################################################################
def _iter_mapping_payload(raw_value: Any) -> Iterator[dict[str, Any]]:
    if raw_value is None:
        return
    if isinstance(raw_value, dict):
        yield raw_value
        return
    if isinstance(raw_value, (str, bytes)):
        return
    if not isinstance(raw_value, Iterable):
        return

    for item in raw_value:
        if isinstance(item, dict):
            yield item
            continue
        if isinstance(item, (str, bytes, dict)) or not isinstance(item, Iterable):
            continue
        for nested in item:
            if isinstance(nested, dict):
                yield nested


###############################################################################
def _iter_sources(inputs: dict[str, Any]) -> Iterator[dict[str, Any]]:
    text_input = str(inputs.get("text", ""))
    if text_input.strip():
        source_id = str(uuid5(NAMESPACE_URL, f"text:{text_input.strip()}"))
        yield {
            "scope": "text",
            "scope_id": source_id,
            "document_id": source_id,
            "source_uri": "",
            "text": text_input,
            "metadata": {},
            "mime_type": "text/plain",
        }

    for document in _iter_mapping_payload(inputs.get("documents")):
        document_id = str(document.get("id", "")).strip()
        source_uri = str(document.get("source_uri", "")).strip()
        text, metadata = _hydrate_document_text(document)
        if not text.strip():
            continue
        yield {
            "scope": "document",
            "scope_id": document_id,
            "document_id": document_id,
            "source_uri": source_uri,
            "text": text,
            "metadata": metadata,
            "mime_type": document.get("mime_type", "text/plain"),
        }

    for parent_chunk in _iter_mapping_payload(inputs.get("chunks")):
        parent_chunk_id = str(parent_chunk.get("id", "")).strip()
        parent_document_id = str(parent_chunk["document_id"]).strip()
        source_uri = str(parent_chunk.get("source_uri", "")).strip()
        text = str(parent_chunk.get("text", ""))
        if not text.strip():
            continue
        metadata = (
            dict(parent_chunk.get("metadata", {}))
            if isinstance(parent_chunk.get("metadata"), dict)
            else {}
        )
        yield {
            "scope": "chunk",
            "scope_id": parent_chunk_id,
            "document_id": parent_document_id,
            "source_uri": source_uri,
            "text": text,
            "metadata": metadata,
            "parent_chunk_id": parent_chunk_id,
        }


###############################################################################
def _resolve_max_chunk_size(value: int) -> int | None:
    return value if value > 0 else None


###############################################################################
def _measure_text_size(text: str, unit: str) -> int:
    if unit == "characters":
        return len(text)
    return len(text.split())


###############################################################################
def _iter_merge_fragments(inputs: dict[str, Any]) -> Iterator[dict[str, Any]]:
    for source in _iter_sources(inputs):
        yield {
            "document_id": str(source.get("document_id", "")).strip(),
            "source_uri": str(source.get("source_uri", "")).strip(),
            "text": str(source.get("text", "")),
            "metadata": dict(source.get("metadata", {}))
            if isinstance(source.get("metadata"), dict)
            else {},
        }
