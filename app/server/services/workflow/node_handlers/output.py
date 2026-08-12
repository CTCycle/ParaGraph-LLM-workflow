from __future__ import annotations

from typing import Any

from server.domain.node_handler import NodeHandler

###############################################################################
def _text_output_executor(
    parameters: dict[str, Any], inputs: dict[str, Any]
) -> dict[str, Any]:
    _ = parameters, inputs
    return {}

###############################################################################
def _json_output_executor(
    parameters: dict[str, Any], inputs: dict[str, Any]
) -> dict[str, Any]:
    _ = parameters, inputs
    return {}


OUTPUT_HANDLERS = {
    "text_output": NodeHandler(executor=_text_output_executor),
    "json_output": NodeHandler(executor=_json_output_executor),
}
