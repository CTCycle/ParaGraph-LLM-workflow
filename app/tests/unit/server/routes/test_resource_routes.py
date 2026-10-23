from __future__ import annotations

from httpx import Response
from fastapi.testclient import TestClient
from server.contracts.configuration import AppConfigurationPayload, ConfigurationProfileListResponse, ConfigurationProfileSummary, OllamaStatusResponse, ProviderConfiguration, ProviderStatusResponse
from server.configurations.settings import SQLiteSettings
from server.repositories.configuration import ConfigurationRepository
from server.repositories.database.migration import run_database_migrations
from server.repositories.database.sqlite import SQLiteRepository
from server.services.configuration import configuration_service
from pathlib import Path
from fastapi import HTTPException
from sqlalchemy import create_engine, text
import server.api.database as database_api
from server.common import path as common_path
from server.contracts.database import DatabaseConfigurationPayload
from server.repositories.database.runtime import DatabaseRuntime
import pytest
from sqlalchemy import Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from server.services.workflow.nodes import connectivity as node_connectivity_module
import shutil
from server.contracts.node_catalog import HuggingFaceModelCatalogResponse, HuggingFaceModelDefinition, HuggingFaceModelDownloadCancelResponse, HuggingFaceModelDownloadResponse, HuggingFaceModelDownloadStatusResponse, OllamaLibraryCatalogResponse, OllamaLibraryModelDefinition, OllamaModelPullResponse, ProviderModelCatalogResponse, ProviderModelDefinition
from server.repositories.workflow import node_manifest_repository
from server.services.workflow.nodes import registry as node_registry_module
from server.services.workflow import provider_service
from server.services.workflow.provider.models import ModelMetadata
from server.services.workflow.provider import ProviderApiError

# Configuration routes

###############################################################################
def _payload(session_name: str = "default") -> AppConfigurationPayload:
    return AppConfigurationPayload(
        session_name=session_name,
        provider_configurations=[
            ProviderConfiguration(
                provider="openai", api_key="sk-test", base_url=None, metadata={}
            ),
            ProviderConfiguration(
                provider="huggingface", api_key="hf-test", base_url=None, metadata={}
            ),
            ProviderConfiguration(
                provider="ollama",
                base_url="http://127.0.0.1:11434",
                metadata={
                    "chat_model": "llama3.2",
                    "embedding_model": "nomic-embed-text",
                },
            ),
        ],
    )

###############################################################################
def test_configurations_load_save_profile_and_ping_flows(
    client: TestClient, monkeypatch
) -> None:
    loaded_payload = _payload("session-a")
    saved_payload = _payload("session-a")
    profile_payload = _payload("session-a")

    monkeypatch.setattr(
        configuration_service,
        "load_configuration",
        lambda session_name="default": loaded_payload,
    )
    monkeypatch.setattr(
        configuration_service, "save_configuration", lambda payload: saved_payload
    )
    monkeypatch.setattr(
        configuration_service,
        "list_configuration_profiles",
        lambda session_name="default": ConfigurationProfileListResponse(
            session_name=session_name,
            profiles=[
                ConfigurationProfileSummary(
                    profile_name="workbench",
                    created_at="2026-03-24T08:00:00+00:00",
                    updated_at="2026-03-24T09:00:00+00:00",
                )
            ],
        ),
    )
    monkeypatch.setattr(
        configuration_service,
        "load_configuration_profile",
        lambda *, session_name, profile_name: profile_payload,
    )
    monkeypatch.setattr(
        configuration_service,
        "save_configuration_profile",
        lambda *, profile_name, payload: saved_payload,
    )
    monkeypatch.setattr(
        configuration_service,
        "ping_ollama",
        lambda *, base_url, session_name="default": OllamaStatusResponse(
            ok=True,
            message="Ollama reachable (2 models discovered).",
            base_url=base_url or "http://127.0.0.1:11434",
            model_count=2,
        ),
    )
    monkeypatch.setattr(
        configuration_service,
        "ping_provider",
        lambda *, provider, base_url, api_key, session_name="default": (
            ProviderStatusResponse(
                ok=True,
                provider=provider,
                message=f"{provider} reachable (1 model discovered).",
                base_url=base_url or "http://localhost:1234/v1",
                model_count=1,
            )
        ),
    )

    load_response = client.get("/configurations", params={"session_name": "session-a"})
    assert load_response.status_code == 200
    assert load_response.json()["session_name"] == "session-a"

    save_response = client.put(
        "/configurations", json=loaded_payload.model_dump(mode="json")
    )
    assert save_response.status_code == 200
    assert save_response.json()["session_name"] == "session-a"

    list_response = client.get(
        "/configurations/profiles", params={"session_name": "session-a"}
    )
    assert list_response.status_code == 200
    assert list_response.json()["profiles"][0]["profile_name"] == "workbench"

    load_profile_response = client.get(
        "/configurations/profiles/workbench", params={"session_name": "session-a"}
    )
    assert load_profile_response.status_code == 200
    assert load_profile_response.json()["session_name"] == "session-a"

    save_profile_response = client.put(
        "/configurations/profiles/workbench",
        json=loaded_payload.model_dump(mode="json"),
    )
    assert save_profile_response.status_code == 200
    assert save_profile_response.json()["session_name"] == "session-a"

    ping_response = client.post(
        "/configurations/ollama/ping",
        params={"session_name": "session-a"},
        json={"base_url": "http://127.0.0.1:11434"},
    )
    assert ping_response.status_code == 200
    assert ping_response.json()["ok"] is True

    provider_ping_response = client.post(
        "/configurations/providers/ping",
        params={"session_name": "session-a"},
        json={"provider": "lmstudio", "base_url": "http://localhost:1234/v1"},
    )
    assert provider_ping_response.status_code == 200
    assert provider_ping_response.json()["provider"] == "lmstudio"

###############################################################################
def test_configuration_routes_persist_and_redact_secrets(
    client: TestClient, monkeypatch, tmp_path
) -> None:
    database_path = tmp_path / "configuration-validation.db"
    run_database_migrations(database_path)
    sqlite_repository = SQLiteRepository(
        SQLiteSettings(insert_batch_size=1000), db_path=str(database_path)
    )
    repository = ConfigurationRepository(database_repository=sqlite_repository)
    monkeypatch.setattr(configuration_service, "_repository", repository)

    session_name = "pg-t1-secret-validation"
    profile_name = "validation-profile"
    sentinel = "pg-t1-sentinel-secret"
    profile_sentinel = "pg-t1-profile-secret"
    payload = {
        "session_name": session_name,
        "provider_configurations": [
            {
                "provider": "openai",
                "api_key": sentinel,
                "base_url": None,
                "metadata": {},
            }
        ],
    }

    def assert_redacted(response: Response) -> None:
        assert response.status_code == 200
        assert sentinel not in response.text
        provider = response.json()["provider_configurations"][0]
        assert provider["api_key"] is None
        assert provider["has_api_key"] is True

    try:
        saved_configuration = client.put("/configurations", json=payload)
        assert_redacted(saved_configuration)
        assert repository.load_configuration(session_name)[
            "provider_configurations"
        ][0]["api_key"] == sentinel

        public_configuration = saved_configuration.json()
        updated_configuration = client.put(
            "/configurations", json=public_configuration
        )
        assert_redacted(updated_configuration)
        assert repository.load_configuration(session_name)[
            "provider_configurations"
        ][0]["api_key"] == sentinel

        profile_payload = {
            "session_name": session_name,
            "provider_configurations": [
                {
                    "provider": "openai",
                    "api_key": profile_sentinel,
                    "base_url": "https://profile.example/v1",
                    "metadata": {},
                }
            ],
        }
        saved_profile = client.put(
            f"/configurations/profiles/{profile_name}", json=profile_payload
        )
        assert saved_profile.status_code == 200
        assert profile_sentinel not in saved_profile.text
        assert saved_profile.json()["provider_configurations"][0]["api_key"] is None
        assert repository.load_configuration(session_name)[
            "provider_configurations"
        ][0]["api_key"] == sentinel

        activated_profile = client.post(
            f"/configurations/profiles/{profile_name}/activate",
            params={"session_name": session_name},
        )
        assert activated_profile.status_code == 200
        assert profile_sentinel not in activated_profile.text
        assert activated_profile.json()["provider_configurations"][0]["api_key"] is None
        active_provider = repository.load_configuration(session_name)[
            "provider_configurations"
        ][0]
        assert active_provider["api_key"] == profile_sentinel
        assert active_provider["base_url"] == "https://profile.example/v1"

        loaded_profile = client.get(
            f"/configurations/profiles/{profile_name}",
            params={"session_name": session_name},
        )
        assert_redacted(loaded_profile)
        assert repository.load_configuration_profile(
            session_name=session_name, profile_name=profile_name
        )["provider_configurations"][0]["api_key"] == profile_sentinel

        updated_profile = client.put(
            f"/configurations/profiles/{profile_name}", json=loaded_profile.json()
        )
        assert_redacted(updated_profile)
        assert repository.load_configuration_profile(
            session_name=session_name, profile_name=profile_name
        )["provider_configurations"][0]["api_key"] == profile_sentinel

        profile_list = client.get(
            "/configurations/profiles", params={"session_name": session_name}
        )
        assert profile_list.status_code == 200
        assert sentinel not in profile_list.text
        assert profile_list.json()["profiles"][0]["profile_name"] == profile_name
    finally:
        sqlite_repository.engine.dispose()

###############################################################################
def test_configuration_profile_errors_map_to_http(
    client: TestClient, monkeypatch
) -> None:
    monkeypatch.setattr(
        configuration_service,
        "load_configuration_profile",
        lambda *, session_name, profile_name: (_ for _ in ()).throw(
            KeyError("Profile missing")
        ),
    )
    monkeypatch.setattr(
        configuration_service,
        "save_configuration_profile",
        lambda *, profile_name, payload: (_ for _ in ()).throw(
            ValueError("Invalid profile name")
        ),
    )

    load_response = client.get(
        "/configurations/profiles/missing", params={"session_name": "default"}
    )
    assert load_response.status_code == 404
    assert load_response.json()["detail"] == "Profile missing"

    activate_response = client.post(
        "/configurations/profiles/missing/activate",
        params={"session_name": "default"},
    )
    assert activate_response.status_code == 404
    assert activate_response.json()["detail"] == "Profile missing"

    save_response = client.put(
        "/configurations/profiles/missing", json=_payload().model_dump(mode="json")
    )
    assert save_response.status_code == 400
    assert save_response.json()["detail"] == "Invalid profile name"

# Database routes

###############################################################################
def _configure_runtime(runtime: DatabaseRuntime, monkeypatch, root: Path) -> None:
    monkeypatch.setattr(common_path, "RESOURCES_ROOT", root)
    monkeypatch.setattr(database_api, "database_runtime", runtime)

###############################################################################
def test_database_endpoints_test_apply_and_rollback(
    tmp_path: Path, monkeypatch
) -> None:
    runtime = DatabaseRuntime(persist_configuration=False, publish_settings=False)
    _configure_runtime(runtime, monkeypatch, tmp_path)
    payload = {
        "backend": "sqlite",
        "database_path": "first.db",
        "insert_batch_size": 12,
    }
    typed_payload = DatabaseConfigurationPayload.model_validate(payload)

    status = database_api.get_database_configuration()
    assert status.connected is False

    tested = database_api.test_database_configuration(typed_payload)
    assert tested.ok is True

    applied = database_api.put_database_configuration(typed_payload)
    assert applied.connected is True
    active_path = runtime.status()["database_path"]

    incompatible = tmp_path / "incompatible.db"
    engine = create_engine(f"sqlite:///{incompatible.as_posix()}")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE unrelated (value TEXT)"))
    engine.dispose()
    with pytest.raises(HTTPException) as failure:
        database_api.put_database_configuration(
            DatabaseConfigurationPayload(
                backend="sqlite",
                database_path=str(incompatible),
                insert_batch_size=12,
            )
        )
    assert failure.value.status_code == 503
    assert runtime.status()["database_path"] == active_path
    runtime.reset_for_tests()

###############################################################################
def test_database_apply_rejects_an_active_workflow(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from server.services.jobs import job_manager

    runtime = DatabaseRuntime(persist_configuration=False, publish_settings=False)
    _configure_runtime(runtime, monkeypatch, tmp_path)
    monkeypatch.setattr(job_manager, "is_job_running", lambda job_type=None: job_type == "workflow")

    with pytest.raises(HTTPException) as failure:
        database_api.put_database_configuration(
            DatabaseConfigurationPayload(
                backend="sqlite", database_path="blocked.db", insert_batch_size=9
            )
        )

    assert failure.value.status_code == 409
    assert "active workflow" in failure.value.detail
    assert runtime.status()["connected"] is False
    runtime.reset_for_tests()

# Node routes

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
def test_check_vector_store_connection_resolves_saved_credential(
    client: TestClient, monkeypatch
) -> None:
    calls: dict[str, object] = {}

    ###############################################################################
    class FakeAdapter:

        # -------------------------------------------------------------------------
        def validate_connection(self, **kwargs):
            calls.update(kwargs)

    resolved: dict[str, object] = {}

    def resolve_configuration(
        *, profile_name: str, provider: str, session_name: str | None = None
    ) -> ProviderConfiguration:
        resolved.update(
            profile_name=profile_name,
            provider=provider,
            session_name=session_name,
        )
        return ProviderConfiguration(
            provider=provider,
            api_key="pinecone-secret",
            base_url="https://configured-vector.example",
        )

    monkeypatch.setattr(
        node_connectivity_module,
        "get_vector_store_adapter",
        lambda provider: FakeAdapter(),
    )
    monkeypatch.setattr(
        node_connectivity_module.configuration_service,
        "resolve_provider_configuration",
        resolve_configuration,
    )

    response = client.post(
        "/nodes/check-vector-store-connection",
        json={
            "node_type": "VECTOR_STORE",
            "node_version": 2,
            "parameters": {
                "provider": "pinecone",
                "index_name": "docs",
                "storage_path": "",
                "endpoint_url": "",
                "credential_profile": "production",
                "credential_session_name": "tenant-a",
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
    assert response.json() == {
        "ok": True,
        "message": "Vector store connection successful.",
    }
    assert calls["api_key"] == "pinecone-secret"
    assert calls["endpoint_url"] == "https://configured-vector.example"
    assert resolved["session_name"] == "tenant-a"

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

# Platform routes

###############################################################################
def build_prompt_to_output_definition() -> dict[str, object]:
    return {
        "schema_version": 2,
        "nodes": [
            {
                "node_id": "prompt_1",
                "node_type": "PROMPT",
                "node_version": 1,
                "parameters": {"prompt_text": "Hello graph"},
            },
            {
                "node_id": "output_1",
                "node_type": "TEXT_OUTPUT",
                "node_version": 1,
                "parameters": {},
            },
        ],
        "connections": [
            {
                "from_node": "prompt_1",
                "from_output": "text",
                "to_node": "output_1",
                "to_input": "text",
            },
        ],
        "metadata": {},
    }

###############################################################################
def test_nodes_catalog_exposes_registry(client: TestClient) -> None:
    response = client.get("/nodes/catalog")

    assert response.status_code == 200
    payload = response.json()

    ids = {node["id"] for node in payload["nodes"]}
    assert ids >= {
        "BY_DELIMITER_CHUNKS",
        "BY_STRUCTURE_CHUNKS",
        "FIXED_SIZE_CHUNKS",
        "HTTP_REQUEST",
        "JSON_OUTPUT",
        "LLM_CHAT",
        "LLM_STRUCTURED",
        "LOAD_DOCUMENTS",
        "LOAD_TEXT",
        "MERGE_SMALL_CHUNKS",
        "MODEL_PROVIDER",
        "VECTOR_STORE",
        "RERANK_RESULTS",
        "SIMILARITY_SEARCH",
        "TEXT_EMBEDDING",
        "PROMPT",
        "PROMPT_TEMPLATE",
        "RECURSIVE_SPLIT_CHUNKS",
        "REGEX_SPLIT_CHUNKS",
        "SAVE_AS_FILE",
        "SAVE_AS_FOLDER",
        "SENTENCE_WINDOW_CHUNKS",
        "SQL_DATABASE",
        "SQL_FILE_DATABASE",
        "TEXT_OUTPUT",
    }
    assert "USER_PROMPT" not in ids
    assert "SYSTEM_PROMPT" not in ids
    assert "EMBEDDING_MODEL" not in ids
    assert "LANCE_DB" not in ids
    assert "LLM_GENERATE" not in ids
    categories = {node["category"] for node in payload["nodes"]}
    assert "fragmentation" not in categories
    assert "text_segmentation" in categories
    assert "prompt" in categories
    assert "retrieval" in categories
    capabilities = {
        item["backend"]: item for item in payload["vector_store_capabilities"]
    }
    assert set(capabilities) == {
        "chroma",
        "faiss",
        "lancedb",
        "milvus",
        "pinecone",
        "qdrant",
        "weaviate",
    }
    assert capabilities["pinecone"]["supports_namespaces"] is True
    assert capabilities["pinecone"]["supports_minimum_should_match"] is False
    assert capabilities["weaviate"]["supported_metrics"] == ["cosine"]

###############################################################################
def test_nodes_import_persists_manifest(client: TestClient, tmp_path: Path) -> None:
    node_dir = tmp_path / "nodes"
    node_dir.mkdir(parents=True, exist_ok=True)
    resources_root = common_path.REPOSITORY_ROOT / "data"
    for manifest in (resources_root / "nodes").glob("*.json"):
        (node_dir / manifest.name).write_text(
            manifest.read_text(encoding="utf-8"), encoding="utf-8"
        )
    plugins_src = resources_root / "nodes" / "plugins"
    if plugins_src.exists():
        plugins_target = node_dir / "plugins"
        plugins_target.mkdir(parents=True, exist_ok=True)
        for plugin_file in plugins_src.glob("*.py"):
            (plugins_target / plugin_file.name).write_text(
                plugin_file.read_text(encoding="utf-8"), encoding="utf-8"
            )

    node_manifest_repository.configure_storage_for_tests(node_dir)
    node_registry_module.node_registry.reload()

    response = client.post(
        "/nodes/import",
        json={
            "id": "CUSTOM_ECHO",
            "version": 1,
            "name": "Custom Echo",
            "category": "processing",
            "description": "Echo text through a custom manifest.",
            "inputs": [
                {
                    "name": "text",
                    "data_type": "TEXT",
                    "required": True,
                    "accepts_multiple": False,
                }
            ],
            "outputs": [
                {
                    "name": "text",
                    "data_type": "TEXT",
                    "required": True,
                    "accepts_multiple": False,
                }
            ],
            "parameters": [],
            "ui": {
                "default_width": 280,
                "accent_color": "#ffffff",
                "collapsed_by_default": False,
            },
            "runtime": {
                "executor_key": "prompt",
                "cacheable": True,
                "deterministic": True,
                "side_effecting": False,
            },
        },
    )

    assert response.status_code == 201
    assert response.json()["id"] == "CUSTOM_ECHO"
    assert (node_dir / "custom_echo_v1.json").exists()

###############################################################################
def test_nodes_upload_directory_stages_browser_selected_folder(
    client: TestClient,
) -> None:
    response = client.post(
        "/nodes/uploads/directory",
        files=[
            ("files", ("dataset/readme.txt", b"hello world", "text/plain")),
            ("files", ("dataset/nested/notes.md", b"# Notes", "text/markdown")),
        ],
    )

    assert response.status_code == 200
    payload = response.json()
    staged_root = Path(payload["path"])
    staged_files = [Path(item) for item in payload["files"]]
    try:
        assert payload["file_count"] == 2
        assert len(staged_files) == 2
        assert all(path.exists() for path in staged_files)
        assert (staged_root / "dataset" / "readme.txt").read_text(
            encoding="utf-8"
        ) == "hello world"
        assert (staged_root / "dataset" / "nested" / "notes.md").read_text(
            encoding="utf-8"
        ) == "# Notes"
    finally:
        if staged_root.exists():
            shutil.rmtree(staged_root, ignore_errors=True)

###############################################################################
def test_nodes_upload_directory_staging_root_is_stable_across_working_directory(
    client: TestClient, monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)

    response = client.post(
        "/nodes/uploads/directory",
        files=[
            ("files", ("dataset/readme.txt", b"hello world", "text/plain")),
        ],
    )

    assert response.status_code == 200
    payload = response.json()
    staged_root = Path(payload["path"])
    expected_root = (common_path.ARTIFACT_ROOT / "browser_uploads").resolve()
    try:
        assert staged_root.is_relative_to(expected_root)
        assert (staged_root / "dataset" / "readme.txt").read_text(
            encoding="utf-8"
        ) == "hello world"
    finally:
        if staged_root.exists():
            shutil.rmtree(staged_root, ignore_errors=True)

###############################################################################
def test_nodes_upload_directory_rejects_parent_directory_segments(
    client: TestClient,
) -> None:
    response = client.post(
        "/nodes/uploads/directory",
        files=[("files", ("../escape.txt", b"invalid", "text/plain"))],
    )

    assert response.status_code == 422
    assert "relative paths" in response.json()["detail"].lower()

###############################################################################
def test_nodes_upload_directory_rejects_absolute_paths(client: TestClient) -> None:
    response = client.post(
        "/nodes/uploads/directory",
        files=[("files", ("/etc/passwd", b"invalid", "text/plain"))],
    )

    assert response.status_code == 422
    assert "absolute paths" in response.json()["detail"].lower()

###############################################################################
def test_nodes_database_connection_check_returns_success_for_sqlite(
    client: TestClient, tmp_path: Path
) -> None:

    ###############################################################################
    class TestHealthBase(DeclarativeBase):
        pass

    ###############################################################################
    class TestTable(TestHealthBase):
        __tablename__ = "test_table"
        id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
        value: Mapped[str | None] = mapped_column(String, nullable=True)

    database_path = tmp_path / "health.sqlite"
    engine = create_engine(f"sqlite:///{database_path}")
    TestHealthBase.metadata.create_all(engine)
    engine.dispose()

    response = client.post(
        "/nodes/check-database-connection",
        json={
            "node_type": "SQL_FILE_DATABASE",
            "node_version": 1,
            "parameters": {
                "db_path": str(database_path),
                "db_connect_timeout": 5,
            },
        },
    )

    assert response.status_code == 200
    assert response.json() == {"ok": True, "message": "Database connection successful."}

###############################################################################
def test_nodes_database_connection_check_returns_failure_payload(
    client: TestClient,
) -> None:
    response = client.post(
        "/nodes/check-database-connection",
        json={
            "node_type": "SQL_FILE_DATABASE",
            "node_version": 1,
            "parameters": {
                "db_path": "C:/does/not/exist/missing.sqlite",
                "db_connect_timeout": 5,
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is False
    assert "not found" in payload["message"].lower()

###############################################################################
def test_provider_models_endpoint_returns_catalog(
    client: TestClient, monkeypatch
) -> None:
    monkeypatch.setattr(
        provider_service,
        "list_models",
        lambda session_name="default": ProviderModelCatalogResponse(
            models=[
                ProviderModelDefinition(
                    provider="ollama",
                    model="llama3.2",
                    label="Llama 3.2",
                    supports_image=False,
                    supports_reasoning=False,
                    supports_structured_output=True,
                )
            ]
        ),
    )

    response = client.get("/providers/models")

    assert response.status_code == 200
    assert response.json()["models"][0]["model"] == "llama3.2"

###############################################################################
def test_ollama_library_endpoint_returns_rows(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(
        provider_service,
        "list_ollama_library_models",
        lambda **kwargs: OllamaLibraryCatalogResponse(
            models=[
                OllamaLibraryModelDefinition(
                    model="llama3.2",
                    description="Llama model",
                    homepage="https://ollama.com/library/llama3.2",
                    pulled=True,
                )
            ],
            total_count=1,
            pulled_count=1,
            refreshed_at="2026-03-16T00:00:00+00:00",
            source="https://ollama.com/library",
        ),
    )

    response = client.get("/providers/ollama/library?refresh=true")

    assert response.status_code == 200
    payload = response.json()
    assert payload["models"][0]["model"] == "llama3.2"
    assert payload["models"][0]["pulled"] is True

###############################################################################
def test_ollama_pull_endpoint_returns_success(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(
        provider_service,
        "pull_ollama_model",
        lambda *, model, session_name="default": OllamaModelPullResponse(
            ok=True,
            model=model,
            message=f"Model '{model}' is available in Ollama.",
        ),
    )

    response = client.post("/providers/ollama/pull", json={"model": "llama3.2"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["model"] == "llama3.2"

###############################################################################
def test_huggingface_models_endpoint_returns_rows(
    client: TestClient, monkeypatch
) -> None:
    monkeypatch.setattr(
        provider_service,
        "list_huggingface_models",
        lambda **kwargs: HuggingFaceModelCatalogResponse(
            models=[
                HuggingFaceModelDefinition(
                    repo_id="meta-llama/Llama-3.2-3B-Instruct",
                    author="meta-llama",
                    task="text-generation",
                    library="transformers",
                    likes=10,
                    downloads=100,
                    visibility="public",
                    private=False,
                    gated=False,
                    last_modified="2026-03-16T00:00:00+00:00",
                    url="https://huggingface.co/meta-llama/Llama-3.2-3B-Instruct",
                )
            ],
            page=1,
            page_size=25,
            has_more=True,
            using_token=False,
            warning=None,
        ),
    )

    response = client.get(
        "/providers/huggingface/models?search=llama&sort=downloads&page=1&page_size=25"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["models"][0]["repo_id"] == "meta-llama/Llama-3.2-3B-Instruct"
    assert payload["has_more"] is True

###############################################################################
def test_huggingface_download_endpoint_returns_success(
    client: TestClient, monkeypatch
) -> None:
    monkeypatch.setattr(
        provider_service,
        "download_huggingface_model",
        lambda *, repo_id, session_name="default": HuggingFaceModelDownloadResponse(
            ok=True,
            repo_id=repo_id,
            message=f"Started download for Hugging Face model '{repo_id}'.",
            destination_path=f"data/models/huggingface/{repo_id.replace('/', '--')}",
            already_downloaded=False,
            job_id="job-1234",
            status="running",
            progress=0.0,
            downloaded_bytes=0,
            total_bytes=1024,
            poll_interval=1.0,
        ),
    )

    response = client.post(
        "/providers/huggingface/download",
        json={"repo_id": "meta-llama/Llama-3.2-3B-Instruct"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["repo_id"] == "meta-llama/Llama-3.2-3B-Instruct"
    assert payload["job_id"] == "job-1234"
    assert payload["status"] == "running"

###############################################################################
def test_huggingface_download_status_endpoint_returns_payload(
    client: TestClient, monkeypatch
) -> None:
    monkeypatch.setattr(
        provider_service,
        "get_huggingface_download_status",
        lambda *, job_id: HuggingFaceModelDownloadStatusResponse(
            job_id=job_id,
            repo_id="meta-llama/Llama-3.2-3B-Instruct",
            destination_path="data/models/huggingface/meta-llama--Llama-3.2-3B-Instruct",
            status="running",
            progress=42.0,
            message="Downloading files...",
            downloaded_bytes=420,
            total_bytes=1000,
            error=None,
        ),
    )

    response = client.get("/providers/huggingface/download/job-1234")

    assert response.status_code == 200
    payload = response.json()
    assert payload["job_id"] == "job-1234"
    assert payload["status"] == "running"
    assert payload["progress"] == 42.0

###############################################################################
def test_huggingface_download_cancel_endpoint_returns_success(
    client: TestClient, monkeypatch
) -> None:
    monkeypatch.setattr(
        provider_service,
        "cancel_huggingface_download",
        lambda *, job_id: HuggingFaceModelDownloadCancelResponse(
            ok=True,
            job_id=job_id,
            repo_id="meta-llama/Llama-3.2-3B-Instruct",
            message="Cancellation requested.",
        ),
    )

    response = client.delete("/providers/huggingface/download/job-1234")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["job_id"] == "job-1234"

###############################################################################
def test_compile_endpoint_returns_diagnostics_for_type_mismatch(
    client: TestClient,
) -> None:
    response = client.post(
        "/executions/compile",
        json={
            "definition": {
                "schema_version": 2,
                "nodes": [
                    {
                        "node_id": "doc_1",
                        "node_type": "LOAD_DOCUMENTS",
                        "node_version": 1,
                        "parameters": {"folder_path": "C:/tmp", "recursive": False},
                    },
                    {
                        "node_id": "output_1",
                        "node_type": "TEXT_OUTPUT",
                        "node_version": 1,
                        "parameters": {},
                    },
                ],
                "connections": [
                    {
                        "from_node": "doc_1",
                        "from_output": "documents",
                        "to_node": "output_1",
                        "to_input": "text",
                    },
                ],
                "metadata": {},
            }
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["valid"] is False
    messages = [item["message"] for item in payload["diagnostics"]]
    assert any("Type mismatch" in message for message in messages)

# Provider routes

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
    assert not by_provider["ollama"]
    assert not by_provider["huggingface"]
    assert not by_provider["lmstudio"]
    assert not by_provider["llama"]
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
    assert providers["deepseek"]["supports_tool_selection"] is True
    assert providers["deepseek"]["supports_native_tool_protocol"] is False
    assert providers["deepseek"]["supports_tool_calling"] is False
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
