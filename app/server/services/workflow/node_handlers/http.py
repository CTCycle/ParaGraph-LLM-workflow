from __future__ import annotations

from functools import partial
from typing import Any

from server.contracts.node_handler_http import (
    HttpDeleteParameters,
    HttpGetParameters,
    HttpPatchParameters,
    HttpPostParameters,
    HttpPutParameters,
    HttpRequestParameters,
)
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


def _http_method_executor(
    method: str, parameters: dict[str, Any], inputs: dict[str, Any]
) -> dict[str, Any]:
    return _http_request_executor(
        {**parameters, "method": method}, inputs
    )


HTTP_HANDLERS = {
    "http_request": NodeHandler(
        executor=_http_request_executor, parameter_model=HttpRequestParameters
    ),
    "http_get": NodeHandler(
        executor=partial(_http_method_executor, "GET"),
        parameter_model=HttpGetParameters,
    ),
    "http_post": NodeHandler(
        executor=partial(_http_method_executor, "POST"),
        parameter_model=HttpPostParameters,
    ),
    "http_put": NodeHandler(
        executor=partial(_http_method_executor, "PUT"),
        parameter_model=HttpPutParameters,
    ),
    "http_patch": NodeHandler(
        executor=partial(_http_method_executor, "PATCH"),
        parameter_model=HttpPatchParameters,
    ),
    "http_delete": NodeHandler(
        executor=partial(_http_method_executor, "DELETE"),
        parameter_model=HttpDeleteParameters,
    ),
}


__all__ = ["HTTP_HANDLERS", "_http_request_executor", "_http_method_executor"]
