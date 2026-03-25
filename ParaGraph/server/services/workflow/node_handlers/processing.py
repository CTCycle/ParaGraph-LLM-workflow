from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable, Iterator
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from ParaGraph.server.domain.node_handler_processing import (
    ByDelimiterChunksParameters,
    ByStructureChunksParameters,
    FixedSizeChunksParameters,
    MergeSmallChunksParameters,
    RecursiveSplitChunksParameters,
    SentenceWindowChunksParameters,
)
from ParaGraph.server.services.workflow.node_handlers.base import NodeHandler
from ParaGraph.server.services.workflow.node_handlers.ingestion import _load_file_text, _resolve_local_path


_SENTENCE_BOUNDARY_PATTERN = re.compile(r"(?<=[.!?])\s+")
_PARAGRAPH_BOUNDARY_PATTERN = re.compile(r"\n\s*\n+")
_HEADING_PATTERN = re.compile(
    r"^\s*(#{1,6}\s+.+|(?:\d+(?:\.\d+)*)\s+[^\n]+|[A-Z][A-Z0-9 _:-]{2,})\s*$"
)
_DELIMITER_PRESETS: dict[str, str] = {
    "newline": "\n",
    "double_newline": "\n\n",
    "comma": ",",
    "period": ".",
    "semicolon": ";",
    "tab": "\t",
    "html_br": "<br>",
    "html_paragraph": "</p>",
}


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


def _iter_sources(inputs: dict[str, Any]) -> Iterator[dict[str, Any]]:
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
        parent_document_id = str(parent_chunk.get("document_id", "")).strip() or parent_chunk_id
        source_uri = str(parent_chunk.get("source_uri", "")).strip()
        text = str(parent_chunk.get("text", ""))
        if not text.strip():
            continue
        metadata = dict(parent_chunk.get("metadata", {})) if isinstance(parent_chunk.get("metadata"), dict) else {}
        yield {
            "scope": "chunk",
            "scope_id": parent_chunk_id,
            "document_id": parent_document_id,
            "source_uri": source_uri,
            "text": text,
            "metadata": metadata,
            "parent_chunk_id": parent_chunk_id,
        }


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


def _build_chunk_records(
    source: dict[str, Any],
    fragments: Iterable[str],
    *,
    strategy_name: str,
    metadata_updates: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    metadata_updates = metadata_updates or {}
    chunks: list[dict[str, Any]] = []
    base_metadata = dict(source.get("metadata", {}))
    for chunk_index, chunk_text in enumerate(fragment for fragment in fragments if fragment.strip()):
        record_metadata = {**base_metadata, **metadata_updates, "fragmentation_strategy": strategy_name}
        if source.get("scope") == "document":
            record_metadata.setdefault("mime_type", source.get("mime_type", "text/plain"))
            chunk_id_seed = f"document:{source.get('scope_id')}:{chunk_index}:{chunk_text}"
        else:
            parent_chunk_id = str(source.get("parent_chunk_id", "")).strip()
            record_metadata["fragmentation_parent_chunk_id"] = parent_chunk_id
            chunk_id_seed = f"chunk:{parent_chunk_id}:{chunk_index}:{chunk_text}"

        chunks.append(
            {
                "id": str(uuid5(NAMESPACE_URL, chunk_id_seed)),
                "document_id": str(source.get("document_id", "")),
                "text": chunk_text,
                "source_uri": str(source.get("source_uri", "")),
                "chunk_index": chunk_index,
                "token_count": len(chunk_text.split()),
                "metadata": record_metadata,
            }
        )
    return chunks


def _resolve_max_chunk_size(value: int) -> int | None:
    return value if value > 0 else None


def _measure_text_size(text: str, unit: str) -> int:
    if unit == "characters":
        return len(text)
    return len(text.split())


def _decode_escaped_text(value: str) -> str:
    try:
        return bytes(value, "utf-8").decode("unicode_escape")
    except UnicodeDecodeError:
        return value


def _resolve_delimiter(raw_delimiter: str) -> str:
    normalized = raw_delimiter.strip().lower()
    preset = _DELIMITER_PRESETS.get(normalized)
    if preset is not None:
        return preset
    decoded = _decode_escaped_text(raw_delimiter)
    if not decoded:
        raise ValueError("delimiter must resolve to a non-empty value")
    return decoded


def _iter_split_by_delimiter(text: str, delimiter: str, *, keep_delimiter: bool) -> Iterator[str]:
    if delimiter == "":
        yield text
        return
    start = 0
    while True:
        index = text.find(delimiter, start)
        if index < 0:
            yield text[start:]
            break
        end = index + len(delimiter) if keep_delimiter else index
        yield text[start:end]
        start = index + len(delimiter)


def _apply_overflow(
    fragment: str,
    *,
    max_chunk_size: int | None,
    overflow_strategy: str,
    unit: str,
    chunk_overlap: int = 0,
) -> Iterator[str]:
    cleaned = fragment.strip()
    if not cleaned:
        return
    if max_chunk_size is None or _measure_text_size(cleaned, unit) <= max_chunk_size:
        yield cleaned
        return

    if overflow_strategy == "discard":
        return
    if overflow_strategy == "emit_as_is":
        yield cleaned
        return

    for part in _iter_fixed_size_segments(
        cleaned,
        chunk_size=max_chunk_size,
        chunk_overlap=chunk_overlap,
        unit=unit,
    ):
        yield part


def _is_heading_line(line: str) -> bool:
    return bool(_HEADING_PATTERN.match(line))


def _split_heading_blocks(text: str) -> list[tuple[str, str]]:
    lines = text.splitlines()
    blocks: list[tuple[str, str]] = []
    active_heading: str | None = None
    active_lines: list[str] = []
    found_heading = False

    for line in lines:
        stripped = line.strip()
        if _is_heading_line(stripped):
            found_heading = True
            if active_heading is not None or active_lines:
                blocks.append((active_heading or "", "\n".join(active_lines).strip()))
            active_heading = stripped
            active_lines = []
            continue
        active_lines.append(line)

    if active_heading is not None or active_lines:
        blocks.append((active_heading or "", "\n".join(active_lines).strip()))

    return blocks if found_heading else []


def _iter_structure_segments(text: str, strategy: str) -> Iterator[str]:
    if strategy == "paragraph":
        for paragraph in _PARAGRAPH_BOUNDARY_PATTERN.split(text):
            cleaned = paragraph.strip()
            if cleaned:
                yield cleaned
        return

    heading_blocks = _split_heading_blocks(text)
    if heading_blocks:
        for heading, content in heading_blocks:
            if strategy == "heading_and_content":
                candidate = "\n".join(part for part in [heading.strip(), content.strip()] if part).strip()
            else:
                candidate = content.strip() or heading.strip()
            if candidate:
                yield candidate
        return

    for paragraph in _PARAGRAPH_BOUNDARY_PATTERN.split(text):
        cleaned = paragraph.strip()
        if cleaned:
            yield cleaned


def _iter_recursive_splits(
    text: str,
    *,
    separators: list[str],
    chunk_size: int,
    chunk_overlap: int,
    unit: str,
    fallback_strategy: str,
    separator_index: int = 0,
) -> Iterator[str]:
    cleaned_text = text.strip()
    if not cleaned_text:
        return
    if _measure_text_size(cleaned_text, unit) <= chunk_size:
        yield cleaned_text
        return

    if separator_index >= len(separators):
        if fallback_strategy == "force_split":
            yield from _iter_fixed_size_segments(
                cleaned_text,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                unit=unit,
            )
        else:
            yield cleaned_text
        return

    separator = _resolve_delimiter(separators[separator_index])
    split_iter = _iter_split_by_delimiter(cleaned_text, separator, keep_delimiter=False)
    first = next(split_iter, None)
    second = next(split_iter, None)

    if second is None:
        yield from _iter_recursive_splits(
            cleaned_text,
            separators=separators,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            unit=unit,
            fallback_strategy=fallback_strategy,
            separator_index=separator_index + 1,
        )
        return

    candidates: list[str] = [first, second, *split_iter]
    for candidate in candidates:
        if not candidate.strip():
            continue
        yield from _iter_recursive_splits(
            candidate,
            separators=separators,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            unit=unit,
            fallback_strategy=fallback_strategy,
            separator_index=separator_index + 1,
        )


def _iter_sentence_windows(text: str, *, sentences_per_chunk: int, sentence_overlap: int) -> Iterator[str]:
    sentences = [part.strip() for part in _SENTENCE_BOUNDARY_PATTERN.split(text) if part.strip()]
    if not sentences:
        return

    step = max(sentences_per_chunk - sentence_overlap, 1)
    start = 0
    sentence_count = len(sentences)
    while start < sentence_count:
        end = min(start + sentences_per_chunk, sentence_count)
        window = " ".join(sentences[start:end]).strip()
        if window:
            yield window
        if end >= sentence_count:
            break
        start += step


def _fixed_size_chunks_executor(parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    parsed = FixedSizeChunksParameters.model_validate(parameters)
    chunks: list[dict[str, Any]] = []
    for source in _iter_sources(inputs):
        chunks.extend(
            _build_chunk_records(
                source,
                _iter_fixed_size_segments(
                    source["text"],
                    chunk_size=parsed.chunk_size,
                    chunk_overlap=parsed.chunk_overlap,
                    unit=parsed.unit,
                ),
                strategy_name="fixed_size_chunks",
                metadata_updates={
                    "fragmentation_unit": parsed.unit,
                    "fragmentation_chunk_size": parsed.chunk_size,
                    "fragmentation_chunk_overlap": parsed.chunk_overlap,
                },
            )
        )
    if not chunks:
        raise ValueError("FIXED_SIZE_CHUNKS requires at least one document or chunk input containing text")
    return {"chunks": chunks}


def _by_delimiter_chunks_executor(parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    parsed = ByDelimiterChunksParameters.model_validate(parameters)
    delimiter = _resolve_delimiter(parsed.delimiter)
    max_chunk_size = _resolve_max_chunk_size(parsed.max_chunk_size)

    chunks: list[dict[str, Any]] = []
    for source in _iter_sources(inputs):
        segments: list[str] = []
        for split_value in _iter_split_by_delimiter(
            source["text"],
            delimiter,
            keep_delimiter=parsed.keep_delimiter,
        ):
            if parsed.drop_empty and not split_value.strip():
                continue
            segments.extend(
                _apply_overflow(
                    split_value,
                    max_chunk_size=max_chunk_size,
                    overflow_strategy=parsed.overflow_strategy,
                    unit="characters",
                )
            )

        chunks.extend(
            _build_chunk_records(
                source,
                segments,
                strategy_name="by_delimiter_chunks",
                metadata_updates={
                    "fragmentation_delimiter": parsed.delimiter,
                    "fragmentation_keep_delimiter": parsed.keep_delimiter,
                    "fragmentation_drop_empty": parsed.drop_empty,
                    "fragmentation_max_chunk_size": parsed.max_chunk_size,
                    "fragmentation_overflow_strategy": parsed.overflow_strategy,
                },
            )
        )

    if not chunks:
        raise ValueError("BY_DELIMITER_CHUNKS requires at least one document or chunk input containing text")
    return {"chunks": chunks}


def _by_structure_chunks_executor(parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    parsed = ByStructureChunksParameters.model_validate(parameters)
    max_chunk_size = _resolve_max_chunk_size(parsed.max_chunk_size)

    chunks: list[dict[str, Any]] = []
    for source in _iter_sources(inputs):
        segments: list[str] = []
        for segment in _iter_structure_segments(source["text"], parsed.strategy):
            segments.extend(
                _apply_overflow(
                    segment,
                    max_chunk_size=max_chunk_size,
                    overflow_strategy=parsed.overflow_strategy,
                    unit=parsed.unit,
                    chunk_overlap=parsed.chunk_overlap,
                )
            )
        chunks.extend(
            _build_chunk_records(
                source,
                segments,
                strategy_name="by_structure_chunks",
                metadata_updates={
                    "fragmentation_structure_strategy": parsed.strategy,
                    "fragmentation_unit": parsed.unit,
                    "fragmentation_max_chunk_size": parsed.max_chunk_size,
                    "fragmentation_chunk_overlap": parsed.chunk_overlap,
                    "fragmentation_overflow_strategy": parsed.overflow_strategy,
                },
            )
        )

    if not chunks:
        raise ValueError("BY_STRUCTURE_CHUNKS requires at least one document or chunk input containing text")
    return {"chunks": chunks}


def _recursive_split_chunks_executor(parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    parsed = RecursiveSplitChunksParameters.model_validate(parameters)
    chunks: list[dict[str, Any]] = []
    for source in _iter_sources(inputs):
        segments = _iter_recursive_splits(
            source["text"],
            separators=parsed.separators,
            chunk_size=parsed.chunk_size,
            chunk_overlap=parsed.chunk_overlap,
            unit=parsed.unit,
            fallback_strategy=parsed.fallback_strategy,
        )
        chunks.extend(
            _build_chunk_records(
                source,
                segments,
                strategy_name="recursive_split_chunks",
                metadata_updates={
                    "fragmentation_separators": parsed.separators,
                    "fragmentation_unit": parsed.unit,
                    "fragmentation_chunk_size": parsed.chunk_size,
                    "fragmentation_chunk_overlap": parsed.chunk_overlap,
                    "fragmentation_fallback_strategy": parsed.fallback_strategy,
                },
            )
        )

    if not chunks:
        raise ValueError("RECURSIVE_SPLIT_CHUNKS requires at least one document or chunk input containing text")
    return {"chunks": chunks}


def _sentence_window_chunks_executor(parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    parsed = SentenceWindowChunksParameters.model_validate(parameters)
    max_chunk_size = _resolve_max_chunk_size(parsed.max_chunk_size)
    chunks: list[dict[str, Any]] = []
    for source in _iter_sources(inputs):
        windows: list[str] = []
        for window in _iter_sentence_windows(
            source["text"],
            sentences_per_chunk=parsed.sentences_per_chunk,
            sentence_overlap=parsed.sentence_overlap,
        ):
            windows.extend(
                _apply_overflow(
                    window,
                    max_chunk_size=max_chunk_size,
                    overflow_strategy=parsed.overflow_strategy,
                    unit="characters",
                )
            )

        chunks.extend(
            _build_chunk_records(
                source,
                windows,
                strategy_name="sentence_window_chunks",
                metadata_updates={
                    "fragmentation_sentences_per_chunk": parsed.sentences_per_chunk,
                    "fragmentation_sentence_overlap": parsed.sentence_overlap,
                    "fragmentation_max_chunk_size": parsed.max_chunk_size,
                    "fragmentation_overflow_strategy": parsed.overflow_strategy,
                },
            )
        )

    if not chunks:
        raise ValueError("SENTENCE_WINDOW_CHUNKS requires at least one document or chunk input containing text")
    return {"chunks": chunks}


def _iter_merge_fragments(inputs: dict[str, Any]) -> Iterator[dict[str, Any]]:
    for source in _iter_sources(inputs):
        yield {
            "document_id": str(source.get("document_id", "")).strip(),
            "source_uri": str(source.get("source_uri", "")).strip(),
            "text": str(source.get("text", "")),
            "metadata": dict(source.get("metadata", {})) if isinstance(source.get("metadata"), dict) else {},
        }


def _flush_current_merged_chunk(
    *,
    current_document_id: str | None,
    current_parts: list[str],
    current_size: int,
    current_metadata: dict[str, Any],
    current_source_uri: str,
    current_merged_count: int,
    joiner: str,
    parsed: MergeSmallChunksParameters,
    next_index_by_document: dict[str, int],
    merged_chunks: list[dict[str, Any]],
) -> tuple[list[str], int, dict[str, Any], str, int]:
    if not current_parts or current_document_id is None:
        return current_parts, current_size, current_metadata, current_source_uri, current_merged_count

    chunk_text = joiner.join(part for part in current_parts if part).strip()
    if not chunk_text:
        return [], 0, {}, "", 0

    chunk_index = next_index_by_document[current_document_id]
    next_index_by_document[current_document_id] = chunk_index + 1
    merged_chunks.append(
        {
            "id": str(uuid5(NAMESPACE_URL, f"merge:{current_document_id}:{chunk_index}:{chunk_text}")),
            "document_id": current_document_id,
            "text": chunk_text,
            "source_uri": current_source_uri,
            "chunk_index": chunk_index,
            "token_count": len(chunk_text.split()),
            "metadata": {
                **current_metadata,
                "fragmentation_strategy": "merge_small_chunks",
                "merge_target_chunk_size": parsed.target_chunk_size,
                "merge_unit": parsed.unit,
                "merge_max_chunk_size": parsed.max_chunk_size,
                "merge_strategy": parsed.merge_strategy,
                "merge_preserve_boundaries": parsed.preserve_boundaries,
                "merge_input_count": current_merged_count,
            },
        }
    )
    return [], 0, {}, "", 0


def _merge_small_chunks_executor(parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    parsed = MergeSmallChunksParameters.model_validate(parameters)
    hard_limit = _resolve_max_chunk_size(parsed.max_chunk_size)
    joiner = "\n\n" if parsed.preserve_boundaries else " "
    merged_chunks: list[dict[str, Any]] = []
    next_index_by_document: dict[str, int] = defaultdict(int)

    current_document_id: str | None = None
    current_source_uri = ""
    current_parts: list[str] = []
    current_size = 0
    current_metadata: dict[str, Any] = {}
    current_merged_count = 0

    for fragment in _iter_merge_fragments(inputs):
        fragment_text = str(fragment.get("text", "")).strip()
        if not fragment_text:
            continue
        fragment_document_id = str(fragment.get("document_id", "")).strip()
        fragment_source_uri = str(fragment.get("source_uri", "")).strip()
        fragment_size = _measure_text_size(fragment_text, parsed.unit)

        if current_document_id is not None and fragment_document_id != current_document_id:
            current_parts, current_size, current_metadata, current_source_uri, current_merged_count = _flush_current_merged_chunk(
                current_document_id=current_document_id,
                current_parts=current_parts,
                current_size=current_size,
                current_metadata=current_metadata,
                current_source_uri=current_source_uri,
                current_merged_count=current_merged_count,
                joiner=joiner,
                parsed=parsed,
                next_index_by_document=next_index_by_document,
                merged_chunks=merged_chunks,
            )

        if current_document_id is None:
            current_document_id = fragment_document_id
        current_source_uri = current_source_uri or fragment_source_uri
        if not current_metadata:
            current_metadata = dict(fragment.get("metadata", {})) if isinstance(fragment.get("metadata"), dict) else {}

        if not current_parts:
            current_parts = [fragment_text]
            current_size = fragment_size
            current_merged_count = 1
            if hard_limit is not None and current_size >= hard_limit:
                current_parts, current_size, current_metadata, current_source_uri, current_merged_count = _flush_current_merged_chunk(
                    current_document_id=current_document_id,
                    current_parts=current_parts,
                    current_size=current_size,
                    current_metadata=current_metadata,
                    current_source_uri=current_source_uri,
                    current_merged_count=current_merged_count,
                    joiner=joiner,
                    parsed=parsed,
                    next_index_by_document=next_index_by_document,
                    merged_chunks=merged_chunks,
                )
                current_document_id = None
            elif parsed.merge_strategy == "sequential" and current_size >= parsed.target_chunk_size:
                current_parts, current_size, current_metadata, current_source_uri, current_merged_count = _flush_current_merged_chunk(
                    current_document_id=current_document_id,
                    current_parts=current_parts,
                    current_size=current_size,
                    current_metadata=current_metadata,
                    current_source_uri=current_source_uri,
                    current_merged_count=current_merged_count,
                    joiner=joiner,
                    parsed=parsed,
                    next_index_by_document=next_index_by_document,
                    merged_chunks=merged_chunks,
                )
                current_document_id = None
            continue

        candidate_parts = [*current_parts, fragment_text]
        candidate_text = joiner.join(candidate_parts).strip()
        candidate_size = _measure_text_size(candidate_text, parsed.unit)

        if hard_limit is not None and candidate_size > hard_limit:
            current_parts, current_size, current_metadata, current_source_uri, current_merged_count = _flush_current_merged_chunk(
                current_document_id=current_document_id,
                current_parts=current_parts,
                current_size=current_size,
                current_metadata=current_metadata,
                current_source_uri=current_source_uri,
                current_merged_count=current_merged_count,
                joiner=joiner,
                parsed=parsed,
                next_index_by_document=next_index_by_document,
                merged_chunks=merged_chunks,
            )
            current_document_id = fragment_document_id
            current_source_uri = fragment_source_uri
            current_metadata = dict(fragment.get("metadata", {})) if isinstance(fragment.get("metadata"), dict) else {}
            current_parts = [fragment_text]
            current_size = fragment_size
            current_merged_count = 1
            if hard_limit is not None and current_size >= hard_limit:
                current_parts, current_size, current_metadata, current_source_uri, current_merged_count = _flush_current_merged_chunk(
                    current_document_id=current_document_id,
                    current_parts=current_parts,
                    current_size=current_size,
                    current_metadata=current_metadata,
                    current_source_uri=current_source_uri,
                    current_merged_count=current_merged_count,
                    joiner=joiner,
                    parsed=parsed,
                    next_index_by_document=next_index_by_document,
                    merged_chunks=merged_chunks,
                )
                current_document_id = None
            continue

        add_fragment = True
        if parsed.merge_strategy == "greedy" and candidate_size > parsed.target_chunk_size:
            current_gap = abs(parsed.target_chunk_size - current_size)
            candidate_gap = abs(parsed.target_chunk_size - candidate_size)
            if candidate_gap > current_gap:
                add_fragment = False

        if add_fragment:
            current_parts.append(fragment_text)
            current_size = candidate_size
            current_merged_count += 1
            if parsed.merge_strategy == "sequential" and current_size >= parsed.target_chunk_size:
                current_parts, current_size, current_metadata, current_source_uri, current_merged_count = _flush_current_merged_chunk(
                    current_document_id=current_document_id,
                    current_parts=current_parts,
                    current_size=current_size,
                    current_metadata=current_metadata,
                    current_source_uri=current_source_uri,
                    current_merged_count=current_merged_count,
                    joiner=joiner,
                    parsed=parsed,
                    next_index_by_document=next_index_by_document,
                    merged_chunks=merged_chunks,
                )
                current_document_id = None
            continue

        current_parts, current_size, current_metadata, current_source_uri, current_merged_count = _flush_current_merged_chunk(
            current_document_id=current_document_id,
            current_parts=current_parts,
            current_size=current_size,
            current_metadata=current_metadata,
            current_source_uri=current_source_uri,
            current_merged_count=current_merged_count,
            joiner=joiner,
            parsed=parsed,
            next_index_by_document=next_index_by_document,
            merged_chunks=merged_chunks,
        )
        current_document_id = fragment_document_id
        current_source_uri = fragment_source_uri
        current_metadata = dict(fragment.get("metadata", {})) if isinstance(fragment.get("metadata"), dict) else {}
        current_parts = [fragment_text]
        current_size = fragment_size
        current_merged_count = 1

    _flush_current_merged_chunk(
        current_document_id=current_document_id,
        current_parts=current_parts,
        current_size=current_size,
        current_metadata=current_metadata,
        current_source_uri=current_source_uri,
        current_merged_count=current_merged_count,
        joiner=joiner,
        parsed=parsed,
        next_index_by_document=next_index_by_document,
        merged_chunks=merged_chunks,
    )

    if not merged_chunks:
        raise ValueError("MERGE_SMALL_CHUNKS requires at least one document or chunk input containing text")
    return {"chunks": merged_chunks}


PROCESSING_HANDLERS = {
    "fixed_size_chunks": NodeHandler(executor=_fixed_size_chunks_executor, parameter_model=FixedSizeChunksParameters),
    "by_delimiter_chunks": NodeHandler(executor=_by_delimiter_chunks_executor, parameter_model=ByDelimiterChunksParameters),
    "by_structure_chunks": NodeHandler(executor=_by_structure_chunks_executor, parameter_model=ByStructureChunksParameters),
    "recursive_split_chunks": NodeHandler(executor=_recursive_split_chunks_executor, parameter_model=RecursiveSplitChunksParameters),
    "sentence_window_chunks": NodeHandler(executor=_sentence_window_chunks_executor, parameter_model=SentenceWindowChunksParameters),
    "merge_small_chunks": NodeHandler(executor=_merge_small_chunks_executor, parameter_model=MergeSmallChunksParameters),
}
