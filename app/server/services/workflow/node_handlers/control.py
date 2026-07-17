from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from server.domain.node_handler_control import ControlParameters
from server.services.workflow.node_handlers.base import NodeHandler
from server.common.utils.values import coerce_text


_CACHE: dict[str, Any] = {}

###############################################################################
def _if_text_contains_executor(
    parameters: dict[str, Any], inputs: dict[str, Any]
) -> dict[str, Any]:
    parsed = ControlParameters.model_validate(parameters)
    text = coerce_text(inputs.get("text", inputs.get("value", "")))
    matched = (
        bool(re.search(parsed.keyword, text))
        if parameters.get("regex")
        else parsed.keyword.lower() in text.lower()
    )
    return {
        "true": text if matched else None,
        "false": text if not matched else None,
        "selected": "true" if matched else "false",
    }

###############################################################################
def _reduce_chunks_executor(
    parameters: dict[str, Any], inputs: dict[str, Any]
) -> dict[str, Any]:
    parsed = ControlParameters.model_validate(parameters)
    chunks = inputs.get("chunks", inputs.get("items", []))
    if not isinstance(chunks, list):
        chunks = [chunks]
    if parsed.operation == "json_array":
        return {"result": chunks}
    return {
        "result": "\n".join(
            coerce_text(item.get("text", item))
            if isinstance(item, dict)
            else coerce_text(item)
            for item in chunks
        )
    }

###############################################################################
def _cache_node_executor(
    parameters: dict[str, Any], inputs: dict[str, Any]
) -> dict[str, Any]:
    payload = json.dumps(
        {"parameters": parameters, "inputs": inputs}, sort_keys=True, default=str
    )
    key = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    if key not in _CACHE:
        _CACHE[key] = inputs.get("value", inputs)
    return {"result": _CACHE[key], "cache_key": key}

###############################################################################
def _human_review_gate_executor(
    parameters: dict[str, Any], inputs: dict[str, Any]
) -> dict[str, Any]:
    return {
        "paused": True,
        "pause_payload": {"parameters": parameters, "inputs": inputs},
    }

###############################################################################
def _trace_debug_viewer_executor(
    parameters: dict[str, Any], inputs: dict[str, Any]
) -> dict[str, Any]:
    _ = parameters
    redacted = json.loads(json.dumps(inputs, default=str))
    for key in list(redacted):
        if "key" in key.lower() or "token" in key.lower() or "password" in key.lower():
            redacted[key] = "[REDACTED]"
    return {"result": {"inputs": redacted}}


CONTROL_HANDLERS = {
    "if_text_contains": NodeHandler(
        executor=_if_text_contains_executor, parameter_model=ControlParameters
    ),
    "reduce_chunks": NodeHandler(
        executor=_reduce_chunks_executor, parameter_model=ControlParameters
    ),
    "cache_node": NodeHandler(executor=_cache_node_executor),
    "human_review_gate": NodeHandler(executor=_human_review_gate_executor),
    "trace_debug_viewer": NodeHandler(executor=_trace_debug_viewer_executor),
}
