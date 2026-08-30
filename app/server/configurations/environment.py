from __future__ import annotations

import os
import shutil
from pathlib import Path
from threading import Lock

from dotenv import load_dotenv

from server.common import path as common_path
from server.common.utils.logger import logger


_TRUE_VALUES = {"1", "true", "yes", "on"}


###############################################################################
class EnvironmentLoader:
    # -------------------------------------------------------------------------
    def __init__(self, env_file_path: str | Path | None = None) -> None:
        self._env_file_path = Path(env_file_path or common_path.ENV_FILE)
        self._env_example_file_path = (
            common_path.ENV_EXAMPLE_FILE
            if env_file_path is None
            else self._env_file_path.with_name(".env.example")
        )
        self._lock = Lock()
        self._bootstrapped = False

    # -------------------------------------------------------------------------
    def _ensure_env_file(self) -> bool:
        if self._env_file_path.exists():
            return True

        if not self._env_example_file_path.exists():
            logger.warning(
                ".env file not found at %s and template not found at %s",
                self._env_file_path,
                self._env_example_file_path,
            )
            return False

        self._env_file_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(self._env_example_file_path, self._env_file_path)
        logger.info(
            "Created %s from %s.",
            self._env_file_path,
            self._env_example_file_path,
        )
        return True

    # -------------------------------------------------------------------------
    def ensure_loaded(self, *, force: bool = False) -> Path | None:
        with self._lock:
            env_path = self._env_file_path
            if self._bootstrapped and not force:
                return env_path if env_path.exists() else None

            if self._ensure_env_file():
                load_dotenv(dotenv_path=env_path, override=True)

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
