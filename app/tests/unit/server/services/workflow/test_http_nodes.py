from __future__ import annotations

import pytest

from server.services.workflow.node_handlers.http import (
    _build_json_body,
    _build_query_params,
    _validate_http_url,
)


def test_query_parameters_can_receive_named_variables() -> None:
    assert _build_query_params({"query": {"q": "$summary"}}, {"summary": "abc"}) == {"q": "abc"}


def test_request_body_can_receive_full_json_object() -> None:
    assert _build_json_body({}, {"json": {"summary": "abc"}}) == {"summary": "abc"}


def test_ssrf_guard_rejects_localhost_private_ip_by_default() -> None:
    with pytest.raises(ValueError, match="blocked private"):
        _validate_http_url("http://127.0.0.1:8000")
