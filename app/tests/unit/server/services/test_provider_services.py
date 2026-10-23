from __future__ import annotations

from typing import Any
import httpx
from server.services.llm.providers import CloudLLMClient, OpenAICompatibleLocalClient
from types import SimpleNamespace
import pytest
import torch
import server.services.workflow.node_handlers.core.embeddings as embeddings_module
from pathlib import Path
from server.services.workflow.provider import huggingface_downloads as huggingface_downloads_module
from server.services.workflow.provider import huggingface_catalog as huggingface_catalog_module
from server.services.workflow.provider import HUGGINGFACE_MODEL_LIST_EXPAND_FIELDS, ProviderApiError, ProviderService
from server.services.workflow.provider.constants import HUGGINGFACE_DOWNLOAD_TIMEOUT_SECONDS, HUGGINGFACE_FALLBACK_LIBRARIES, HUGGINGFACE_FALLBACK_TASKS
import server.services.workflow.provider.service as provider_service_module
from server.services.llm.providers import OllamaClient
from pytest import MonkeyPatch
from server.services.workflow import node_registry
from server.services.workflow.node_handlers.core import routing

# LLM provider services

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

# Hugging Face embedding nodes

###############################################################################
def test_huggingface_embedding_uses_eos_token_when_tokenizer_has_no_pad_token(
    monkeypatch,
) -> None:
    embeddings_module._HF_EMBEDDING_CACHE.clear()  # noqa: SLF001

    ###############################################################################
    class FakeTokenizer:
        pad_token = None
        eos_token = "<eos>"

        # -------------------------------------------------------------------------
        def __call__(self, texts, *, padding, truncation, return_tensors):
            assert texts == ["hello"]
            assert padding is True
            assert truncation is True
            assert return_tensors == "pt"
            assert self.pad_token == self.eos_token
            return {
                "input_ids": torch.tensor([[1, 2]]),
                "attention_mask": torch.tensor([[1, 1]]),
            }

    fake_tokenizer = FakeTokenizer()

    ###############################################################################
    class FakeAutoTokenizer:

        # -------------------------------------------------------------------------
        @staticmethod
        def from_pretrained(model_name: str, token: str | None = None):
            assert model_name == "fake-embedding-model"
            assert token is None
            return fake_tokenizer

    ###############################################################################
    class FakeModel:
        device = None

        # -------------------------------------------------------------------------
        def __call__(self, **kwargs):
            assert "input_ids" in kwargs
            return SimpleNamespace(
                last_hidden_state=torch.tensor([[[1.0, 2.0], [3.0, 4.0]]])
            )

    ###############################################################################
    class FakeAutoModel:

        # -------------------------------------------------------------------------
        @staticmethod
        def from_pretrained(model_name: str, token: str | None = None):
            assert model_name == "fake-embedding-model"
            assert token is None
            return FakeModel()

    monkeypatch.setattr(
        embeddings_module.configuration_service,
        "load_configuration",
        lambda: SimpleNamespace(provider_configurations=[]),
    )
    monkeypatch.setattr(
        embeddings_module,
        "load_huggingface_embedding_modules",
        lambda: (torch, FakeAutoModel, FakeAutoTokenizer),
    )

    vector = embeddings_module._embed_text_with_huggingface(  # noqa: SLF001
        model_name="fake-embedding-model",
        text="hello",
    )

    assert fake_tokenizer.pad_token == fake_tokenizer.eos_token
    assert len(vector) == 2
    assert sum(item * item for item in vector) == pytest.approx(1.0, abs=1e-6)

###############################################################################
def test_huggingface_embedding_can_use_explicit_tokenizer_repo(monkeypatch) -> None:
    embeddings_module._HF_EMBEDDING_CACHE.clear()  # noqa: SLF001
    captured: dict[str, str] = {}

    ###############################################################################
    class FakeTokenizer:
        pad_token = "<pad>"
        eos_token = "<eos>"

        # -------------------------------------------------------------------------
        def __call__(self, texts, *, padding, truncation, return_tensors):
            _ = (texts, padding, truncation, return_tensors)
            return {
                "input_ids": torch.tensor([[1]]),
                "attention_mask": torch.tensor([[1]]),
            }

    ###############################################################################
    class FakeAutoTokenizer:

        # -------------------------------------------------------------------------
        @staticmethod
        def from_pretrained(model_name: str, token: str | None = None):
            _ = token
            captured["tokenizer"] = model_name
            return FakeTokenizer()

    ###############################################################################
    class FakeModel:
        device = None

        # -------------------------------------------------------------------------
        def __call__(self, **kwargs):
            _ = kwargs
            return SimpleNamespace(last_hidden_state=torch.tensor([[[1.0, 0.0]]]))

    ###############################################################################
    class FakeAutoModel:

        # -------------------------------------------------------------------------
        @staticmethod
        def from_pretrained(model_name: str, token: str | None = None):
            _ = token
            captured["model"] = model_name
            return FakeModel()

    monkeypatch.setattr(
        embeddings_module.configuration_service,
        "load_configuration",
        lambda: SimpleNamespace(provider_configurations=[]),
    )
    monkeypatch.setattr(
        embeddings_module,
        "load_huggingface_embedding_modules",
        lambda: (torch, FakeAutoModel, FakeAutoTokenizer),
    )

    vector = embeddings_module._embed_text_with_huggingface(  # noqa: SLF001
        model_name="sentence-transformers/all-MiniLM-L6-v2",
        tokenizer_name="bert-base-uncased",
        text="hello",
    )

    assert captured == {
        "model": "sentence-transformers/all-MiniLM-L6-v2",
        "tokenizer": "bert-base-uncased",
    }
    assert vector == [1.0, 0.0]

# Hugging Face provider behavior

###############################################################################
class _FakeExpandApi:

    # -------------------------------------------------------------------------
    def list_models(
        self,
        *,
        search: str | None = None,
        author: str | None = None,
        pipeline_tag: str | None = None,
        library: str | None = None,
        filter: str | list[str] | None = None,
        sort: str | None = None,
        direction: int | None = None,
        gated: bool | None = None,
        expand: list[str] | None = None,
        full: bool | None = None,
        limit: int | None = None,
        token: str | None = None,
    ) -> None:
        return None

###############################################################################
def test_build_huggingface_list_kwargs_prefers_expand() -> None:
    service = ProviderService()

    kwargs = service._build_huggingface_list_kwargs(  # noqa: SLF001
        _FakeExpandApi(),
        token="hf_test",
        search="qwen",
        task="text-generation",
        library="transformers",
        author="Qwen",
        visibility="public",
        sort="downloads",
        limit=10,
    )

    assert kwargs["expand"] == list(HUGGINGFACE_MODEL_LIST_EXPAND_FIELDS)
    assert "full" not in kwargs

###############################################################################
def test_huggingface_model_iteration_errors_are_translated(monkeypatch) -> None:
    service = ProviderService()

    ###############################################################################
    class _LazyFailingApi:

        # -------------------------------------------------------------------------
        def list_models(self, **kwargs):
            _ = kwargs
            raise AssertionError("generator body should run during iteration")
            yield

    def _raise_connect_error(self, **kwargs):
        _ = (self, kwargs)
        raise httpx.ConnectError("connection refused")
        yield

    monkeypatch.setattr(_LazyFailingApi, "list_models", _raise_connect_error)
    monkeypatch.setattr(
        service,
        "_resolve_huggingface_api",
        lambda session_name: (_LazyFailingApi(), None),
    )
    monkeypatch.setattr(service, "_downloaded_huggingface_repo_ids", lambda: set())

    try:
        service.list_huggingface_models(refresh=True)
    except ProviderApiError as exc:
        assert exc.status_code == 503
        assert "Unable to reach Hugging Face" in str(exc)
    else:
        raise AssertionError(
            "expected lazy Hugging Face iteration failure to translate"
        )

###############################################################################
def test_huggingface_download_uses_explicit_stream_timeout(
    monkeypatch, tmp_path: Path, job_state_factory
) -> None:
    service = ProviderService()
    destination = tmp_path / "huggingface"
    files = [{"path": "model.bin", "size": 4}]
    capture: dict[str, object] = {}

    ###############################################################################
    class _FakeResponse:
        headers = {"Content-Length": "4"}

        # -------------------------------------------------------------------------
        def raise_for_status(self) -> None:
            return None

        # -------------------------------------------------------------------------
        def iter_bytes(self, chunk_size: int = 0):
            _ = chunk_size
            yield b"data"

    ###############################################################################
    class _FakeStreamContext:

        # -------------------------------------------------------------------------
        def __enter__(self) -> _FakeResponse:
            return _FakeResponse()

        # -------------------------------------------------------------------------
        def __exit__(self, exc_type, exc, tb) -> bool:
            _ = (exc_type, exc, tb)
            return False

    def _fake_stream(method: str, url: str, **kwargs):
        _ = (method, url)
        capture["timeout"] = kwargs.get("timeout")
        return _FakeStreamContext()

    monkeypatch.setattr(
        huggingface_downloads_module,
        "hf_hub_url",
        lambda **kwargs: "https://example.invalid/model.bin",
    )
    monkeypatch.setattr(huggingface_downloads_module.httpx, "stream", _fake_stream)
    job_state_factory("job-timeout", "huggingface_download")

    result = service._run_huggingface_download_job(  # noqa: SLF001
        job_id="job-timeout",
        repo_id="owner/model",
        destination_path=str(destination),
        files=files,
        total_bytes=4,
        revision="main",
        token=None,
    )

    assert result["downloaded_bytes"] == 4
    assert isinstance(capture["timeout"], httpx.Timeout)
    timeout = capture["timeout"]
    assert timeout.connect == HUGGINGFACE_DOWNLOAD_TIMEOUT_SECONDS
    assert timeout.read == HUGGINGFACE_DOWNLOAD_TIMEOUT_SECONDS
    assert timeout.write == HUGGINGFACE_DOWNLOAD_TIMEOUT_SECONDS
    assert timeout.pool == HUGGINGFACE_DOWNLOAD_TIMEOUT_SECONDS

###############################################################################
def test_huggingface_filter_tags_logs_and_falls_back(monkeypatch) -> None:
    service = ProviderService()
    captured: list[dict[str, object]] = []

    ###############################################################################
    class _FailingApi:

        # -------------------------------------------------------------------------
        def get_model_tags(self) -> dict[str, object]:
            raise RuntimeError("tag service unavailable")

    def _capture_warning(message: str, *args, **kwargs) -> None:
        captured.append({"message": message, "args": args, "kwargs": kwargs})

    monkeypatch.setattr(huggingface_catalog_module.logger, "warning", _capture_warning)
    tasks, libraries = service._load_huggingface_filter_tags(  # noqa: SLF001
        api=_FailingApi(),
        token="hf_secret",
        refresh=True,
    )

    assert tasks == HUGGINGFACE_FALLBACK_TASKS
    assert libraries == HUGGINGFACE_FALLBACK_LIBRARIES
    assert captured
    assert captured[0]["kwargs"].get("exc_info") is True

# Provider catalog and service behavior

###############################################################################
def test_ollama_chat_uses_provider_abstraction(monkeypatch) -> None:
    service = ProviderService()
    captured: dict[str, object] = {}

    ###############################################################################
    class FakeClient:

        # -------------------------------------------------------------------------
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
            provider_configurations=[
                SimpleNamespace(
                    provider="ollama",
                    base_url="http://127.0.0.1:11434",
                )
            ]
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

###############################################################################
def test_validate_model_request_accepts_openai_gemini_and_claude(monkeypatch) -> None:
    service = ProviderService()
    monkeypatch.setattr(
        service,
        "_get_provider_configuration",
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
        model="claude-sonnet-4-6",
        structured_output=False,
        requires_image=False,
        use_reasoning=False,
    )

###############################################################################
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

###############################################################################
def test_validate_model_request_allows_huggingface_structured_output(
    monkeypatch,
) -> None:
    service = ProviderService()
    monkeypatch.setattr(service, "_downloaded_huggingface_repo_ids", lambda: set())
    monkeypatch.setattr(
        service,
        "_get_provider_configuration",
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

###############################################################################
def test_claude_embeddings_are_rejected() -> None:
    service = ProviderService()

    try:
        service.assert_capabilities("claude", embeddings=True)
    except ValueError as exc:
        assert "does not support embeddings" in str(exc)
    else:
        raise AssertionError("Expected ValueError")

###############################################################################
def test_ollama_client_chat_uses_chat_endpoint_only(monkeypatch) -> None:
    client = OllamaClient(base_url="http://127.0.0.1:11434")
    calls: list[tuple[str, str]] = []

    ###############################################################################
    class FakeResponse:
        status_code = 200

        # -------------------------------------------------------------------------
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

###############################################################################
def test_ollama_embedding_uses_current_endpoint_only(monkeypatch) -> None:
    service = ProviderService()
    calls: list[tuple[str, dict[str, object]]] = []

    ###############################################################################
    class FakeResponse:

        # -------------------------------------------------------------------------
        @staticmethod
        def raise_for_status() -> None:
            return None

        # -------------------------------------------------------------------------
        @staticmethod
        def json() -> dict[str, object]:
            return {"embeddings": [[0.1, 0.2, 0.3]]}

    def fake_post(url: str, **kwargs: object) -> FakeResponse:
        calls.append((url, kwargs))
        return FakeResponse()

    monkeypatch.setattr(provider_service_module.httpx, "post", fake_post)
    monkeypatch.setattr(
        service,
        "_load_configuration",
        lambda session_name="default": SimpleNamespace(
            provider_configurations=[
                SimpleNamespace(
                    provider="ollama",
                    base_url="http://127.0.0.1:11434",
                )
            ]
        ),
    )

    assert service.embed_text(
        provider="ollama", model="nomic-embed-text", text="hello"
    ) == [
        0.1,
        0.2,
        0.3,
    ]
    assert calls == [
        (
            "http://127.0.0.1:11434/api/embed",
            {"json": {"model": "nomic-embed-text", "input": "hello"}, "timeout": 30.0},
        )
    ]

###############################################################################
def test_embedding_rejects_unsupported_provider_without_fallback() -> None:
    service = ProviderService()

    try:
        service.embed_text(provider="gemini", model="test", text="hello")
    except ValueError as exc:
        assert "Unsupported embedding provider: gemini" in str(exc)
    else:
        raise AssertionError("Expected unsupported providers to fail explicitly")

# Tokenizer nodes

###############################################################################
class FakeTokenizer:

    # -------------------------------------------------------------------------
    def __call__(self, text: str, **_: Any) -> dict[str, list[int]]:
        return {
            "input_ids": [len(text), 101],
            "attention_mask": [1, 1],
            "token_type_ids": [0, 0],
        }

###############################################################################
class FakeAutoTokenizer:

    # -------------------------------------------------------------------------
    @staticmethod
    def from_pretrained(_: str, **__: Any) -> FakeTokenizer:
        return FakeTokenizer()

###############################################################################
def test_tokenizer_returns_structured_output_only(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(routing, "AutoTokenizer", FakeAutoTokenizer)

    result = node_registry.execute(
        "TOKENIZER",
        2,
        {
            "tokenizer_name": "fake-tokenizer",
            "output_format": "json",
            "return_attention_mask": True,
            "return_token_type_ids": True,
        },
        {"text": "hello"},
    )

    assert set(result) == {"tokenized"}
    assert result["tokenized"]["records"][0]["token_ids"] == [5, 101]

###############################################################################
def test_tokenizer_returns_serialized_output_only(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(routing, "AutoTokenizer", FakeAutoTokenizer)

    result = node_registry.execute(
        "TOKENIZER",
        2,
        {"tokenizer_name": "fake-tokenizer", "output_format": "string"},
        {"text": "hello"},
    )

    assert set(result) == {"serialized"}
