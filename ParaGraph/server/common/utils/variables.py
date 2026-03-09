from __future__ import annotations

import os
from dotenv import load_dotenv

from ParaGraph.server.common.constants import ENV_FILE_PATH
from ParaGraph.server.common.utils.logger import logger


# [LOAD ENVIRONMENT VARIABLES]
###############################################################################
class EnvironmentVariables:
    def __init__(self) -> None:
        self.env_path = ENV_FILE_PATH
        if os.path.exists(self.env_path):
            load_dotenv(dotenv_path=self.env_path, override=False)
        else:
            logger.warning(".env file not found at: %s", self.env_path)

    # -------------------------------------------------------------------------
    def get(self, key: str, default: str | None = None) -> str | None:
        return os.getenv(key, default)


env_variables = EnvironmentVariables()

