from __future__ import annotations

import re
from collections.abc import Iterable, Iterator
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from pydantic import BaseModel, Field, field_validator, model_validator

from ParaGraph.server.services.workflow.node_handlers.base import NodeHandler
from ParaGraph.server.services.workflow.node_handlers.common import coerce_bool, strip_html
from ParaGraph.server.services.workflow.node_handlers.ingestion import _load_file_text, _resolve_local_path


_SENTENCE_BOUNDARY_PATTERN = re.compile(r"(?<=[.!?])\s+")


class TextCleanerParameters(BaseModel):
    strip_html_content: bool = True
    collapse_whitespace: bool = True


class ChunkerParameters(BaseModel):
    strategy: str = "token"
    chunk_size_tokens: int = Field(default=800, ge=100, le=4096)
    chunk_overlap_tokens: int = Field(default=400, ge=0, le=2048)
    respect_sentence_boundaries: bool = True

    @model_validator(mode="after")
    def validate_overlap(self) -> "ChunkerParameters":
        if self.chunk_overlap_tokens > self.chunk_size_tokens // 2:
            raise ValueError("chunk_overlap_tokens must be less than or equal to half the chunk size")
        if self.strategy not in {"token"}:
            raise ValueError("Only the 'token' chunking strategy is supported in phase 1")
        return self


class FixedSizeChunksParameters(BaseModel):
    chunk_size: int = Field(default=800, ge=1, le=100_000)
    chunk_overlap: int = Field(default=80, ge=0, le=99_999)
    unit: str = "words"

    @field_validator("unit")
    @classmethod
    def validate_unit(cls, value: str) -> str:
        normalized = str(value or "").strip().lower()
        if normalized not in {"words", "characters"}:
            raise ValueError("unit must be one of: words, characters")
        return normalized

    @model_validator(mode="after")
    def validate_overlap(self) -> "FixedSizeChunksParameters":
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")
        return self


def _clean_text(text: str, *, strip_html_content: bool, collapse_whitespace: bool) -> str:
    result = strip_html(text) if strip_html_content else text
    if collapse_whitespace:
        result = re.sub(r"\s+", " ", result).strip()
    return result


def _hydrate_document_text(document: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    metadata = dict(document.get("metadata", {})) if isinstance(document.get("metadata"), dict) else {}
    text = str(document.get("text", ""))
    if text.strip():
        return text, metadata

    source_uri = str(document.get("source_uri", "")).strip()
    path_candidate = str(metadata.get("file_path") or source_uri).strip()
    if not path_candidate:
        return text, metadata

    try:
        path = _resolve_local_path(path_candidate)
    except Exception:  # noqa: BLE001
        return text, metadata
    if not path.exists() or not path.is_file():
        return text, metadata

    try:
        loaded_text, _mime_type = _load_file_text(path)
    except Exception as exc:  # noqa: BLE001
        metadata["deferred_load_error"] = str(exc)
        return text, metadata

    metadata["deferred_load"] = False
    metadata["loaded_from_path"] = str(path)
    metadata["loaded_extension"] = path.suffix.lower()
    return loaded_text, metadata


def _text_cleaner_executor(parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    documents = inputs.get("documents") or []
    cleaned: list[dict[str, Any]] = []
    for document in documents:
        if not isinstance(document, dict):
            continue
        original_text, metadata = _hydrate_document_text(document)
        text = _clean_text(
            original_text,
            strip_html_content=coerce_bool(parameters.get("strip_html_content", True)),
            collapse_whitespace=coerce_bool(parameters.get("collapse_whitespace", True)),
        )
        metadata["cleaned"] = True
        cleaned.append(
            {
                "id": document.get("id", ""),
                "text": text,
                "source_uri": document.get("source_uri", ""),
                "mime_type": document.get("mime_type", "text/plain"),
                "metadata": metadata,
            }
        )
    return {"documents": cleaned}


def _chunk_text(text: str, chunk_size: int, chunk_overlap: int, respect_sentence_boundaries: bool) -> list[str]:
    if not text.strip():
        return []
    if not respect_sentence_boundaries:
        tokens = text.split()
        chunks: list[str] = []
        start = 0
        while start < len(tokens):
            end = min(start + chunk_size, len(tokens))
            chunks.append(" ".join(tokens[start:end]).strip())
            if end == len(tokens):
                break
            start = max(end - chunk_overlap, start + 1)
        return [chunk for chunk in chunks if chunk]

    sentences = [part.strip() for part in _SENTENCE_BOUNDARY_PATTERN.split(text) if part.strip()]
    chunks: list[str] = []
    current_tokens: list[str] = []

    for sentence in sentences:
        sentence_tokens = sentence.split()
        if len(sentence_tokens) > chunk_size:
            if current_tokens:
                _flush_current_chunk(current_tokens, chunks)
                overlap_tokens = current_tokens[-chunk_overlap:] if chunk_overlap > 0 else []
                current_tokens = list(overlap_tokens)
            start = 0
            while start < len(sentence_tokens):
                end = min(start + chunk_size, len(sentence_tokens))
                chunks.append(" ".join(sentence_tokens[start:end]).strip())
                if end == len(sentence_tokens):
                    current_tokens = sentence_tokens[max(0, end - chunk_overlap):end]
                    break
                start = max(end - chunk_overlap, start + 1)
            continue

        candidate = [*current_tokens, *sentence_tokens]
        if current_tokens and len(candidate) > chunk_size:
            _flush_current_chunk(current_tokens, chunks)
            overlap_tokens = current_tokens[-chunk_overlap:] if chunk_overlap > 0 else []
            current_tokens = [*overlap_tokens, *sentence_tokens]
        else:
            current_tokens = candidate

    _flush_current_chunk(current_tokens, chunks)
    return [chunk for chunk in chunks if chunk]


def _flush_current_chunk(current_tokens: list[str], chunks: list[str]) -> None:
    if current_tokens:
        chunks.append(" ".join(current_tokens).strip())


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


def _iter_fixed_size_segments(
    text: str,
    *,
    chunk_size: int,
    chunk_overlap: int,
    unit: str,
) -> Iterator[str]:
    if not text:
        return

    step = max(chunk_size - chunk_overlap, 1)
    if unit == "characters":
        start = 0
        text_length = len(text)
        while start < text_length:
            end = min(start + chunk_size, text_length)
            segment = text[start:end].strip()
            if segment:
                yield segment
            if end >= text_length:
                break
            start += step
        return

    tokens = text.split()
    if not tokens:
        return

    start = 0
    token_count = len(tokens)
    while start < token_count:
        end = min(start + chunk_size, token_count)
        segment = " ".join(tokens[start:end]).strip()
        if segment:
            yield segment
        if end >= token_count:
            break
        start += step


def _fixed_size_chunks_executor(parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    chunk_size = int(parameters.get("chunk_size", 800))
    chunk_overlap = int(parameters.get("chunk_overlap", 80))
    unit = str(parameters.get("unit", "words")).strip().lower()

    chunks: list[dict[str, Any]] = []
    emitted_count = 0

    for document in _iter_mapping_payload(inputs.get("documents")):
        document_id = str(document.get("id", "")).strip()
        source_uri = str(document.get("source_uri", "")).strip()
        text, metadata = _hydrate_document_text(document)
        for chunk_index, chunk_text in enumerate(
            _iter_fixed_size_segments(text, chunk_size=chunk_size, chunk_overlap=chunk_overlap, unit=unit)
        ):
            chunks.append(
                {
                    "id": str(uuid5(NAMESPACE_URL, f"document:{document_id}:{chunk_index}:{chunk_text}")),
                    "document_id": document_id,
                    "text": chunk_text,
                    "source_uri": source_uri,
                    "chunk_index": chunk_index,
                    "token_count": len(chunk_text.split()),
                    "metadata": {
                        **metadata,
                        "fragmentation_unit": unit,
                        "fragmentation_chunk_size": chunk_size,
                        "fragmentation_chunk_overlap": chunk_overlap,
                        "mime_type": document.get("mime_type", "text/plain"),
                    },
                }
            )
            emitted_count += 1

    for parent_chunk in _iter_mapping_payload(inputs.get("chunks")):
        parent_chunk_id = str(parent_chunk.get("id", "")).strip()
        parent_document_id = str(parent_chunk.get("document_id", "")).strip() or parent_chunk_id
        source_uri = str(parent_chunk.get("source_uri", "")).strip()
        text = str(parent_chunk.get("text", ""))
        metadata = (
            dict(parent_chunk.get("metadata", {}))
            if isinstance(parent_chunk.get("metadata"), dict)
            else {}
        )
        for chunk_index, chunk_text in enumerate(
            _iter_fixed_size_segments(text, chunk_size=chunk_size, chunk_overlap=chunk_overlap, unit=unit)
        ):
            chunks.append(
                {
                    "id": str(uuid5(NAMESPACE_URL, f"chunk:{parent_chunk_id}:{chunk_index}:{chunk_text}")),
                    "document_id": parent_document_id,
                    "text": chunk_text,
                    "source_uri": source_uri,
                    "chunk_index": chunk_index,
                    "token_count": len(chunk_text.split()),
                    "metadata": {
                        **metadata,
                        "fragmentation_unit": unit,
                        "fragmentation_chunk_size": chunk_size,
                        "fragmentation_chunk_overlap": chunk_overlap,
                        "fragmentation_parent_chunk_id": parent_chunk_id,
                    },
                }
            )
            emitted_count += 1

    if emitted_count == 0:
        raise ValueError("FIXED_SIZE_CHUNKS requires at least one document or chunk input containing text")
    return {"chunks": chunks}


def _chunker_executor(parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    documents = inputs.get("documents") or []
    chunk_size = int(parameters.get("chunk_size_tokens", 800))
    chunk_overlap = int(parameters.get("chunk_overlap_tokens", 400))
    respect_sentence_boundaries = bool(parameters.get("respect_sentence_boundaries", True))

    chunks: list[dict[str, Any]] = []
    for document in documents:
        if not isinstance(document, dict):
            continue
        document_id = str(document.get("id", ""))
        source_uri = str(document.get("source_uri", ""))
        text, metadata = _hydrate_document_text(document)
        for chunk_index, chunk_text in enumerate(
            _chunk_text(
                text,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                respect_sentence_boundaries=respect_sentence_boundaries,
            )
        ):
            chunks.append(
                {
                    "id": str(uuid5(NAMESPACE_URL, f"{document_id}:{chunk_index}:{chunk_text}")),
                    "document_id": document_id,
                    "text": chunk_text,
                    "source_uri": source_uri,
                    "chunk_index": chunk_index,
                    "token_count": len(chunk_text.split()),
                    "metadata": {
                        **metadata,
                        "mime_type": document.get("mime_type", "text/plain"),
                    },
                }
            )
    return {"chunks": chunks}


PROCESSING_HANDLERS = {
    "text_cleaner": NodeHandler(executor=_text_cleaner_executor, parameter_model=TextCleanerParameters),
    "chunker": NodeHandler(executor=_chunker_executor, parameter_model=ChunkerParameters),
    "fixed_size_chunks": NodeHandler(executor=_fixed_size_chunks_executor, parameter_model=FixedSizeChunksParameters),
}
