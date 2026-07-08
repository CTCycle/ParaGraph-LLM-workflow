from __future__ import annotations

from fastapi.testclient import TestClient

from server.domain.provider import ModelMetadata
from server.services.workflow import provider_service
from server.services.workflow.provider import ProviderApiError

###############################################################################
def _raise_provider_error(message: str, status_code: int):
    raise ProviderApiError(message, status_code=status_code)

###############################################################################
def test_provider_errors_are_mapped_to_http_status_codes(
    client: TestClient, monkeypatch
) -> None:
    monkeypatch.setattr(
        provider_service,
        "list_ollama_library_models",
        lambda **kwargs: _raise_provider_error("ollama unavailable", 503),
    )
    ollama_response = client.get("/providers/ollama/library")
    assert ollama_response.status_code == 503
    assert ollama_response.json()["detail"] == "ollama unavailable"

    monkeypatch.setattr(
        provider_service,
        "pull_ollama_model",
        lambda **kwargs: _raise_provider_error("pull denied", 502),
    )
    pull_response = client.post("/providers/ollama/pull", json={"model": "llama3.2"})
    assert pull_response.status_code == 502
    assert pull_response.json()["detail"] == "pull denied"

    monkeypatch.setattr(
        provider_service,
        "list_huggingface_models",
        lambda **kwargs: _raise_provider_error("rate limited", 429),
    )
    hf_models_response = client.get("/providers/huggingface/models")
    assert hf_models_response.status_code == 429
    assert hf_models_response.json()["detail"] == "rate limited"

    monkeypatch.setattr(
        provider_service,
        "download_huggingface_model",
        lambda **kwargs: _raise_provider_error("repo not found", 404),
    )
    hf_download_response = client.post(
        "/providers/huggingface/download", json={"repo_id": "org/model"}
    )
    assert hf_download_response.status_code == 404
    assert hf_download_response.json()["detail"] == "repo not found"

    monkeypatch.setattr(
        provider_service,
        "get_huggingface_download_status",
        lambda **kwargs: _raise_provider_error("job missing", 404),
    )
    hf_status_response = client.get("/providers/huggingface/download/job-404")
    assert hf_status_response.status_code == 404
    assert hf_status_response.json()["detail"] == "job missing"

    monkeypatch.setattr(
        provider_service,
        "cancel_huggingface_download",
        lambda **kwargs: _raise_provider_error("cannot cancel", 409),
    )
    hf_cancel_response = client.delete("/providers/huggingface/download/job-409")
    assert hf_cancel_response.status_code == 409
    assert hf_cancel_response.json()["detail"] == "cannot cancel"

###############################################################################
def test_provider_models_include_embedding_capabilities(
    client: TestClient, monkeypatch
) -> None:
    monkeypatch.setattr(
        provider_service, "_ollama_models", lambda session_name="default": ()
    )
    monkeypatch.setattr(provider_service, "_downloaded_huggingface_models", lambda: ())

    response = client.get("/providers/models")

    assert response.status_code == 200
    payload = response.json()
    models = payload["models"]
    embedding_models = [
        item for item in models if item.get("supports_embeddings") is True
    ]
    assert embedding_models, (
        "Expected at least one embedding-capable model in /providers/models"
    )

    by_provider = {
        provider: []
        for provider in (
            "openai",
            "gemini",
            "ollama",
            "huggingface",
            "lmstudio",
            "llama",
        )
    }
    for item in embedding_models:
        provider = item.get("provider")
        if provider in by_provider:
            by_provider[provider].append(item)

    assert by_provider["openai"], (
        "OpenAI embedding models should be exposed by /providers/models"
    )
    assert by_provider["gemini"], (
        "Gemini embedding models should be exposed by /providers/models"
    )
    assert by_provider["ollama"], (
        "Ollama embedding models should be exposed by /providers/models"
    )
    assert by_provider["huggingface"], (
        "Hugging Face embedding models should be exposed by /providers/models"
    )
    assert by_provider["lmstudio"], (
        "LM Studio embedding models should be exposed by /providers/models"
    )
    assert by_provider["llama"], (
        "llama.cpp embedding models should be exposed by /providers/models"
    )
    assert not [
        item
        for item in models
        if item.get("provider") == "claude" and item.get("supports_embeddings") is True
    ]
    assert not [
        item
        for item in models
        if item.get("provider") == "deepseek"
        and item.get("supports_embeddings") is True
    ]

###############################################################################
def test_provider_catalog_includes_new_providers(client: TestClient) -> None:
    response = client.get("/providers/catalog")

    assert response.status_code == 200
    providers = {item["provider"]: item for item in response.json()["providers"]}
    assert providers["claude"]["supports_chat"] is True
    assert providers["claude"]["supports_embeddings"] is False
    assert providers["deepseek"]["supports_tool_calling"] is True
    assert providers["deepseek"]["supports_embeddings"] is False
    assert providers["lmstudio"]["supports_embeddings"] is True
    assert providers["llama"]["supports_embeddings"] is True

###############################################################################
def test_provider_model_definition_propagates_supports_embeddings_flag() -> None:
    metadata = ModelMetadata(
        provider="openai",
        model="text-embedding-3-small",
        label="Text Embedding 3 Small",
        supports_embeddings=True,
    )

    model_definition = provider_service._to_model_definition(metadata)  # noqa: SLF001

    assert model_definition.supports_embeddings is True
