from __future__ import annotations

from server.contracts.node_handler_processing import FixedSizeChunksParameters
from server.services.workflow.node_handlers.processing.shared import (
    _build_chunk_records,
    _iter_fixed_size_segments,
)
from server.services.workflow.node_handlers.processing.sources import _iter_sources


###############################################################################
def _fixed_size_chunks_executor(
    parameters: dict[str, object], inputs: dict[str, object]
) -> dict[str, object]:
    parsed = FixedSizeChunksParameters.model_validate(parameters)
    chunks: list[dict[str, object]] = []
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
        raise ValueError(
            "FIXED_SIZE_CHUNKS requires at least one document, chunk, or text input containing text"
        )
    return {"chunks": chunks}


__all__ = ["_fixed_size_chunks_executor"]
