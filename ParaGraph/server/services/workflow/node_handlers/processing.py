from __future__ import annotations

import re
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from pydantic import BaseModel, Field, model_validator

from ParaGraph.server.services.workflow.node_handlers.base import NodeHandler
from ParaGraph.server.services.workflow.node_handlers.common import coerce_bool, strip_html


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


def _clean_text(text: str, *, strip_html_content: bool, collapse_whitespace: bool) -> str:
    result = strip_html(text) if strip_html_content else text
    if collapse_whitespace:
        result = re.sub(r"\s+", " ", result).strip()
    return result


def _text_cleaner_executor(parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    documents = inputs.get("documents") or []
    cleaned: list[dict[str, Any]] = []
    for document in documents:
        metadata = dict(document.get("metadata", {})) if isinstance(document, dict) else {}
        original_text = str(document.get("text", "")) if isinstance(document, dict) else ""
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
        text = str(document.get("text", ""))
        for chunk_index, chunk_text in enumerate(
            _chunk_text(text, chunk_size=chunk_size, chunk_overlap=chunk_overlap, respect_sentence_boundaries=respect_sentence_boundaries)
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
                        **(document.get("metadata", {}) if isinstance(document.get("metadata"), dict) else {}),
                        "mime_type": document.get("mime_type", "text/plain"),
                    },
                }
            )
    return {"chunks": chunks}


PROCESSING_HANDLERS = {
    "text_cleaner": NodeHandler(executor=_text_cleaner_executor, parameter_model=TextCleanerParameters),
    "chunker": NodeHandler(executor=_chunker_executor, parameter_model=ChunkerParameters),
}
