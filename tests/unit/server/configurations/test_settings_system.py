from __future__ import annotations

import importlib
import json
import os
from pathlib import Path

import pytest

from ParaGraph.server.configurations.environment import EnvironmentLoader
from ParaGraph.server.configurations.startup import (
    get_server_settings,
    reset_configuration_runtime_for_tests,
)
from ParaGraph.server.services.llm.providers import CloudLLMClient


###############################################################################
@pytest.fixture(autouse=True)
def reset_configuration_state() -> None:
    reset_configuration_runtime_for_tests()
    yield
    reset_configuration_runtime_for_tests()


# -----------------------------------------------------------------------------
def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


# -----------------------------------------------------------------------------
def _write_env(path: Path, lines: list[str]) -> None:
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# -----------------------------------------------------------------------------
def test_environment_loader_overrides_existing_process_values(
    tmp_path: Path, monkeypatch
) -> None:
    env_path = tmp_path / ".env"
    _write_env(env_path, ["FASTAPI_HOST=from_dotenv"])

    loader = EnvironmentLoader(str(env_path))
    monkeypatch.setenv("FASTAPI_HOST", "from_process")

    loader.ensure_loaded()

    assert os.getenv("FASTAPI_HOST") == "from_dotenv"


# -----------------------------------------------------------------------------
def test_environment_loader_is_idempotent_without_force(
    tmp_path: Path, monkeypatch
) -> None:
    env_path = tmp_path / ".env"
    _write_env(env_path, ["FASTAPI_HOST=first"])

    loader = EnvironmentLoader(str(env_path))
    monkeypatch.setenv("FASTAPI_HOST", "from_process")

    loader.ensure_loaded()
    _write_env(env_path, ["FASTAPI_HOST=second"])
    loader.ensure_loaded()

    assert os.getenv("FASTAPI_HOST") == "first"


# -----------------------------------------------------------------------------
def test_server_package_import_has_no_bootstrap_side_effect(monkeypatch) -> None:
    monkeypatch.setenv("PARAGRAPH_CLOUD_MODE", "false")

    import ParaGraph.server as server_package

    importlib.reload(server_package)

    assert os.getenv("PARAGRAPH_CLOUD_MODE") == "false"


# -----------------------------------------------------------------------------
def test_json_owned_db_embedded_ignores_environment_overlap(
    tmp_path: Path, monkeypatch
) -> None:
    config_path = tmp_path / "configurations.json"
    _write_json(
        config_path,
        {
            "database": {"embedded_database": True},
            "global": {"seed": 42},
            "jobs": {"polling_interval": 1.0},
        },
    )

    monkeypatch.setenv("DB_EMBEDDED", "false")
    monkeypatch.setenv("DB_ENGINE", "postgres")
    monkeypatch.setenv("DB_HOST", "remote-db")
    monkeypatch.setenv("DB_NAME", "remote_db")
    monkeypatch.setenv("DB_USER", "remote_user")

    settings = get_server_settings(config_path=str(config_path))

    assert settings.database.embedded_database is True
    assert settings.database.host is None
    assert settings.database.engine is None


# -----------------------------------------------------------------------------
def test_external_database_requires_host_name_and_user(
    tmp_path: Path, monkeypatch
) -> None:
    config_path = tmp_path / "configurations.json"
    _write_json(
        config_path,
        {
            "database": {"embedded_database": False},
            "global": {"seed": 42},
            "jobs": {"polling_interval": 1.0},
        },
    )

    monkeypatch.setenv("FASTAPI_HOST", "127.0.0.1")

    with pytest.raises(
        RuntimeError, match="database.host, database.name, database.user"
    ):
        _ = get_server_settings(config_path=str(config_path))


# -----------------------------------------------------------------------------
def test_missing_configuration_file_fails_fast(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FASTAPI_HOST", "127.0.0.1")

    with pytest.raises(RuntimeError, match="Configuration file not found"):
        _ = get_server_settings(config_path=str(tmp_path / "missing.json"))


# -----------------------------------------------------------------------------
def test_invalid_configuration_file_fails_fast(tmp_path: Path, monkeypatch) -> None:
    config_path = tmp_path / "configurations.json"
    config_path.write_text("{not-json", encoding="utf-8")

    monkeypatch.setenv("FASTAPI_HOST", "127.0.0.1")

    with pytest.raises(RuntimeError, match="Unable to load configuration"):
        _ = get_server_settings(config_path=str(config_path))


# -----------------------------------------------------------------------------
def test_cloud_provider_client_does_not_fallback_to_provider_env(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "env-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://example.invalid/v1")

    client = CloudLLMClient(provider="openai")

    assert client.api_key is None
    assert client.base_url == "https://api.openai.com/v1"
