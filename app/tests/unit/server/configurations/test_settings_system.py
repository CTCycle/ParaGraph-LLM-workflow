from __future__ import annotations

import importlib
import json
import os
from pathlib import Path

import pytest

from server.configurations.environment import EnvironmentLoader
from server.configurations.startup import (
    ConfigurationRuntime,
    get_server_settings,
    reset_configuration_runtime_for_tests,
)
from server.services.llm.providers import CloudLLMClient

###############################################################################
@pytest.fixture(autouse=True)
def reset_configuration_state() -> None:
    reset_configuration_runtime_for_tests()
    yield
    reset_configuration_runtime_for_tests()

###############################################################################
def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")

###############################################################################
def _write_env(path: Path, lines: list[str]) -> None:
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

###############################################################################
def test_environment_loader_overrides_existing_process_values(
    tmp_path: Path, monkeypatch
) -> None:
    env_path = tmp_path / ".env"
    _write_env(env_path, ["FASTAPI_HOST=from_dotenv"])

    loader = EnvironmentLoader(env_path)
    monkeypatch.setenv("FASTAPI_HOST", "from_process")

    loader.ensure_loaded()

    assert os.getenv("FASTAPI_HOST") == "from_dotenv"

###############################################################################
def test_environment_loader_is_idempotent_without_force(
    tmp_path: Path, monkeypatch
) -> None:
    env_path = tmp_path / ".env"
    _write_env(env_path, ["FASTAPI_HOST=first"])

    loader = EnvironmentLoader(env_path)
    monkeypatch.setenv("FASTAPI_HOST", "from_process")

    loader.ensure_loaded()
    _write_env(env_path, ["FASTAPI_HOST=second"])
    loader.ensure_loaded()

    assert os.getenv("FASTAPI_HOST") == "first"

###############################################################################
def test_environment_loader_returns_path_instance_for_existing_env(
    tmp_path: Path,
) -> None:
    env_path = tmp_path / ".env"
    _write_env(env_path, ["FASTAPI_HOST=from_dotenv"])

    loader = EnvironmentLoader(env_path)

    loaded_path = loader.ensure_loaded()

    assert loaded_path == env_path

###############################################################################
def test_server_package_import_has_no_bootstrap_side_effect(monkeypatch) -> None:
    monkeypatch.setenv("PARAGRAPH_CLOUD_MODE", "false")

    import server as server_package

    importlib.reload(server_package)

    assert os.getenv("PARAGRAPH_CLOUD_MODE") == "false"

###############################################################################
def test_environment_owned_db_embedded_ignores_stale_json_overlap(
    tmp_path: Path, monkeypatch
) -> None:
    config_path = tmp_path / "configurations.json"
    env_path = tmp_path / ".env"
    _write_json(
        config_path,
        {
            "database": {
                "embedded_database": False,
                "engine": "postgres",
                "host": "stale-host",
                "name": "stale_db",
                "user": "stale_user",
            },
            "global": {"seed": 42},
            "jobs": {"polling_interval": 1.0},
        },
    )
    _write_env(
        env_path,
        [
            "DATABASE_EMBEDDED=true",
            "DATABASE_URL=",
            "DATABASE_ENGINE=postgres",
            "DATABASE_HOST=remote-db",
            "DATABASE_PORT=5432",
            "DATABASE_NAME=remote_db",
            "DATABASE_USERNAME=remote_user",
            "DATABASE_PASSWORD=",
        ],
    )

    runtime = ConfigurationRuntime(environment_loader=EnvironmentLoader(env_path))
    settings = runtime.get_server_settings(config_path=config_path)

    assert settings.database.embedded_database is True
    assert settings.database.host is None
    assert settings.database.engine is None
    runtime_settings = runtime.get_runtime_settings()
    assert "database" not in runtime_settings.model_dump(by_alias=True)

###############################################################################
def test_external_database_requires_host_name_and_user(
    tmp_path: Path, monkeypatch
) -> None:
    config_path = tmp_path / "configurations.json"
    env_path = tmp_path / ".env"
    _write_json(
        config_path,
        {
            "global": {"seed": 42},
            "jobs": {"polling_interval": 1.0},
        },
    )
    _write_env(
        env_path,
        [
            "DATABASE_EMBEDDED=false",
            "DATABASE_URL=",
            "DATABASE_ENGINE=postgres",
            "DATABASE_HOST=",
            "DATABASE_NAME=",
            "DATABASE_USERNAME=",
            "DATABASE_PASSWORD=",
        ],
    )

    runtime = ConfigurationRuntime(environment_loader=EnvironmentLoader(env_path))

    with pytest.raises(
        RuntimeError, match="database.host, database.name, database.user"
    ):
        _ = runtime.get_server_settings(config_path=config_path)

###############################################################################
def test_database_url_populates_external_database_settings(
    tmp_path: Path, monkeypatch
) -> None:
    config_path = tmp_path / "configurations.json"
    env_path = tmp_path / ".env"
    _write_json(
        config_path,
        {
            "global": {"seed": 42},
            "jobs": {"polling_interval": 1.0},
        },
    )
    _write_env(
        env_path,
        [
            "DATABASE_EMBEDDED=false",
            "DATABASE_URL=postgresql://env_user:env_password@db.example.test:6543/env_db?sslmode=require&connect_timeout=17",
            "DATABASE_ENGINE=",
            "DATABASE_HOST=",
            "DATABASE_PORT=",
            "DATABASE_NAME=",
            "DATABASE_USERNAME=",
            "DATABASE_PASSWORD=",
            "DATABASE_SSL=",
            "DATABASE_CONNECT_TIMEOUT=",
        ],
    )

    runtime = ConfigurationRuntime(environment_loader=EnvironmentLoader(env_path))
    settings = runtime.get_server_settings(config_path=config_path)

    assert settings.database.embedded_database is False
    assert settings.database.engine == "postgresql"
    assert settings.database.host == "db.example.test"
    assert settings.database.port == 6543
    assert settings.database.database_name == "env_db"
    assert settings.database.username == "env_user"
    assert settings.database.password == "env_password"
    assert settings.database.ssl is True
    assert settings.database.connect_timeout == 17

###############################################################################
def test_runtime_settings_ignore_database_block_from_json(tmp_path: Path) -> None:
    config_path = tmp_path / "configurations.json"
    env_path = tmp_path / ".env"
    _write_json(
        config_path,
        {
            "database": {
                "embedded_database": False,
                "engine": "postgres",
                "host": "json-host",
                "name": "json_db",
                "user": "json_user",
            },
            "global": {"seed": 7},
            "jobs": {"polling_interval": 2.5},
        },
    )
    _write_env(env_path, ["DATABASE_EMBEDDED=true"])

    runtime = ConfigurationRuntime(environment_loader=EnvironmentLoader(env_path))

    runtime_settings = runtime.initialize(force=True, configuration_file=config_path)

    assert runtime_settings.model_dump(by_alias=True) == {
        "global": {"seed": 7},
        "jobs": {"polling_interval": 2.5},
    }

###############################################################################
def test_missing_configuration_file_fails_fast(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FASTAPI_HOST", "127.0.0.1")

    with pytest.raises(RuntimeError, match="Configuration file not found"):
        _ = get_server_settings(config_path=tmp_path / "missing.json")

###############################################################################
def test_invalid_configuration_file_fails_fast(tmp_path: Path, monkeypatch) -> None:
    config_path = tmp_path / "configurations.json"
    config_path.write_text("{not-json", encoding="utf-8")

    monkeypatch.setenv("FASTAPI_HOST", "127.0.0.1")

    with pytest.raises(RuntimeError, match="Unable to load configuration"):
        _ = get_server_settings(config_path=config_path)

###############################################################################
def test_cloud_provider_client_does_not_fallback_to_provider_env(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "env-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://example.invalid/v1")

    client = CloudLLMClient(provider="openai")

    assert client.api_key is None
    assert client.base_url == "https://api.openai.com/v1"
