from __future__ import annotations

import ipaddress
import os
import socket
from string import Template
from typing import Any
from urllib.parse import urlparse

import httpx

from server.domain.node_handler_http import (
    HttpDeleteParameters,
    HttpGetParameters,
    HttpPatchParameters,
    HttpPostParameters,
    HttpPutParameters,
)
from server.services.workflow.node_handlers.base import NodeHandler


SENSITIVE_HEADERS = {"authorization", "cookie", "set-cookie", "x-api-key"}


def _resolve_http_template_values(value: Any, variables: dict[str, Any]) -> Any:
    if isinstance(value, str):
        return Template(value).safe_substitute({key: str(val) for key, val in variables.items()})
    if isinstance(value, dict):
        return {key: _resolve_http_template_values(val, variables) for key, val in value.items()}
    if isinstance(value, list):
        return [_resolve_http_template_values(item, variables) for item in value]
    return value


def _validate_http_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("HTTP node URL must use http or https")
    allow_private = os.getenv("PARAGRAPH_ALLOW_PRIVATE_HTTP_NODES", "").lower() == "true"
    for result in socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80)):
        address = ipaddress.ip_address(result[4][0])
        if not allow_private and (address.is_loopback or address.is_private or address.is_link_local or address.is_multicast or address.is_unspecified):
            raise ValueError("HTTP node blocked private, localhost, link-local, multicast, or unspecified target")


def _build_query_params(parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    return _resolve_http_template_values(parameters.get("query", {}), inputs)


def _build_headers(parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, str]:
    return {str(key): str(value) for key, value in _resolve_http_template_values(parameters.get("headers", {}), inputs).items()}


def _build_json_body(parameters: dict[str, Any], inputs: dict[str, Any]) -> Any:
    body = parameters.get("json_body", inputs.get("json", inputs.get("body")))
    return _resolve_http_template_values(body, inputs)


def _parse_http_response(response: httpx.Response) -> dict[str, Any]:
    try:
        json_body = response.json()
    except ValueError:
        json_body = None
    return {
        "status_code": response.status_code,
        "headers": {key: ("[REDACTED]" if key.lower() in SENSITIVE_HEADERS else value) for key, value in response.headers.items()},
        "text": response.text,
        "json": json_body,
        "fields": json_body if isinstance(json_body, dict) else {},
        "ok": response.is_success,
        "error": None if response.is_success else response.text,
    }


def _execute_http_request(method: str, parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    url = _resolve_http_template_values(parameters.get("url", ""), inputs)
    _validate_http_url(str(url))
    with httpx.Client(timeout=float(parameters.get("timeout_seconds", 30.0)), follow_redirects=False) as client:
        response = client.request(
            method,
            str(url),
            params=_build_query_params(parameters, inputs),
            headers=_build_headers(parameters, inputs),
            json=_build_json_body(parameters, inputs) if method in {"POST", "PUT", "PATCH"} else None,
        )
    return _parse_http_response(response)


def _http_get_executor(parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    HttpGetParameters.model_validate(parameters)
    return _execute_http_request("GET", parameters, inputs)


def _http_post_executor(parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    HttpPostParameters.model_validate(parameters)
    return _execute_http_request("POST", parameters, inputs)


def _http_put_executor(parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    HttpPutParameters.model_validate(parameters)
    return _execute_http_request("PUT", parameters, inputs)


def _http_patch_executor(parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    HttpPatchParameters.model_validate(parameters)
    return _execute_http_request("PATCH", parameters, inputs)


def _http_delete_executor(parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    HttpDeleteParameters.model_validate(parameters)
    return _execute_http_request("DELETE", parameters, inputs)


HTTP_HANDLERS = {
    "http_get": NodeHandler(executor=_http_get_executor, parameter_model=HttpGetParameters),
    "http_post": NodeHandler(executor=_http_post_executor, parameter_model=HttpPostParameters),
    "http_put": NodeHandler(executor=_http_put_executor, parameter_model=HttpPutParameters),
    "http_patch": NodeHandler(executor=_http_patch_executor, parameter_model=HttpPatchParameters),
    "http_delete": NodeHandler(executor=_http_delete_executor, parameter_model=HttpDeleteParameters),
}
