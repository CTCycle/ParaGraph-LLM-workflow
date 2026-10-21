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
    reset_configuration_runtime_for_tests,
)

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
def test_resources_root_defaults_to_repository_data(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(common_path, "ENV_FILE", tmp_path / ".env")
    monkeypatch.delenv(common_path.RESOURCES_ENV_KEY, raising=False)

    assert common_path.resolve_resources_root() == (
        common_path.REPOSITORY_ROOT / "data"
    )

###############################################################################
def test_resources_root_can_be_overridden_by_environment_file(
    tmp_path: Path, monkeypatch
) -> None:
    configured_root = tmp_path / "paragraph-data"
    env_path = tmp_path / ".env"
    _write_env(env_path, [f"PARAGRAPH_RESOURCES_DIR={configured_root}"])
    monkeypatch.setattr(common_path, "ENV_FILE", env_path)
    monkeypatch.delenv(common_path.RESOURCES_ENV_KEY, raising=False)

    assert common_path.resolve_resources_root() == configured_root

###############################################################################
def test_resources_root_environment_overrides_environment_file(
    tmp_path: Path, monkeypatch
) -> None:
    environment_root = tmp_path / "environment-data"
    file_root = tmp_path / "file-data"
    env_path = tmp_path / ".env"
    _write_env(env_path, [f"PARAGRAPH_RESOURCES_DIR={file_root}"])
    monkeypatch.setattr(common_path, "ENV_FILE", env_path)
    monkeypatch.setenv(common_path.RESOURCES_ENV_KEY, str(environment_root))

    assert common_path.resolve_resources_root() == environment_root

###############################################################################
def test_resources_root_can_use_repository_relative_environment_path(
    tmp_path: Path, monkeypatch
) -> None:
    env_path = tmp_path / ".env"
    _write_env(env_path, ["PARAGRAPH_RESOURCES_DIR=custom-data"])
    monkeypatch.setattr(common_path, "ENV_FILE", env_path)
    monkeypatch.delenv(common_path.RESOURCES_ENV_KEY, raising=False)

    assert common_path.resolve_resources_root() == (
        common_path.REPOSITORY_ROOT / "custom-data"
    )

###############################################################################
def test_server_package_import_has_no_bootstrap_side_effect(monkeypatch) -> None:
    monkeypatch.setenv("PARAGRAPH_CLOUD_MODE", "false")

    import server as server_package

    importlib.reload(server_package)

    assert os.getenv("PARAGRAPH_CLOUD_MODE") == "false"

###############################################################################
def test_application_settings_are_not_read_from_legacy_json_or_environment(
    tmp_path: Path, monkeypatch
) -> None:
    config_path = tmp_path / "configurations.json"
    _write_json(
        config_path,
        {"global": {"seed": 7}, "jobs": {"polling_interval": 2.5}},
    )
    monkeypatch.setenv("DATABASE_INSERT_BATCH_SIZE", "37")

    runtime = ConfigurationRuntime(environment_loader=EnvironmentLoader(tmp_path / ".env"))
    settings = runtime.get_server_settings()

    assert settings.database.insert_batch_size == 1000
    assert settings.global_settings.seed == 42
    assert settings.jobs.polling_interval == 1.0
    assert config_path.is_file()

###############################################################################
def test_invalid_llm_timeout_environment_value_fails_fast(
    tmp_path: Path,
) -> None:
    env_path = tmp_path / ".env"
    _write_env(env_path, ["LLM_TIMEOUT_S=not-a-number"])
    loader = EnvironmentLoader(env_path)

    with pytest.raises(ValueError, match="LLM_TIMEOUT_S must be a number"):
        loader.get_float("LLM_TIMEOUT_S", 30.0)

###############################################################################
###############################################################################
def test_cloud_provider_client_does_not_fallback_to_provider_env(monkeypatch) -> None:
    from server.services.llm.providers import CloudLLMClient

    monkeypatch.setenv("OPENAI_API_KEY", "env-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://example.invalid/v1")

    client = CloudLLMClient(provider="openai")

    assert client.api_key is None
    assert client.base_url == "https://api.openai.com/v1"
