from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from server.common.constants import CONFIGURATION_FILE
from server.domain.settings import (
    RuntimeConfigurationSettings,
    ServerSettings,
    get_database_settings_from_env,
)


###############################################################################
class RuntimeConfigurationManager:
    def __init__(self, configuration_file: str | Path = CONFIGURATION_FILE) -> None:
        self._configuration_file = Path(configuration_file)
        self._settings: RuntimeConfigurationSettings | None = None
        self._server_settings: ServerSettings | None = None

    # -------------------------------------------------------------------------
    @property
    def configuration_file(self) -> Path:
        return self._configuration_file

    # -------------------------------------------------------------------------
    def load(
        self, configuration_file: str | Path | None = None
    ) -> RuntimeConfigurationSettings:
        if configuration_file:
            self._configuration_file = Path(configuration_file)

        if not self._configuration_file.exists():
            raise RuntimeError(
                f"Configuration file not found: {self._configuration_file}"
            )

        try:
            payload = json.loads(self._configuration_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(
                f"Unable to load configuration from {self._configuration_file}"
            ) from exc

        if not isinstance(payload, dict):
            raise RuntimeError("Configuration must be a JSON object.")

        try:
            settings = RuntimeConfigurationSettings.model_validate(payload)
        except ValidationError as exc:
            raise RuntimeError(f"Invalid application settings: {exc}") from exc

        self._settings = settings
        self._server_settings = settings.to_server_settings(
            database=get_database_settings_from_env()
        )
        return settings

    # -------------------------------------------------------------------------
    def reload(self) -> RuntimeConfigurationSettings:
        return self.load()

    # -------------------------------------------------------------------------
    @property
    def settings(self) -> RuntimeConfigurationSettings:
        if self._settings is None:
            self.load()
        return self._settings

    # -------------------------------------------------------------------------
    @property
    def server_settings(self) -> ServerSettings:
        if self._server_settings is None:
            self.load()
        return self._server_settings

    # -------------------------------------------------------------------------
    def get_block(self, block_name: str) -> dict[str, Any]:
        blocks: dict[str, Any] = self.settings.model_dump(by_alias=True)
        block = blocks.get(block_name)
        if isinstance(block, dict):
            return block
        return {}

    # -------------------------------------------------------------------------
    def get_value(self, block_name: str, key: str, default: Any = None) -> Any:
        block = self.get_block(block_name)
        return block.get(key, default)
