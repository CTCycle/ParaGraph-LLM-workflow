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
def _chunk(text: str, size: int, overlap: int) -> list[dict[str, Any]]:
    size = max(1, size)
    overlap = max(0, min(overlap, size - 1))
    chunks: list[dict[str, Any]] = []
    start = 0
    index = 0
    while start < len(text):
        end = min(len(text), start + size)
        chunks.append(
            {
                "text": text[start:end],
                "chunk_id": f"chunk-{index}",
                "metadata": {"start": start, "end": end},
            }
        )
        if end >= len(text):
            break
        start = end - overlap
        index += 1
    return chunks

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
def _token_split_chunks_executor(
    parameters: dict[str, Any], inputs: dict[str, Any]
) -> dict[str, Any]:
    return {
        "chunks": _chunk(
            _text_of(inputs.get("text", inputs.get("value", ""))),
            int(parameters.get("max_tokens", 800)),
            int(parameters.get("overlap", 80)),
        )
    }

###############################################################################
def _semantic_split_chunks_executor(
    parameters: dict[str, Any], inputs: dict[str, Any]
) -> dict[str, Any]:
    _ = parameters
    text = _text_of(inputs.get("text", inputs.get("value", "")))
    parts = [
        part.strip()
        for part in re.split(r"\n\s*\n|(?<=[.!?])\s+", text)
        if part.strip()
    ]
    return {
        "chunks": [
            {"text": part, "chunk_id": f"chunk-{index}", "metadata": {}}
            for index, part in enumerate(parts)
        ]
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
def _language_detect_executor(
    parameters: dict[str, Any], inputs: dict[str, Any]
) -> dict[str, Any]:
    _ = parameters
    text = _text_of(inputs.get("text", ""))
    label = "en" if re.search(r"\b(the|and|of|to|in)\b", text.lower()) else "unknown"
    return {
        "label": label,
        "score": 0.6 if label == "en" else 0.0,
        "matches": [],
        "metadata": {},
    }

###############################################################################
def _token_counter_executor(
    parameters: dict[str, Any], inputs: dict[str, Any]
) -> dict[str, Any]:
    text = _text_of(inputs.get("text", inputs.get("value", "")))
    tokens = max(1, len(text.split()))
    return {
        "result": {
            "tokens": tokens,
            "characters": len(text),
            "estimated_cost": tokens * float(parameters.get("cost_per_token", 0.0)),
        }
    }

###############################################################################
def _truncate_to_budget_executor(
    parameters: dict[str, Any], inputs: dict[str, Any]
) -> dict[str, Any]:
    text = _text_of(inputs.get("text", ""))
    budget = max(1, int(parameters.get("max_tokens", 800)))
    words = text.split()
    mode = parameters.get("mode", "first")
    if len(words) <= budget:
        result = text
    elif mode == "last":
        result = " ".join(words[-budget:])
    elif mode == "balanced":
        half = budget // 2
        result = " ".join(words[:half] + words[-(budget - half) :])
    else:
        result = " ".join(words[:budget])
    return {"result": result}

###############################################################################
def _llm_summarize_executor(
    parameters: dict[str, Any], inputs: dict[str, Any]
) -> dict[str, Any]:
    max_sentences = int(parameters.get("max_sentences", 3))
    sentences = [
        part.strip()
        for part in re.split(r"(?<=[.!?])\s+", _text_of(inputs.get("text", "")))
        if part.strip()
    ]
    return {"result": " ".join(sentences[:max_sentences])}

###############################################################################
def _llm_rewrite_executor(
    parameters: dict[str, Any], inputs: dict[str, Any]
) -> dict[str, Any]:
    _ = parameters
    return {"result": _text_of(inputs.get("text", ""))}


TEXT_PROCESSING_HANDLERS = {
    "normalize_text": NodeHandler(executor=_normalize_text_executor),
    "regex_extract": NodeHandler(executor=_regex_extract_executor),
    "regex_replace": NodeHandler(executor=_regex_replace_executor),
    "token_split_chunks": NodeHandler(executor=_token_split_chunks_executor),
    "semantic_split_chunks": NodeHandler(executor=_semantic_split_chunks_executor),
    "join_merge_text": NodeHandler(executor=_join_merge_text_executor),
    "deduplicate_text": NodeHandler(executor=_deduplicate_text_executor),
    "metadata_attach": NodeHandler(executor=_metadata_attach_executor),
    "language_detect": NodeHandler(executor=_language_detect_executor),
    "token_counter": NodeHandler(executor=_token_counter_executor),
    "truncate_to_budget": NodeHandler(executor=_truncate_to_budget_executor),
    "llm_summarize": NodeHandler(executor=_llm_summarize_executor),
    "llm_rewrite": NodeHandler(executor=_llm_rewrite_executor),
}
