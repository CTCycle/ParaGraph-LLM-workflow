from __future__ import annotations

import re
import unicodedata
from typing import Any

from server.services.workflow.node_handlers.base import NodeHandler
from server.common.utils.values import coerce_text

###############################################################################
def _records(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]

###############################################################################
def _text_of(value: Any) -> str:
    if isinstance(value, dict):
        return coerce_text(
            value.get("text") or value.get("content") or value.get("chunk") or ""
        )
    return coerce_text(value)

###############################################################################
def _normalize_text_executor(
    parameters: dict[str, Any], inputs: dict[str, Any]
) -> dict[str, Any]:
    text = unicodedata.normalize(
        "NFKC", _text_of(inputs.get("text", inputs.get("value", "")))
    )
    text = (
        text.replace("\u201c", '"')
        .replace("\u201d", '"')
        .replace("\u2018", "'")
        .replace("\u2019", "'")
    )
    if parameters.get("collapse_whitespace", True):
        text = re.sub(r"\s+", " ", text).strip()
    return {"result": text}

###############################################################################
def _regex_extract_executor(
    parameters: dict[str, Any], inputs: dict[str, Any]
) -> dict[str, Any]:
    pattern = coerce_text(parameters.get("pattern", ""))
    text = _text_of(inputs.get("text", inputs.get("value", "")))
    flags = re.IGNORECASE if parameters.get("ignore_case", False) else 0
    matches = []
    for match in re.finditer(pattern, text, flags):
        matches.append(
            {
                "match": match.group(0),
                "groups": match.groupdict(),
                "span": list(match.span()),
            }
        )
    return {"result": matches}

###############################################################################
def _regex_replace_executor(
    parameters: dict[str, Any], inputs: dict[str, Any]
) -> dict[str, Any]:
    return {
        "result": re.sub(
            coerce_text(parameters.get("pattern", "")),
            coerce_text(parameters.get("replacement", "")),
            _text_of(inputs.get("text", "")),
        )
    }

###############################################################################
def _join_merge_text_executor(
    parameters: dict[str, Any], inputs: dict[str, Any]
) -> dict[str, Any]:
    separator = coerce_text(parameters.get("separator", "\n"))
    values = _records(inputs.get("items", inputs.get("texts", inputs.get("value", []))))
    return {"result": separator.join(_text_of(item) for item in values)}

###############################################################################
def _deduplicate_text_executor(
    parameters: dict[str, Any], inputs: dict[str, Any]
) -> dict[str, Any]:
    _ = parameters
    seen: set[str] = set()
    kept: list[str] = []
    for line in _text_of(inputs.get("text", "")).splitlines():
        normalized = " ".join(line.lower().split())
        if normalized and normalized not in seen:
            seen.add(normalized)
            kept.append(line)
    return {"result": "\n".join(kept)}

###############################################################################
def _metadata_attach_executor(
    parameters: dict[str, Any], inputs: dict[str, Any]
) -> dict[str, Any]:
    metadata = (
        parameters.get("metadata")
        if isinstance(parameters.get("metadata"), dict)
        else {}
    )
    value = inputs.get("value", inputs.get("document", inputs.get("chunk", {})))
    if isinstance(value, list):
        return {
            "result": [
                {**item, "metadata": {**item.get("metadata", {}), **metadata}}
                if isinstance(item, dict)
                else {"text": _text_of(item), "metadata": metadata}
                for item in value
            ]
        }
    if isinstance(value, dict):
        return {
            "result": {**value, "metadata": {**value.get("metadata", {}), **metadata}}
        }
    return {"result": {"text": _text_of(value), "metadata": metadata}}

###############################################################################
TEXT_PROCESSING_HANDLERS = {
    "normalize_text": NodeHandler(executor=_normalize_text_executor),
    "regex_extract": NodeHandler(executor=_regex_extract_executor),
    "regex_replace": NodeHandler(executor=_regex_replace_executor),
    "join_merge_text": NodeHandler(executor=_join_merge_text_executor),
    "deduplicate_text": NodeHandler(executor=_deduplicate_text_executor),
    "metadata_attach": NodeHandler(executor=_metadata_attach_executor),
}
