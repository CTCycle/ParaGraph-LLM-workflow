from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from ParaGraph.server.api import nodes as nodes_api


def test_check_vector_store_connection_calls_adapter_validate(client: TestClient, monkeypatch) -> None:
    calls: dict[str, object] = {}

    class FakeAdapter:
        def validate_connection(self, **kwargs):
            calls.update(kwargs)

    monkeypatch.setattr(nodes_api, "get_vector_store_adapter", lambda provider: FakeAdapter())

    response = client.post(
        "/nodes/check-vector-store-connection",
        json={
            "node_type": "VECTOR_STORE",
            "node_version": 1,
            "parameters": {
                "provider": "qdrant",
                "index_name": "docs",
                "storage_path": "",
                "endpoint_url": "https://qdrant.local",
                "api_key": "secret",
                "collection_name": "docs",
                "database_name": "",
                "namespace": "",
                "provider_config": {},
                "write_mode": "overwrite",
                "distance_metric": "cosine",
            },
        },
    )

    assert response.status_code == 200
    assert response.json() == {"ok": True, "message": "Vector store connection successful."}
    assert calls["index_name"] == "docs"
    assert calls["endpoint_url"] == "https://qdrant.local"
    assert calls["api_key"] == "secret"


@pytest.mark.parametrize("provider", ["lancedb", "chroma", "faiss"])
def test_check_vector_store_connection_local_providers_require_storage_path(
    client: TestClient,
    monkeypatch,
    provider: str,
) -> None:
    calls: dict[str, object] = {}

    class FakeAdapter:
        def validate_connection(self, **kwargs):
            calls.update(kwargs)

    monkeypatch.setattr(nodes_api, "get_vector_store_adapter", lambda backend: FakeAdapter())
    response = client.post(
        "/nodes/check-vector-store-connection",
        json={
            "node_type": "VECTOR_STORE",
            "node_version": 1,
            "parameters": {
                "provider": provider,
                "index_name": "docs",
                "storage_path": "C:/tmp/vectorstore",
                "endpoint_url": "",
                "api_key": "",
                "collection_name": "",
                "database_name": "",
                "namespace": "",
                "provider_config": {},
                "write_mode": "overwrite",
                "distance_metric": "cosine",
            },
        },
    )

    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert calls["storage_directory"] == "C:/tmp/vectorstore"


@pytest.mark.parametrize("provider", ["qdrant", "pinecone", "weaviate", "milvus"])
def test_check_vector_store_connection_remote_providers_require_endpoint(
    client: TestClient,
    monkeypatch,
    provider: str,
) -> None:
    calls: dict[str, object] = {}

    class FakeAdapter:
        def validate_connection(self, **kwargs):
            calls.update(kwargs)

    monkeypatch.setattr(nodes_api, "get_vector_store_adapter", lambda backend: FakeAdapter())
    response = client.post(
        "/nodes/check-vector-store-connection",
        json={
            "node_type": "VECTOR_STORE",
            "node_version": 1,
            "parameters": {
                "provider": provider,
                "index_name": "docs",
                "storage_path": "",
                "endpoint_url": "https://vector.example",
                "api_key": "token",
                "collection_name": "",
                "database_name": "",
                "namespace": "",
                "provider_config": {},
                "write_mode": "overwrite",
                "distance_metric": "cosine",
            },
        },
    )

    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert calls["endpoint_url"] == "https://vector.example"
