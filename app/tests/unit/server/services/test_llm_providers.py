from __future__ import annotations

from typing import Any

import httpx

from server.services.llm.providers import CloudLLMClient


class _FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload
        self.is_error = False
        self.status_code = 200
        self.text = ""

    def json(self) -> dict[str, Any]:
        return self._payload


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
