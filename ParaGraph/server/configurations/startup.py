from __future__ import annotations

from threading import Lock
from typing import Any

from ParaGraph.server.configurations.environment import EnvironmentLoader
from ParaGraph.server.configurations.management import RuntimeConfigurationManager
from ParaGraph.server.domain.settings import (
    RuntimeConfigurationSettings,
    ServerSettings,
)


###############################################################################
class ConfigurationRuntime:
    def __init__(
        self,
        *,
        environment_loader: EnvironmentLoader | None = None,
        configuration_manager: RuntimeConfigurationManager | None = None,
    ) -> None:
        self._environment_loader = environment_loader or EnvironmentLoader()
        self._configuration_manager = (
            configuration_manager or RuntimeConfigurationManager()
        )
        self._lock = Lock()
        self._initialized = False

    # -------------------------------------------------------------------------
    def initialize(
        self, *, force: bool = False, configuration_file: str | None = None
    ) -> ServerSettings:
        with self._lock:
            self._environment_loader.ensure_loaded(force=force)
            if force or not self._initialized:
                self._configuration_manager.load(configuration_file=configuration_file)
            self._initialized = True
            return self._configuration_manager.server_settings

    # -------------------------------------------------------------------------
    def reset_for_tests(self) -> None:
        with self._lock:
            self._initialized = False
            self._environment_loader.reset_for_tests()
            self._configuration_manager = RuntimeConfigurationManager()

    # -------------------------------------------------------------------------
    def get_server_settings(self, config_path: str | None = None) -> ServerSettings:
        if config_path:
            return self.initialize(force=True, configuration_file=config_path)
        if not self._initialized:
            self.initialize()
        return self._configuration_manager.server_settings

    # -------------------------------------------------------------------------
    def get_runtime_settings(self) -> RuntimeConfigurationSettings:
        if not self._initialized:
            self.initialize()
        return self._configuration_manager.settings

    # -------------------------------------------------------------------------
    def reload_configuration(self) -> ServerSettings:
        with self._lock:
            self._configuration_manager.reload()
            self._initialized = True
            return self._configuration_manager.server_settings

    # -------------------------------------------------------------------------
    def get_configuration_block(self, block_name: str) -> dict[str, Any]:
        if not self._initialized:
            self.initialize()
        return self._configuration_manager.get_block(block_name)

    # -------------------------------------------------------------------------
    def get_configuration_value(
        self, block_name: str, key: str, default: Any = None
    ) -> Any:
        if not self._initialized:
            self.initialize()
        return self._configuration_manager.get_value(
            block_name=block_name, key=key, default=default
        )

    # -------------------------------------------------------------------------
    def environment(self) -> EnvironmentLoader:
        return self._environment_loader


_runtime = ConfigurationRuntime()


###############################################################################
def get_configuration_runtime() -> ConfigurationRuntime:
    return _runtime


# -----------------------------------------------------------------------------
def get_server_settings(config_path: str | None = None) -> ServerSettings:
    return _runtime.get_server_settings(config_path=config_path)


# -----------------------------------------------------------------------------
def get_runtime_settings() -> RuntimeConfigurationSettings:
    return _runtime.get_runtime_settings()


# -----------------------------------------------------------------------------
def reset_configuration_runtime_for_tests() -> None:
    _runtime.reset_for_tests()

