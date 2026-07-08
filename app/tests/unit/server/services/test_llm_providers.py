from __future__ import annotations

from typing import Any

import httpx

from server.services.llm.providers import CloudLLMClient, OpenAICompatibleLocalClient

###############################################################################
class _FakeResponse:

    # -------------------------------------------------------------------------
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload
        self.is_error = False
        self.status_code = 200
        self.text = ""

    # -------------------------------------------------------------------------
    def json(self) -> dict[str, Any]:
        return self._payload

###############################################################################
def _mock_openai_post(
    captured: list[dict[str, Any]],
):
    def _post(
        url: str,
        json: dict[str, Any],
        headers: dict[str, str],
        timeout: float,
    ) -> _FakeResponse:
        captured.append(
            {
                "url": url,
                "json": json,
                "headers": headers,
                "timeout": timeout,
            }
        )
        return _FakeResponse({"choices": [{"message": {"content": "ok"}}]})

    return _post

###############################################################################
def _mock_request(captured: list[dict[str, Any]], payload: dict[str, Any]):
    def _request(
        method: str,
        url: str,
        json: dict[str, Any] | None = None,
        timeout: float = 30.0,
        headers: dict[str, str] | None = None,
    ) -> _FakeResponse:
        captured.append(
            {
                "method": method,
                "url": url,
                "json": json,
                "headers": headers or {},
                "timeout": timeout,
            }
        )
        return _FakeResponse(payload)

    return _request

###############################################################################
def test_openai_gpt5_uses_max_completion_tokens(monkeypatch) -> None:
    captured: list[dict[str, Any]] = []
    monkeypatch.setattr(httpx, "post", _mock_openai_post(captured))

    client = CloudLLMClient(
        provider="openai", api_key="sk-test", base_url="https://api.openai.com/v1"
    )
    result = client.chat(
        model="gpt-5-mini",
        messages=[{"role": "user", "content": "hello"}],
        options={"max_output_tokens": 128},
    )

    assert result == "ok"
    payload = captured[0]["json"]
    assert payload["max_completion_tokens"] == 128
    assert "max_tokens" not in payload

###############################################################################
def test_openai_non_gpt5_uses_max_tokens(monkeypatch) -> None:
    captured: list[dict[str, Any]] = []
    monkeypatch.setattr(httpx, "post", _mock_openai_post(captured))

    client = CloudLLMClient(
        provider="openai", api_key="sk-test", base_url="https://api.openai.com/v1"
    )
    result = client.chat(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "hello"}],
        options={"max_output_tokens": 128},
    )

    assert result == "ok"
    payload = captured[0]["json"]
    assert payload["max_tokens"] == 128
    assert "max_completion_tokens" not in payload

###############################################################################
def test_deepseek_chat_uses_openai_compatible_payload(monkeypatch) -> None:
    captured: list[dict[str, Any]] = []
    monkeypatch.setattr(httpx, "post", _mock_openai_post(captured))

    client = CloudLLMClient(provider="deepseek", api_key="ds-test")
    result = client.chat(
        model="deepseek-v4-pro",
        messages=[{"role": "user", "content": "hello"}],
        format="json",
        options={"max_output_tokens": 128, "use_reasoning": True},
    )

    assert result == "ok"
    request = captured[0]
    assert request["url"] == "https://api.deepseek.com/chat/completions"
    assert request["headers"]["Authorization"] == "Bearer ds-test"
    payload = request["json"]
    assert payload["max_tokens"] == 128
    assert payload["response_format"] == {"type": "json_object"}
    assert payload["thinking"] == {"type": "enabled"}
    assert payload["reasoning_effort"] == "high"

###############################################################################
def test_local_openai_compatible_client_lists_models_and_chats(monkeypatch) -> None:
    captured: list[dict[str, Any]] = []
    responses = [
        {"data": [{"id": "local-chat"}, {"id": "local-embed"}]},
        {"choices": [{"message": {"content": "local ok"}}]},
    ]

    def _request(*args: Any, **kwargs: Any) -> _FakeResponse:
        return _mock_request(captured, responses.pop(0))(*args, **kwargs)

    monkeypatch.setattr(httpx, "request", _request)

    client = OpenAICompatibleLocalClient(provider="lmstudio")
    assert client.list_models() == ["local-chat", "local-embed"]
    assert (
        client.chat(
            model="local-chat",
            messages=[{"role": "user", "content": "hello"}],
            format="json",
            options={"max_output_tokens": 64},
        )
        == "local ok"
    )

    assert captured[0]["url"] == "http://localhost:1234/v1/models"
    assert captured[1]["url"] == "http://localhost:1234/v1/chat/completions"
    assert captured[1]["headers"]["Authorization"] == "Bearer lm-studio"
    assert captured[1]["json"]["response_format"] == {"type": "json_object"}
