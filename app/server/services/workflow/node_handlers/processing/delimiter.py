from __future__ import annotations

from server.contracts.node_handler_processing import ByDelimiterChunksParameters
from server.services.workflow.node_handlers.processing.shared import (
    _apply_overflow,
    _build_chunk_records,
    _iter_split_by_delimiter,
    _resolve_delimiter,
)
from server.services.workflow.node_handlers.processing.sources import (
    _iter_sources,
    _measure_text_size,
    _resolve_max_chunk_size,
)


###############################################################################
def _by_delimiter_chunks_executor(
    parameters: dict[str, object], inputs: dict[str, object]
) -> dict[str, object]:
    parsed = ByDelimiterChunksParameters.model_validate(parameters)
    delimiter = _resolve_delimiter(parsed.delimiter)
    max_chunk_size = _resolve_max_chunk_size(parsed.max_chunk_size)

    chunks: list[dict[str, object]] = []
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
                    measure_text_size=_measure_text_size,
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
        raise ValueError(
            "BY_DELIMITER_CHUNKS requires at least one document, chunk, or text input containing text"
        )
    return {"chunks": chunks}


__all__ = ["_by_delimiter_chunks_executor"]
