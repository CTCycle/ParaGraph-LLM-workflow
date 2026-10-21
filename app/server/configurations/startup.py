from __future__ import annotations

from threading import RLock
from typing import Any

from server.configurations.environment import EnvironmentLoader
from server.configurations.settings import (
    GlobalSettings,
    JobsSettings,
    RuntimeConfigurationSettings,
    SQLiteSettings,
    ServerSettings,
)


###############################################################################
class ConfigurationRuntime:
    """Loads non-database environment values and exposes DB-loaded settings."""

    # -------------------------------------------------------------------------
    def __init__(self, *, environment_loader: EnvironmentLoader | None = None) -> None:
        self._environment_loader = environment_loader or EnvironmentLoader()
        self._lock = RLock()
        self._server_settings = ServerSettings(
            database=SQLiteSettings(insert_batch_size=1000),
            global_settings=GlobalSettings(seed=42),
            jobs=JobsSettings(polling_interval=1.0, retention_days=30),
        )

    # -------------------------------------------------------------------------
    def initialize(self) -> ServerSettings:
        self._environment_loader.ensure_loaded()
        return self._server_settings

    # -------------------------------------------------------------------------
    def reset_for_tests(self) -> None:
        with self._lock:
            self._environment_loader.reset_for_tests()
            self._server_settings = ServerSettings(
                database=SQLiteSettings(insert_batch_size=1000),
                global_settings=GlobalSettings(seed=42),
                jobs=JobsSettings(polling_interval=1.0, retention_days=30),
            )

    # -------------------------------------------------------------------------
    def install(self, settings: ServerSettings) -> None:
        with self._lock:
            self._server_settings = settings

    # -------------------------------------------------------------------------
    def get_server_settings(self) -> ServerSettings:
        self._environment_loader.ensure_loaded()
        return self._server_settings

    # -------------------------------------------------------------------------
    def get_runtime_settings(self) -> RuntimeConfigurationSettings:
        value = self._server_settings
        return RuntimeConfigurationSettings(
            global_settings={"seed": value.global_settings.seed},
            jobs={
                "polling_interval": value.jobs.polling_interval,
                "retention_days": value.jobs.retention_days,
            },
        )

    # -------------------------------------------------------------------------
    def reload_configuration(self) -> ServerSettings:
        return self._server_settings

    # -------------------------------------------------------------------------
    def get_configuration_block(self, block_name: str) -> dict[str, Any]:
        return self.get_runtime_settings().model_dump(by_alias=True).get(block_name, {})

    # -------------------------------------------------------------------------
    def get_configuration_value(self, block_name: str, key: str, default: Any = None) -> Any:
        return self.get_configuration_block(block_name).get(key, default)

    # -------------------------------------------------------------------------
    def environment(self) -> EnvironmentLoader:
        return self._environment_loader


_runtime = ConfigurationRuntime()


###############################################################################
def get_configuration_runtime() -> ConfigurationRuntime:
    return _runtime


###############################################################################
def get_server_settings() -> ServerSettings:
    return _runtime.get_server_settings()


###############################################################################
def get_runtime_settings() -> RuntimeConfigurationSettings:
    return _runtime.get_runtime_settings()


###############################################################################
def install_server_settings(settings: ServerSettings) -> None:
    _runtime.install(settings)


###############################################################################
def reset_configuration_runtime_for_tests() -> None:
    _runtime.reset_for_tests()
