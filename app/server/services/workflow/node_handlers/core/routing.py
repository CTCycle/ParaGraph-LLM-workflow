from __future__ import annotations

from typing import Any

from server.services.workflow.node_handlers.common import coerce_text

###############################################################################
def _tokenize_executor(
    parameters: dict[str, Any], inputs: dict[str, Any]
) -> dict[str, Any]:
    _ = parameters
    text = coerce_text(inputs.get("text") or "")
    tokens = [index for index, part in enumerate(text.split(), start=1) if part]
    return {"tokens": tokens}

###############################################################################
def _text_split_executor(
    parameters: dict[str, Any], inputs: dict[str, Any]
) -> dict[str, Any]:
    text = coerce_text(inputs.get("text") or "")
    delimiter = coerce_text(parameters.get("delimiter") or "\n")
    return {
        "segments": [
            segment.strip() for segment in text.split(delimiter) if segment.strip()
        ]
    }

###############################################################################
def _if_executor(parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    _ = parameters
    return {
        "result": inputs.get("true_value")
        if bool(inputs.get("condition"))
        else inputs.get("false_value")
    }

###############################################################################
def _router_executor(
    parameters: dict[str, Any], inputs: dict[str, Any]
) -> dict[str, Any]:
    value = inputs.get("value")
    expected = coerce_text(parameters.get("expected_value") or "")
    if coerce_text(value) == expected:
        return {"matched": value, "unmatched": None}
    return {"matched": None, "unmatched": value}


__all__ = [
    "_if_executor",
    "_router_executor",
    "_text_split_executor",
    "_tokenize_executor",
]

