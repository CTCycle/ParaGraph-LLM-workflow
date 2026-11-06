from __future__ import annotations

from server.contracts.node_handler_processing import RecursiveSplitChunksParameters
from server.services.workflow.node_handlers.processing.shared import (
    _build_chunk_records,
    _iter_recursive_splits,
)
from server.services.workflow.node_handlers.processing.sources import (
    _iter_sources,
    _measure_text_size,
)


###############################################################################
def _recursive_split_chunks_executor(
    parameters: dict[str, object], inputs: dict[str, object]
) -> dict[str, object]:
    parsed = RecursiveSplitChunksParameters.model_validate(parameters)
    chunks: list[dict[str, object]] = []
    for source in _iter_sources(inputs):
        segments = _iter_recursive_splits(
            source["text"],
            separators=parsed.separators,
            chunk_size=parsed.chunk_size,
            chunk_overlap=parsed.chunk_overlap,
            unit=parsed.unit,
            fallback_strategy=parsed.fallback_strategy,
            measure_text_size=_measure_text_size,
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
        raise ValueError(
            "RECURSIVE_SPLIT_CHUNKS requires at least one document, chunk, or text input containing text"
        )
    return {"chunks": chunks}


__all__ = ["_recursive_split_chunks_executor"]
