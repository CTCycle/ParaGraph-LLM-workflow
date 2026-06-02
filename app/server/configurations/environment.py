from __future__ import annotations

import os
from pathlib import Path
from threading import Lock

from dotenv import load_dotenv

from server.common.constants import ENV_FILE_PATH as DEFAULT_ENV_FILE_PATH
from server.common.utils.logger import logger


_TRUE_VALUES = {"1", "true", "yes", "on"}


###############################################################################
class EnvironmentLoader:
    def __init__(self, env_file_path: str | Path | None = None) -> None:
        self._env_file_path = Path(env_file_path or DEFAULT_ENV_FILE_PATH)
        self._lock = Lock()
        self._bootstrapped = False

    # -------------------------------------------------------------------------
    def ensure_loaded(self, *, force: bool = False) -> Path | None:
        with self._lock:
            env_path = self._env_file_path
            if self._bootstrapped and not force:
                return env_path if env_path.exists() else None

            if env_path.exists():
                load_dotenv(dotenv_path=env_path, override=True)
            else:
                logger.warning(".env file not found at: %s", env_path)

            self._bootstrapped = True
            return env_path if env_path.exists() else None

    # -------------------------------------------------------------------------
    def reset_for_tests(self) -> None:
        with self._lock:
            self._bootstrapped = False

    # -------------------------------------------------------------------------
    def get(self, key: str, default: str | None = None) -> str | None:
        self.ensure_loaded()
        return os.getenv(key, default)

    # -------------------------------------------------------------------------
    def get_int(self, key: str, default: int) -> int:
        value = self.get(key)
        if value is None:
            return default
        try:
            return int(value.strip())
        except (TypeError, ValueError):
            return default

    # -------------------------------------------------------------------------
    def get_float(self, key: str, default: float) -> float:
        value = self.get(key)
        if value is None:
            return default
        try:
            return float(value.strip())
        except (TypeError, ValueError):
            return default

    # -------------------------------------------------------------------------
    def get_bool(self, key: str, default: bool) -> bool:
        value = self.get(key)
        if value is None:
            return default
        normalized = str(value).strip().lower()
        if not normalized:
            return default
        return normalized in _TRUE_VALUES

