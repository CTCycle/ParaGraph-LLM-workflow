from __future__ import annotations

from typing import Any

from server.contracts.node_handler_http import HttpRequestParameters
from server.services.workflow.http_transport import SecureHttpTransport
from server.services.workflow.nodes.handler import NodeHandler

###############################################################################
def _http_request_executor(
    parameters: dict[str, Any], inputs: dict[str, Any]
) -> dict[str, Any]:
    parsed = HttpRequestParameters.model_validate(parameters)
    result = SecureHttpTransport().execute(parsed, inputs)
    return {
        "response": result,
        "json": result.get("json"),
        "text": result.get("text", ""),
    }


HTTP_HANDLERS = {
    "http_request": NodeHandler(
        executor=_http_request_executor, parameter_model=HttpRequestParameters
    )
}


__all__ = ["HTTP_HANDLERS", "_http_request_executor"]
