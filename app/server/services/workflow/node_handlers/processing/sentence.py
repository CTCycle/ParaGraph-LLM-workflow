from __future__ import annotations

from server.contracts.node_handler_processing import SentenceWindowChunksParameters
from server.services.workflow.node_handlers.processing.shared import (
    _apply_overflow,
    _build_chunk_records,
    _iter_sentence_windows,
)
from server.services.workflow.node_handlers.processing.sources import (
    _iter_sources,
    _measure_text_size,
    _resolve_max_chunk_size,
)


###############################################################################
def _sentence_window_chunks_executor(
    parameters: dict[str, object], inputs: dict[str, object]
) -> dict[str, object]:
    parsed = SentenceWindowChunksParameters.model_validate(parameters)
    max_chunk_size = _resolve_max_chunk_size(parsed.max_chunk_size)
    chunks: list[dict[str, object]] = []
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
                    measure_text_size=_measure_text_size,
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
        raise ValueError(
            "SENTENCE_WINDOW_CHUNKS requires at least one document, chunk, or text input containing text"
        )
    return {"chunks": chunks}


__all__ = ["_sentence_window_chunks_executor"]
