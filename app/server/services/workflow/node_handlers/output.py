from __future__ import annotations

from typing import Any

from server.services.workflow.node_handlers.base import NodeHandler
from server.services.workflow.node_handlers.common import node_value_service


def _text_output_executor(
    parameters: dict[str, Any], inputs: dict[str, Any]
) -> dict[str, Any]:
    _ = parameters
    return {"result": node_value_service.coerce_text(inputs.get("text") or "")}


def _image_output_executor(
    parameters: dict[str, Any], inputs: dict[str, Any]
) -> dict[str, Any]:
    _ = parameters
    return {"result": inputs.get("image") or {}}


def _json_output_executor(
    parameters: dict[str, Any], inputs: dict[str, Any]
) -> dict[str, Any]:
    _ = parameters
    return {"result": inputs.get("value")}


OUTPUT_HANDLERS = {
    "text_output": NodeHandler(executor=_text_output_executor),
    "image_output": NodeHandler(executor=_image_output_executor),
    "json_output": NodeHandler(executor=_json_output_executor),
}
