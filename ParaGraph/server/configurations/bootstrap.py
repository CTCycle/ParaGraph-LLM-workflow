from __future__ import annotations

from pathlib import Path
from threading import Lock

from dotenv import load_dotenv

from ParaGraph.server.common.constants import ENV_FILE_PATH
from ParaGraph.server.common.utils.logger import logger


_BOOTSTRAP_LOCK = Lock()
_BOOTSTRAPPED = False


###############################################################################
def ensure_environment_loaded(*, force: bool = False) -> Path | None:
    global _BOOTSTRAPPED

    with _BOOTSTRAP_LOCK:
        env_path = Path(ENV_FILE_PATH)
        if _BOOTSTRAPPED and not force:
            return env_path if env_path.exists() else None

        if env_path.exists():
            load_dotenv(dotenv_path=env_path, override=True)
        else:
            logger.warning(".env file not found at: %s", env_path)

        _BOOTSTRAPPED = True
        return env_path if env_path.exists() else None


###############################################################################
def reset_environment_bootstrap_for_tests() -> None:
    global _BOOTSTRAPPED
    with _BOOTSTRAP_LOCK:
        _BOOTSTRAPPED = False
