from __future__ import annotations

from types import SimpleNamespace

import server.services.workflow.provider.service as provider_service_module
from server.services.llm.providers import OllamaClient
from server.services.workflow.provider import ProviderService


def test_ollama_chat_uses_provider_abstraction(monkeypatch) -> None:
    service = ProviderService()
    captured: dict[str, object] = {}

    class FakeClient:
        def chat(self, *, model, messages, format=None, options=None):  # noqa: A002
            captured["model"] = model
            captured["messages"] = messages
            captured["format"] = format
            captured["options"] = options
            return "ok"

    def fake_select_llm_provider(provider: str, **kwargs):
        captured["provider"] = provider
        captured["kwargs"] = kwargs
        return FakeClient()

    monkeypatch.setattr(
        provider_service_module, "select_llm_provider", fake_select_llm_provider
    )
    monkeypatch.setattr(
        service,
        "_load_configuration",
        lambda session_name="default": SimpleNamespace(
            ollama=SimpleNamespace(base_url="http://127.0.0.1:11434")
        ),
    )

    response = service.chat(
        provider="ollama",
        model="llama3.2",
        messages=[{"role": "user", "content": "hello"}],
        options={"max_output_tokens": 32},
    )

    assert response == "ok"
    assert captured["provider"] == "ollama"
    assert captured["kwargs"] == {"base_url": "http://127.0.0.1:11434"}
    assert captured["model"] == "llama3.2"


def test_validate_model_request_accepts_openai_gemini_and_claude(monkeypatch) -> None:
    service = ProviderService()
    monkeypatch.setattr(
        service,
        "_get_access_key",
        lambda provider, session_name="default": SimpleNamespace(
            api_key=f"{provider}-key", base_url=None
        ),
    )

    service.validate_model_request(
        provider="openai",
        model="gpt-5.4",
        structured_output=False,
        requires_image=False,
        use_reasoning=False,
    )
    service.validate_model_request(
        provider="gemini",
        model="gemini-2.5-pro",
        structured_output=False,
        requires_image=False,
        use_reasoning=False,
    )
    service.validate_model_request(
        provider="claude",
        model="claude-sonnet-4-20250514",
        structured_output=False,
        requires_image=False,
        use_reasoning=False,
    )


def test_validate_model_request_rejects_huggingface_image_input() -> None:
    service = ProviderService()

    try:
        service.validate_model_request(
            provider="huggingface",
            model="meta-llama/Llama-3.2-3B-Instruct",
            structured_output=False,
            requires_image=True,
            use_reasoning=False,
        )
    except ValueError as exc:
        assert "does not support image input" in str(exc)
    else:
        raise AssertionError("Expected ValueError")


def test_validate_model_request_allows_huggingface_structured_output(
    monkeypatch,
) -> None:
    service = ProviderService()
    monkeypatch.setattr(service, "_downloaded_huggingface_repo_ids", lambda: set())
    monkeypatch.setattr(
        service,
        "_get_access_key",
        lambda provider, session_name="default": SimpleNamespace(
            api_key="hf-key", base_url=None
        ),
    )

    service.validate_model_request(
        provider="huggingface",
        model="meta-llama/Llama-3.2-3B-Instruct",
        structured_output=True,
        requires_image=False,
        use_reasoning=False,
    )


def test_claude_embeddings_are_rejected() -> None:
    service = ProviderService()

    try:
        service.assert_capabilities("claude", embeddings=True)
    except ValueError as exc:
        assert "does not support embeddings" in str(exc)
    else:
        raise AssertionError("Expected ValueError")


def test_ollama_client_chat_uses_chat_endpoint_only(monkeypatch) -> None:
    client = OllamaClient(base_url="http://127.0.0.1:11434")
    calls: list[tuple[str, str]] = []

    class FakeResponse:
        status_code = 200

        @staticmethod
        def json() -> dict[str, object]:
            return {"message": {"content": "ok"}}

    def fake_request(method: str, path: str, **kwargs):
        _ = kwargs
        calls.append((method, path))
        return FakeResponse()

    monkeypatch.setattr(client, "_request", fake_request)

    result = client.chat(model="llama3.2", messages=[{"role": "user", "content": "hi"}])

    assert result == "ok"
    assert calls == [("POST", "/api/chat")]

