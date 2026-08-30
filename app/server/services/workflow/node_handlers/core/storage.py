from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any

from server.common import path as common_path
from server.common.security import ensure_path_within_root, is_cloud_deployment
from server.contracts.node_handler_core import (
    SaveAsFileParameters,
    SaveAsFolderParameters,
)
from server.common.utils.values import coerce_text
from server.services.workflow.node_handlers.core.constants import (
    SAVE_AS_FILE_CHUNK_SEPARATOR,
    SAVE_AS_FOLDER_INDEX_WIDTH,
)
from server.services.workflow.node_handlers.ingestion import (
    load_file_text,
    resolve_local_path,
)


###############################################################################
def _resolve_storage_path(
    raw_path: Any,
    *,
    label: str,
    relative_to_artifacts_root: bool = False,
) -> Path:
    storage_path = coerce_text(raw_path).strip()
    if not storage_path:
        raise ValueError(f"{label} is required. Select a local path.")
    candidate = Path(storage_path).expanduser()
    artifact_root = common_path.ARTIFACT_ROOT.resolve()
    if candidate.is_absolute():
        resolved = candidate.resolve()
        if is_cloud_deployment():
            return ensure_path_within_root(resolved, artifact_root, label=label)
        return resolved

    if relative_to_artifacts_root:
        resolved = (common_path.ARTIFACT_ROOT / candidate).resolve()
        return ensure_path_within_root(resolved, artifact_root, label=label)

    resolved = candidate.resolve()
    if is_cloud_deployment():
        return ensure_path_within_root(resolved, artifact_root, label=label)
    return resolved


###############################################################################
def _to_artifact_path(path: Path) -> str:
    artifact_root = common_path.ARTIFACT_ROOT.resolve()
    try:
        return str(path.resolve().relative_to(artifact_root))
    except ValueError:
        return str(path.resolve())


###############################################################################
def _safe_file_stem(raw_name: str, fallback: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", raw_name).strip("._-")
    return cleaned or fallback


###############################################################################
def _derive_item_name_from_source(source_uri: str, fallback: str) -> str:
    source = source_uri.strip()
    if not source:
        return fallback
    candidate = Path(source)
    if candidate.name:
        return candidate.stem or candidate.name
    return fallback


###############################################################################
def _extract_text_from_payload(
    payload: dict[str, Any], candidate_keys: tuple[str, ...]
) -> str:
    for key in candidate_keys:
        if key not in payload:
            continue
        raw_value = payload.get(key)
        if isinstance(raw_value, dict):
            nested = coerce_text(
                raw_value.get("text")
                or raw_value.get("content")
                or raw_value.get("chunk")
                or ""
            )
            if nested.strip():
                return nested
            continue
        text_value = coerce_text(raw_value or "")
        if text_value.strip():
            return text_value
    return ""


###############################################################################
def _collect_save_items(inputs: dict[str, Any]) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    text_payload = coerce_text(inputs.get("text") or "")
    if text_payload.strip():
        items.append({"name": "text_output", "text": text_payload})

    raw_documents = inputs.get("documents")
    documents: list[Any] = raw_documents if isinstance(raw_documents, list) else []
    for index, document in enumerate(documents, start=1):
        if not isinstance(document, dict):
            continue
        raw_metadata = document.get("metadata")
        metadata: dict[str, Any] = (
            raw_metadata if isinstance(raw_metadata, dict) else {}
        )
        text_content = _extract_text_from_payload(
            document, ("text", "content", "chunk")
        )
        if not text_content.strip():
            path_candidate = coerce_text(
                metadata.get("file_path") or document.get("source_uri") or ""
            ).strip()
            if path_candidate:
                path = resolve_local_path(path_candidate)
                if path.exists() and path.is_file():
                    text_content, _mime_type = load_file_text(path)
        if not text_content.strip():
            continue
        file_name = coerce_text(metadata.get("file_name") or "")
        source_uri = coerce_text(document.get("source_uri") or "")
        derived = (
            Path(file_name).stem
            if file_name
            else _derive_item_name_from_source(source_uri, f"document_{index}")
        )
        items.append({"name": derived or f"document_{index}", "text": text_content})

    raw_chunks = inputs.get("chunks")
    chunks: list[Any] = raw_chunks if isinstance(raw_chunks, list) else []
    for index, chunk in enumerate(chunks, start=1):
        if not isinstance(chunk, dict):
            continue
        text_content = _extract_text_from_payload(chunk, ("text", "content", "chunk"))
        if not text_content.strip():
            continue
        document_id = coerce_text(chunk.get("document_id") or "").strip()
        chunk_index = chunk.get("chunk_index")
        if isinstance(chunk_index, int) and chunk_index >= 0:
            derived = f"{document_id or 'chunk'}_{chunk_index}"
        else:
            derived = document_id or f"chunk_{index}"
        items.append({"name": derived, "text": text_content})

    return items


###############################################################################
def _ensure_extension(path: Path, extension: str) -> Path:
    if path.suffix.lower() == extension:
        return path
    if path.suffix:
        return path.with_suffix(extension)
    return Path(f"{path.as_posix()}{extension}")


###############################################################################
def _prepare_directory(path: Path) -> None:
    if path.exists() and path.is_file():
        path.unlink()
    path.mkdir(parents=True, exist_ok=True)


###############################################################################
def _prepare_file_destination(path: Path) -> None:
    if path.exists() and path.is_dir():
        shutil.rmtree(path)
    path.parent.mkdir(parents=True, exist_ok=True)


###############################################################################
def _build_client_side_save_as_file_artifact(
    parsed: SaveAsFileParameters,
    item_texts: list[str],
) -> dict[str, Any]:
    output_path = coerce_text(parsed.output_path).strip()
    if not output_path:
        raise ValueError("output_path is required. Select a local path.")

    destination = _ensure_extension(Path(output_path).expanduser(), parsed.extension)
    resolved_path = str(destination)
    return {
        "artifact": {
            "path": resolved_path,
            "files": [resolved_path],
            "count": 1,
            "extension": parsed.extension,
            "item_texts": item_texts,
        }
    }


###############################################################################
def _save_as_file_executor(
    parameters: dict[str, Any], inputs: dict[str, Any]
) -> dict[str, Any]:
    parsed = SaveAsFileParameters.model_validate(parameters)
    items = _collect_save_items(inputs)
    if not items:
        raise ValueError(
            "SAVE_AS_FILE requires at least one non-empty text, documents, or chunks input"
        )

    item_texts = [item["text"] for item in items]

    if parsed.client_side_write and not is_cloud_deployment():
        return _build_client_side_save_as_file_artifact(parsed, item_texts)

    target_root = _resolve_storage_path(
        parsed.output_path, label="output_path", relative_to_artifacts_root=True
    )
    destination = _ensure_extension(target_root, parsed.extension)
    _prepare_file_destination(destination)
    with destination.open("w", encoding="utf-8") as stream:
        for index, item_text in enumerate(item_texts):
            if index > 0:
                stream.write(SAVE_AS_FILE_CHUNK_SEPARATOR)
            stream.write(item_text)
    resolved_path = _to_artifact_path(destination)
    return {
        "artifact": {
            "path": resolved_path,
            "files": [resolved_path],
            "count": 1,
            "extension": parsed.extension,
        }
    }


###############################################################################
def _build_client_side_save_as_folder_artifact(
    parsed: SaveAsFolderParameters,
    item_count: int,
    item_texts: list[str],
) -> dict[str, Any]:
    output_path = coerce_text(parsed.output_path).strip()
    if not output_path:
        raise ValueError("output_path is required. Select a local path.")

    destination_dir = Path(output_path).expanduser()
    base_stem = _safe_file_stem(destination_dir.name, "output")
    files = [
        str(
            destination_dir
            / f"{base_stem}_{index:0{SAVE_AS_FOLDER_INDEX_WIDTH}d}{parsed.extension}"
        )
        for index in range(1, item_count + 1)
    ]
    return {
        "artifact": {
            "path": str(destination_dir),
            "files": files,
            "count": len(files),
            "extension": parsed.extension,
            "item_texts": item_texts,
        }
    }


###############################################################################
def _save_as_folder_executor(
    parameters: dict[str, Any], inputs: dict[str, Any]
) -> dict[str, Any]:
    parsed = SaveAsFolderParameters.model_validate(parameters)
    items = _collect_save_items(inputs)
    if not items:
        raise ValueError(
            "SAVE_AS_FOLDER requires at least one non-empty text, documents, or chunks input"
        )

    item_texts = [item["text"] for item in items]
    if parsed.client_side_write and not is_cloud_deployment():
        return _build_client_side_save_as_folder_artifact(
            parsed,
            len(items),
            item_texts,
        )

    destination_dir = _resolve_storage_path(
        parsed.output_path, label="output_path", relative_to_artifacts_root=True
    )
    _prepare_directory(destination_dir)
    base_stem = _safe_file_stem(destination_dir.name, "output")
    written_files: list[str] = []
    for index, item in enumerate(items, start=1):
        candidate_name = (
            f"{base_stem}_{index:0{SAVE_AS_FOLDER_INDEX_WIDTH}d}{parsed.extension}"
        )
        destination = destination_dir / candidate_name
        destination.write_text(item["text"], encoding="utf-8")
        written_files.append(_to_artifact_path(destination))

    return {
        "artifact": {
            "path": _to_artifact_path(destination_dir),
            "files": written_files,
            "count": len(written_files),
            "extension": parsed.extension,
        }
    }


###############################################################################
def _load_text_executor(
    parameters: dict[str, Any],
    inputs: dict[str, Any],
    *,
    text_loader=None,
) -> dict[str, Any]:
    _ = inputs
    source = _resolve_storage_path(parameters.get("storage_path"), label="storage_path")
    if not source.exists():
        raise ValueError(f"Text file not found: {source}")
    if not source.is_file():
        raise ValueError(f"storage_path must point to a file: {source}")
    loader = text_loader or load_file_text
    text_content, _mime_type = loader(source)
    return {"text": text_content}


__all__ = [
    "_collect_save_items",
    "_extract_text_from_payload",
    "_load_text_executor",
    "_resolve_storage_path",
    "_save_as_file_executor",
    "_save_as_folder_executor",
    "_to_artifact_path",
]
