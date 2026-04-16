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
        environment_loader: EnvironmentLoader,
        configuration_manager: RuntimeConfigurationManager,
    ) -> None:
        self._environment_loader = environment_loader
        self._configuration_manager = configuration_manager
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
    def get_server_settings(self) -> ServerSettings:
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
    def get_env_value(self, key: str, default: str | None = None) -> str | None:
        if not self._initialized:
            self.initialize()
        return self._environment_loader.get(key=key, default=default)

    # -------------------------------------------------------------------------
    def get_env_int(self, key: str, default: int) -> int:
        if not self._initialized:
            self.initialize()
        return self._environment_loader.get_int(key=key, default=default)

    # -------------------------------------------------------------------------
    def get_env_float(self, key: str, default: float) -> float:
        if not self._initialized:
            self.initialize()
        return self._environment_loader.get_float(key=key, default=default)

    # -------------------------------------------------------------------------
    def get_env_bool(self, key: str, default: bool) -> bool:
        if not self._initialized:
            self.initialize()
        return self._environment_loader.get_bool(key=key, default=default)


_runtime = ConfigurationRuntime(
    environment_loader=EnvironmentLoader(),
    configuration_manager=RuntimeConfigurationManager(),
)


###############################################################################
def initialize_configurations(
    *, force: bool = False, configuration_file: str | None = None
) -> ServerSettings:
    return _runtime.initialize(force=force, configuration_file=configuration_file)


# -----------------------------------------------------------------------------
def reset_configuration_runtime_for_tests() -> None:
    _runtime.reset_for_tests()


# -----------------------------------------------------------------------------
def reload_runtime_configuration() -> ServerSettings:
    return _runtime.reload_configuration()


# -----------------------------------------------------------------------------
def get_server_settings(config_path: str | None = None) -> ServerSettings:
    if config_path:
        return _runtime.initialize(force=True, configuration_file=config_path)
    return _runtime.get_server_settings()


# -----------------------------------------------------------------------------
def get_runtime_settings() -> RuntimeConfigurationSettings:
    return _runtime.get_runtime_settings()


# -----------------------------------------------------------------------------
def get_configuration_block(block_name: str) -> dict[str, Any]:
    return _runtime.get_configuration_block(block_name)


# -----------------------------------------------------------------------------
def get_configuration_value(block_name: str, key: str, default: Any = None) -> Any:
    return _runtime.get_configuration_value(
        block_name=block_name, key=key, default=default
    )


# -----------------------------------------------------------------------------
def get_environment_value(key: str, default: str | None = None) -> str | None:
    return _runtime.get_env_value(key=key, default=default)


# -----------------------------------------------------------------------------
def get_fastapi_host() -> str:
    return get_environment_value("FASTAPI_HOST", "127.0.0.1") or "127.0.0.1"


# -----------------------------------------------------------------------------
def get_fastapi_port() -> int:
    return _runtime.get_env_int("FASTAPI_PORT", 8000)


# -----------------------------------------------------------------------------
def get_ui_host() -> str:
    return get_environment_value("UI_HOST", "127.0.0.1") or "127.0.0.1"


# -----------------------------------------------------------------------------
def get_ui_port() -> int:
    return _runtime.get_env_int("UI_PORT", 8001)


# -----------------------------------------------------------------------------
def get_vite_api_base_url() -> str:
    return get_environment_value("VITE_API_BASE_URL", "/api") or "/api"


# -----------------------------------------------------------------------------
def get_cloud_mode_enabled() -> bool:
    return _runtime.get_env_bool("PARAGRAPH_CLOUD_MODE", False)


# -----------------------------------------------------------------------------
def get_reload_enabled() -> bool:
    return _runtime.get_env_bool("RELOAD", True)


# -----------------------------------------------------------------------------
def get_llm_timeout_seconds() -> float:
    return _runtime.get_env_float("LLM_TIMEOUT_S", 30.0)
