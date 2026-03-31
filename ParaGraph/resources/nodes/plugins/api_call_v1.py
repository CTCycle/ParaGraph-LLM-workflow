from __future__ import annotations

from typing import Any

import httpx

from ParaGraph.server.services.workflow.node_handlers.common import coerce_bool, coerce_float, coerce_text


def _pick_override(inputs: dict[str, Any], input_key: str, parameters: dict[str, Any], parameter_key: str) -> Any:
    if input_key in inputs and inputs[input_key] is not None:
        return inputs[input_key]
    return parameters.get(parameter_key)


def _as_object(value: Any, *, label: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def _normalize_headers(headers: dict[str, Any]) -> dict[str, str]:
    return {str(key): coerce_text(value) for key, value in headers.items()}


def _parse_json_if_available(response: httpx.Response) -> Any:
    content_type = (response.headers.get("content-type") or "").lower()
    if "json" not in content_type:
        raise ValueError("Response is not JSON")
    return response.json()


def execute(parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    url = coerce_text(_pick_override(inputs, "url", parameters, "url")).strip()
    if not url:
        raise ValueError("url is required")

    method = coerce_text(parameters.get("method", "GET")).strip().upper() or "GET"
    if method not in {"GET", "POST"}:
        raise ValueError("method must be GET or POST")

    headers = _normalize_headers(_as_object(_pick_override(inputs, "headers_in", parameters, "headers"), label="headers"))
    params = _as_object(_pick_override(inputs, "params_in", parameters, "params"), label="params")
    body = inputs.get("body")

    auth_mode = coerce_text(parameters.get("auth_mode", "none")).strip().lower()
    if auth_mode not in {"none", "bearer", "basic"}:
        raise ValueError("auth_mode must be one of: none, bearer, basic")

    auth: httpx.Auth | None = None
    if auth_mode == "bearer":
        token = coerce_text(parameters.get("token")).strip()
        if not token:
            raise ValueError("token is required when auth_mode is bearer")
        headers = {**headers, "Authorization": f"Bearer {token}"}
    elif auth_mode == "basic":
        username = coerce_text(parameters.get("username")).strip()
        password = coerce_text(parameters.get("password"))
        if not username:
            raise ValueError("username is required when auth_mode is basic")
        auth = httpx.BasicAuth(username=username, password=password)

    timeout_s = max(0.1, coerce_float(parameters.get("timeout_s"), 15.0))
    follow_redirects = coerce_bool(parameters.get("follow_redirects", True))
    raise_for_status = coerce_bool(parameters.get("raise_for_status", False))
    response_mode = coerce_text(parameters.get("response_mode", "auto")).strip().lower() or "auto"
    if response_mode not in {"auto", "json", "text"}:
        raise ValueError("response_mode must be one of: auto, json, text")

    with httpx.Client(timeout=timeout_s, follow_redirects=follow_redirects) as client:
        request_kwargs: dict[str, Any] = {
            "method": method,
            "url": url,
            "headers": headers,
            "params": params,
            "auth": auth,
        }
        if method == "POST":
            if body is not None:
                request_kwargs["json"] = body
        response = client.request(**request_kwargs)

    if raise_for_status:
        response.raise_for_status()

    content_type = response.headers.get("content-type") or ""
    response_payload = {
        "status_code": response.status_code,
        "final_url": str(response.url),
        "headers": dict(response.headers),
        "elapsed_ms": round(response.elapsed.total_seconds() * 1000.0, 3),
        "content_type": content_type,
    }

    text_output = response.text
    json_output: Any = None

    if response_mode == "json":
        json_output = response.json()
    elif response_mode == "text":
        json_output = None
    else:
        try:
            json_output = _parse_json_if_available(response)
        except Exception:
            json_output = None

    return {"text": text_output, "json": json_output, "response": response_payload}
