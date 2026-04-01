from __future__ import annotations

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
