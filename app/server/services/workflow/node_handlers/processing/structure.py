from __future__ import annotations

from server.domain.node_handler_processing import (
    ByStructureChunksParameters,
    RegexSplitChunksParameters,
)
from server.services.workflow.node_handlers.processing.shared import (
    _apply_overflow,
    _build_chunk_records,
    _iter_split_by_regex,
    _iter_structure_segments,
)
from server.services.workflow.node_handlers.processing.sources import (
    _iter_sources,
    _measure_text_size,
    _resolve_max_chunk_size,
)


def _by_structure_chunks_executor(
    parameters: dict[str, object], inputs: dict[str, object]
) -> dict[str, object]:
    parsed = ByStructureChunksParameters.model_validate(parameters)
    max_chunk_size = _resolve_max_chunk_size(parsed.max_chunk_size)

    chunks: list[dict[str, object]] = []
    for source in _iter_sources(inputs):
        segments: list[tuple[str, dict[str, object]]] = []
        for segment in _iter_structure_segments(source["text"], parsed.strategy):
            segment_text, segment_metadata = (
                segment if isinstance(segment, tuple) else (segment, {})
            )
            segments.extend(
                (
                    part,
                    dict(segment_metadata),
                )
                for part in _apply_overflow(
                    segment_text,
                    max_chunk_size=max_chunk_size,
                    overflow_strategy=parsed.overflow_strategy,
                    unit=parsed.unit,
                    chunk_overlap=parsed.chunk_overlap,
                    measure_text_size=_measure_text_size,
                )
            )
        for segment_text, segment_metadata in segments:
            chunks.extend(
                _build_chunk_records(
                    source,
                    [segment_text],
                    strategy_name="by_structure_chunks",
                    metadata_updates={
                        "fragmentation_structure_strategy": parsed.strategy,
                        "fragmentation_unit": parsed.unit,
                        "fragmentation_max_chunk_size": parsed.max_chunk_size,
                        "fragmentation_chunk_overlap": parsed.chunk_overlap,
                        "fragmentation_overflow_strategy": parsed.overflow_strategy,
                        **segment_metadata,
                    },
                )
            )

    if not chunks:
        raise ValueError(
            "BY_STRUCTURE_CHUNKS requires at least one document, chunk, or text input containing text"
        )
    return {"chunks": chunks}


def _regex_split_chunks_executor(
    parameters: dict[str, object], inputs: dict[str, object]
) -> dict[str, object]:
    parsed = RegexSplitChunksParameters.model_validate(parameters)
    chunks: list[dict[str, object]] = []
    for source in _iter_sources(inputs):
        chunks.extend(
            _build_chunk_records(
                source,
                _iter_split_by_regex(source["text"], parsed.regex),
                strategy_name="regex_split_chunks",
                metadata_updates={"fragmentation_regex": parsed.regex},
            )
        )

    if not chunks:
        raise ValueError(
            "REGEX_SPLIT_CHUNKS requires at least one document, chunk, or text input containing text"
        )
    return {"chunks": chunks}


__all__ = ["_by_structure_chunks_executor", "_regex_split_chunks_executor"]
