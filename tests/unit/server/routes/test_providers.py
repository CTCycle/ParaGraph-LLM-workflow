from __future__ import annotations

from fastapi.testclient import TestClient

from ParaGraph.server.services.workflow import provider_service
from ParaGraph.server.services.workflow.provider import ProviderApiError



def _raise_provider_error(message: str, status_code: int):
    raise ProviderApiError(message, status_code=status_code)


def test_provider_errors_are_mapped_to_http_status_codes(client: TestClient, monkeypatch) -> None:
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
    hf_download_response = client.post("/providers/huggingface/download", json={"repo_id": "org/model"})
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