from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Integer, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from server.services.workflow.nodes import connectivity as node_connectivity_module

###############################################################################
class SchemaRouteBase(DeclarativeBase):
    pass

###############################################################################
class SchemaRouteItem(SchemaRouteBase):
    __tablename__ = "schema_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)

###############################################################################
def test_database_schema_endpoint_returns_sqlite_schema(
    client: TestClient, tmp_path
) -> None:
    database_path = tmp_path / "schema.sqlite"
    engine = create_engine(f"sqlite:///{database_path}")
    SchemaRouteBase.metadata.create_all(engine)
    engine.dispose()

    response = client.post(
        "/nodes/database-schema",
        json={
            "node_type": "SQL_FILE_DATABASE",
            "node_version": 1,
            "parameters": {"db_path": str(database_path), "db_connect_timeout": 30},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["tables"][0]["name"] == "schema_items"
    assert payload["tables"][0]["columns"][0]["name"] == "id"

###############################################################################
def test_check_vector_store_connection_calls_adapter_validate(
    client: TestClient, monkeypatch
) -> None:
    calls: dict[str, object] = {}

    ###############################################################################
    class FakeAdapter:

        # -------------------------------------------------------------------------
        def validate_connection(self, **kwargs):
            calls.update(kwargs)

    monkeypatch.setattr(
        node_connectivity_module,
        "get_vector_store_adapter",
        lambda provider: FakeAdapter(),
    )

    response = client.post(
        "/nodes/check-vector-store-connection",
        json={
            "node_type": "VECTOR_STORE",
            "node_version": 2,
            "parameters": {
                "provider": "qdrant",
                "index_name": "docs",
                "storage_path": "",
                "endpoint_url": "https://qdrant.local",
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
    assert response.json() == {
        "ok": True,
        "message": "Vector store connection successful.",
    }
    assert calls["index_name"] == "docs"
    assert calls["endpoint_url"] == "https://qdrant.local"
    assert calls["api_key"] == ""

###############################################################################
@pytest.mark.parametrize("provider", ["lancedb", "chroma", "faiss"])
def test_check_vector_store_connection_local_providers_require_storage_path(
    client: TestClient,
    monkeypatch,
    provider: str,
) -> None:
    calls: dict[str, object] = {}

    ###############################################################################
    class FakeAdapter:

        # -------------------------------------------------------------------------
        def validate_connection(self, **kwargs):
            calls.update(kwargs)

    monkeypatch.setattr(
        node_connectivity_module,
        "get_vector_store_adapter",
        lambda backend: FakeAdapter(),
    )
    response = client.post(
        "/nodes/check-vector-store-connection",
        json={
            "node_type": "VECTOR_STORE",
            "node_version": 2,
            "parameters": {
                "provider": provider,
                "index_name": "docs",
                "storage_path": "C:/tmp/vectorstore",
                "endpoint_url": "",
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

###############################################################################
@pytest.mark.parametrize("provider", ["qdrant", "pinecone", "weaviate", "milvus"])
def test_check_vector_store_connection_remote_providers_require_endpoint(
    client: TestClient,
    monkeypatch,
    provider: str,
) -> None:
    calls: dict[str, object] = {}

    ###############################################################################
    class FakeAdapter:

        # -------------------------------------------------------------------------
        def validate_connection(self, **kwargs):
            calls.update(kwargs)

    monkeypatch.setattr(
        node_connectivity_module,
        "get_vector_store_adapter",
        lambda backend: FakeAdapter(),
    )
    response = client.post(
        "/nodes/check-vector-store-connection",
        json={
            "node_type": "VECTOR_STORE",
            "node_version": 2,
            "parameters": {
                "provider": provider,
                "index_name": "docs",
                "storage_path": "",
                "endpoint_url": "https://vector.example",
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
