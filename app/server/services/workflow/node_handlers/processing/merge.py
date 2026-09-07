from __future__ import annotations

from collections import defaultdict
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from server.contracts.node_handler_processing import MergeSmallChunksParameters
from server.services.workflow.node_handlers.processing.sources import (
    _iter_merge_fragments,
    _measure_text_size,
    _resolve_max_chunk_size,
)

###############################################################################
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
        return (
            current_parts,
            current_size,
            current_metadata,
            current_source_uri,
            current_merged_count,
        )

    chunk_text = joiner.join(part for part in current_parts if part).strip()
    if not chunk_text:
        return [], 0, {}, "", 0

    chunk_index = next_index_by_document[current_document_id]
    next_index_by_document[current_document_id] = chunk_index + 1
    merged_chunks.append(
        {
            "id": str(
                uuid5(
                    NAMESPACE_URL,
                    f"merge:{current_document_id}:{chunk_index}:{chunk_text}",
                )
            ),
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

###############################################################################
def _merge_small_chunks_executor(
    parameters: dict[str, Any], inputs: dict[str, Any]
) -> dict[str, Any]:
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

        if (
            current_document_id is not None
            and fragment_document_id != current_document_id
        ):
            (
                current_parts,
                current_size,
                current_metadata,
                current_source_uri,
                current_merged_count,
            ) = _flush_current_merged_chunk(
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
            current_metadata = (
                dict(fragment.get("metadata", {}))
                if isinstance(fragment.get("metadata"), dict)
                else {}
            )

        if not current_parts:
            current_parts = [fragment_text]
            current_size = fragment_size
            current_merged_count = 1
            if hard_limit is not None and current_size >= hard_limit:
                (
                    current_parts,
                    current_size,
                    current_metadata,
                    current_source_uri,
                    current_merged_count,
                ) = _flush_current_merged_chunk(
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
            elif (
                parsed.merge_strategy == "sequential"
                and current_size >= parsed.target_chunk_size
            ):
                (
                    current_parts,
                    current_size,
                    current_metadata,
                    current_source_uri,
                    current_merged_count,
                ) = _flush_current_merged_chunk(
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
            (
                current_parts,
                current_size,
                current_metadata,
                current_source_uri,
                current_merged_count,
            ) = _flush_current_merged_chunk(
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
            current_metadata = (
                dict(fragment.get("metadata", {}))
                if isinstance(fragment.get("metadata"), dict)
                else {}
            )
            current_parts = [fragment_text]
            current_size = fragment_size
            current_merged_count = 1
            if hard_limit is not None and current_size >= hard_limit:
                (
                    current_parts,
                    current_size,
                    current_metadata,
                    current_source_uri,
                    current_merged_count,
                ) = _flush_current_merged_chunk(
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
        if (
            parsed.merge_strategy == "greedy"
            and candidate_size > parsed.target_chunk_size
        ):
            current_gap = abs(parsed.target_chunk_size - current_size)
            candidate_gap = abs(parsed.target_chunk_size - candidate_size)
            if candidate_gap > current_gap:
                add_fragment = False

        if add_fragment:
            current_parts.append(fragment_text)
            current_size = candidate_size
            current_merged_count += 1
            if (
                parsed.merge_strategy == "sequential"
                and current_size >= parsed.target_chunk_size
            ):
                (
                    current_parts,
                    current_size,
                    current_metadata,
                    current_source_uri,
                    current_merged_count,
                ) = _flush_current_merged_chunk(
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

        (
            current_parts,
            current_size,
            current_metadata,
            current_source_uri,
            current_merged_count,
        ) = _flush_current_merged_chunk(
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
        current_metadata = (
            dict(fragment.get("metadata", {}))
            if isinstance(fragment.get("metadata"), dict)
            else {}
        )
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
        raise ValueError(
            "MERGE_SMALL_CHUNKS requires at least one document, chunk, or text input containing text"
        )
    return {"chunks": merged_chunks}
