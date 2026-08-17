from __future__ import annotations

import importlib
import json
import os
from pathlib import Path

import pytest

from server.common import path as common_path
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
def test_environment_loader_creates_missing_env_from_example(
    tmp_path: Path,
) -> None:
    env_path = tmp_path / ".env"
    example_path = tmp_path / ".env.example"
    _write_env(example_path, ["FASTAPI_HOST=from_example"])

    loader = EnvironmentLoader(env_path)

    loaded_path = loader.ensure_loaded()

    assert loaded_path == env_path
    assert env_path.read_text(encoding="utf-8") == example_path.read_text(
        encoding="utf-8"
    )
    assert os.getenv("FASTAPI_HOST") == "from_example"

###############################################################################
def test_environment_loader_preserves_existing_env_over_example(
    tmp_path: Path,
) -> None:
    env_path = tmp_path / ".env"
    example_path = tmp_path / ".env.example"
    _write_env(example_path, ["FASTAPI_HOST=from_example"])
    _write_env(env_path, ["FASTAPI_HOST=from_local"])

    loader = EnvironmentLoader(env_path)

    loader.ensure_loaded()

    assert env_path.read_text(encoding="utf-8") == "FASTAPI_HOST=from_local\n"
    assert os.getenv("FASTAPI_HOST") == "from_local"

###############################################################################
def test_resources_root_can_be_overridden_by_environment_file(
    tmp_path: Path, monkeypatch
) -> None:
    configured_root = tmp_path / "paragraph-resources"
    env_path = tmp_path / ".env"
    _write_env(env_path, [f"PARAGRAPH_RESOURCES_DIR={configured_root}"])
    monkeypatch.setattr(common_path, "ENV_FILE", env_path)

    assert common_path.resolve_resources_root() == configured_root

###############################################################################
def test_server_package_import_has_no_bootstrap_side_effect(monkeypatch) -> None:
    monkeypatch.setenv("PARAGRAPH_CLOUD_MODE", "false")

    import server as server_package

    importlib.reload(server_package)

    assert os.getenv("PARAGRAPH_CLOUD_MODE") == "false"

###############################################################################
def test_application_database_settings_are_sqlite_only(
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
    _write_env(env_path, ["DATABASE_INSERT_BATCH_SIZE=37"])

    runtime = ConfigurationRuntime(environment_loader=EnvironmentLoader(env_path))
    settings = runtime.get_server_settings(config_path=config_path)

    assert settings.database.insert_batch_size == 37
    assert not hasattr(settings.database, "engine")

###############################################################################
def test_application_database_settings_reject_non_positive_batch_size(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "configurations.json"
    env_path = tmp_path / ".env"
    _write_json(config_path, {"global": {"seed": 42}, "jobs": {"polling_interval": 1.0}})
    _write_env(env_path, ["DATABASE_INSERT_BATCH_SIZE=0"])

    runtime = ConfigurationRuntime(environment_loader=EnvironmentLoader(env_path))

    with pytest.raises(ValueError, match="greater than or equal to 1"):
        _ = runtime.get_server_settings(config_path=config_path)

###############################################################################
def test_runtime_settings_ignore_database_block_from_json(tmp_path: Path) -> None:
    config_path = tmp_path / "configurations.json"
    env_path = tmp_path / ".env"
    _write_json(
        config_path,
        {
            "database": {
                "mode": "legacy",
            },
            "global": {"seed": 7},
            "jobs": {"polling_interval": 2.5},
        },
    )
    _write_env(env_path, ["DATABASE_INSERT_BATCH_SIZE=1000"])

    runtime = ConfigurationRuntime(environment_loader=EnvironmentLoader(env_path))
    runtime.initialize(force=True, configuration_file=config_path)

    runtime_settings = runtime.get_runtime_settings()
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
