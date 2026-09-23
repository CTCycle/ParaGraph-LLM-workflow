from __future__ import annotations

from httpx import Response
from fastapi.testclient import TestClient

from server.contracts.configuration import (
    AppConfigurationPayload,
    ConfigurationProfileListResponse,
    ConfigurationProfileSummary,
    OllamaStatusResponse,
    ProviderConfiguration,
    ProviderStatusResponse,
)
from server.configurations.settings import SQLiteSettings
from server.repositories.configuration import ConfigurationRepository
from server.repositories.database.migration import run_database_migrations
from server.repositories.database.sqlite import SQLiteRepository
from server.services.configuration import configuration_service

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

        saved_profile = client.put(
            f"/configurations/profiles/{profile_name}", json=payload
        )
        assert_redacted(saved_profile)

        loaded_profile = client.get(
            f"/configurations/profiles/{profile_name}",
            params={"session_name": session_name},
        )
        assert_redacted(loaded_profile)
        assert repository.load_configuration_profile(
            session_name=session_name, profile_name=profile_name
        )["provider_configurations"][0]["api_key"] == sentinel

        updated_profile = client.put(
            f"/configurations/profiles/{profile_name}", json=loaded_profile.json()
        )
        assert_redacted(updated_profile)
        assert repository.load_configuration_profile(
            session_name=session_name, profile_name=profile_name
        )["provider_configurations"][0]["api_key"] == sentinel

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

    save_response = client.put(
        "/configurations/profiles/missing", json=_payload().model_dump(mode="json")
    )
    assert save_response.status_code == 400
    assert save_response.json()["detail"] == "Invalid profile name"
