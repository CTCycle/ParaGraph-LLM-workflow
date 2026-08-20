from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest

from server.contracts.node_handler_http import HttpRequestParameters
from server.services.workflow.http_transport import HttpTransportError, SecureHttpTransport
from server.common import path as common_path

###############################################################################
def PUBLIC_RESOLVER(host: str, port: int) -> list[str]:
    return ["93.184.216.34"]

###############################################################################
def _execute(handler, *, parameters=None, sleep=lambda delay: None, cancelled=lambda: False):
    parsed = HttpRequestParameters.model_validate(
        {"url": "https://example.test/resource", **(parameters or {})}
    )
    return SecureHttpTransport(
        resolver=PUBLIC_RESOLVER,
        transport=httpx.MockTransport(handler),
        sleep=sleep,
        jitter=lambda: 0.0,
        cancelled=cancelled,
    ).execute(parsed, {})

###############################################################################
@pytest.mark.parametrize("method", ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"])
def test_all_supported_methods_use_shared_transport(method: str) -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.method)
        return httpx.Response(200, json={"method": request.method})

    parameters = {"method": method}
    if method in {"POST", "PATCH"}:
        parameters["idempotency_key"] = "stable"
    assert _execute(handler, parameters=parameters)["json"] == {"method": method}
    assert seen == [method]

###############################################################################
@pytest.mark.parametrize(
    ("body_mode", "parameters", "expected"),
    [
        ("json", {"json_body": {"a": 1}}, b'{"a":1}'),
        ("text", {"text_body": "hello"}, b"hello"),
        ("form", {"form_body": {"a": "1"}}, b"a=1"),
        ("binary", {"text_body": "bytes"}, b"bytes"),
    ],
)
def test_request_body_modes(body_mode, parameters, expected: bytes) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.content == expected
        return httpx.Response(204)

    _execute(
        handler,
        parameters={
            "method": "POST",
            "idempotency_key": "stable",
            "body_mode": body_mode,
            "accepted_statuses": [204],
            **parameters,
        },
    )

###############################################################################
def test_binary_invalid_json_and_size_limit() -> None:
    result = _execute(
        lambda request: httpx.Response(200, content=b"\x00\x01"),
        parameters={"response_mode": "binary"},
    )
    assert result["binary_base64"] == "AAE="
    with pytest.raises(HttpTransportError, match="valid JSON") as invalid:
        _execute(
            lambda request: httpx.Response(200, text="not-json"),
            parameters={"response_mode": "json"},
        )
    assert invalid.value.code == "invalid_json"
    with pytest.raises(HttpTransportError) as too_large:
        _execute(
            lambda request: httpx.Response(200, content=b"12345"),
            parameters={"max_response_bytes": 4},
        )
    assert too_large.value.code == "response_too_large"

###############################################################################
def test_file_response_commits_only_an_accepted_response(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(common_path, "ARTIFACT_ROOT", tmp_path)
    destination = tmp_path / "response.bin"
    destination.write_bytes(b"last-good")
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(503, content=b"failed-response")
        return httpx.Response(200, content=b"accepted-response")

    result = _execute(
        handler,
        parameters={
            "response_mode": "file",
            "download_path": "response.bin",
            "max_attempts": 2,
        },
        sleep=lambda delay: None,
    )

    assert result["download_path"] == str(destination)
    assert destination.read_bytes() == b"accepted-response"
    assert not list(tmp_path.glob("*.partial-*"))

###############################################################################
def test_retry_after_and_idempotency_key_retention() -> None:
    calls: list[str] = []
    delays: list[float] = []
    retry_date = (datetime.now(UTC) + timedelta(seconds=1)).strftime(
        "%a, %d %b %Y %H:%M:%S GMT"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.headers["Idempotency-Key"])
        if len(calls) == 1:
            return httpx.Response(429, headers={"Retry-After": "1"})
        if len(calls) == 2:
            return httpx.Response(429, headers={"Retry-After": retry_date})
        return httpx.Response(200, json={"ok": True})

    result = _execute(
        handler,
        parameters={
            "method": "POST",
            "idempotency_key": "one-key",
            "max_attempts": 3,
            "max_retry_delay": 2,
        },
        sleep=delays.append,
    )
    assert result["json"] == {"ok": True}
    assert calls == ["one-key", "one-key", "one-key"]
    assert delays[0] == 1 and 0 <= delays[1] <= 2

###############################################################################
def test_unsafe_retry_requires_explicit_contract() -> None:
    with pytest.raises(ValueError, match="unsafe HTTP retries"):
        HttpRequestParameters(
            url="https://example.test", method="POST", max_attempts=2
        )

###############################################################################
def test_redirect_revalidation_and_loop_limit() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(302, headers={"Location": "https://other.test/final"})

    with pytest.raises(HttpTransportError) as limited:
        _execute(handler, parameters={"max_redirects": 1})
    assert limited.value.code == "redirect_limit"
    assert calls == 2

###############################################################################
@pytest.mark.parametrize(
    "address",
    ["127.0.0.1", "10.0.0.1", "169.254.169.254", "::1", "::ffff:127.0.0.1"],
)
def test_ssrf_blocks_private_metadata_and_mapped_addresses(address: str) -> None:
    transport = SecureHttpTransport(resolver=lambda host, port: [address])
    with pytest.raises(HttpTransportError) as blocked:
        transport.execute(HttpRequestParameters(url="http://target.test"), {})
    assert blocked.value.code == "ssrf_blocked"

###############################################################################
def test_credential_url_dns_rebinding_and_cancellation() -> None:
    with pytest.raises(HttpTransportError) as credentials:
        SecureHttpTransport(resolver=PUBLIC_RESOLVER).execute(
            HttpRequestParameters(url="https://user:pass@example.test"), {}
        )
    assert credentials.value.code == "credential_url"
    with pytest.raises(HttpTransportError) as rebinding:
        SecureHttpTransport(
            resolver=lambda host, port: ["93.184.216.34", "127.0.0.1"]
        ).execute(HttpRequestParameters(url="https://example.test"), {})
    assert rebinding.value.code == "ssrf_blocked"
    with pytest.raises(HttpTransportError) as cancelled:
        _execute(lambda request: httpx.Response(200), cancelled=lambda: True)
    assert cancelled.value.code == "cancelled"
