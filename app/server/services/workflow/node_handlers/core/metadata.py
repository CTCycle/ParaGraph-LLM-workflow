from __future__ import annotations

from typing import Any

from server.domain.node_handler_core import MetadataParameters


def _metadata_for_record(
    record: dict[str, Any], parameters: MetadataParameters, input_metadata: dict[str, Any]
) -> dict[str, Any]:
    metadata = {**parameters.metadata, **input_metadata}
    if parameters.id_field:
        key = str(record.get(parameters.id_field) or "").strip()
        if key and key in parameters.metadata_by_id:
            metadata.update(parameters.metadata_by_id[key])
    else:
        for key_name in ("id", "document_id", "chunk_id"):
            key = str(record.get(key_name) or "").strip()
            if key and key in parameters.metadata_by_id:
                metadata.update(parameters.metadata_by_id[key])
                break
    return metadata


def _merge_record_metadata(
    record: dict[str, Any], parameters: MetadataParameters, input_metadata: dict[str, Any]
) -> dict[str, Any]:
    current = record.get("metadata") if isinstance(record.get("metadata"), dict) else {}
    incoming = _metadata_for_record(record, parameters, input_metadata)
    merged = incoming if parameters.merge_strategy == "replace" else {**current, **incoming}
    return {**record, "metadata": merged}


def _merge_document_metadata(
    document: dict[str, Any], parameters: MetadataParameters, input_metadata: dict[str, Any]
) -> dict[str, Any]:
    return _merge_record_metadata(document, parameters, input_metadata)


def _merge_chunk_metadata(
    chunk: dict[str, Any], parameters: MetadataParameters, input_metadata: dict[str, Any]
) -> dict[str, Any]:
    return _merge_record_metadata(chunk, parameters, input_metadata)


def _metadata_executor(
    parameters: dict[str, Any], inputs: dict[str, Any]
) -> dict[str, Any]:
    parsed = MetadataParameters.model_validate(parameters)
    input_metadata = inputs.get("metadata") if isinstance(inputs.get("metadata"), dict) else {}
    outputs: dict[str, Any] = {
        "metadata": {"metadata": {**parsed.metadata, **input_metadata}}
    }

    if parsed.scope in {"all", "documents"}:
        if isinstance(inputs.get("document"), dict):
            outputs["document"] = _merge_document_metadata(
                inputs["document"], parsed, input_metadata
            )
        if isinstance(inputs.get("documents"), list):
            outputs["documents"] = [
                _merge_document_metadata(item, parsed, input_metadata)
                for item in inputs["documents"]
                if isinstance(item, dict)
            ]

    if parsed.scope in {"all", "chunks"}:
        if isinstance(inputs.get("chunk"), dict):
            outputs["chunk"] = _merge_chunk_metadata(
                inputs["chunk"], parsed, input_metadata
            )
        if isinstance(inputs.get("chunks"), list):
            outputs["chunks"] = [
                _merge_chunk_metadata(item, parsed, input_metadata)
                for item in inputs["chunks"]
                if isinstance(item, dict)
            ]
    return outputs


__all__ = [
    "_metadata_executor",
    "_merge_chunk_metadata",
    "_merge_document_metadata",
    "_metadata_for_record",
]
