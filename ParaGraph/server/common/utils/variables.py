from __future__ import annotations

import os

from ParaGraph.server.configurations.startup import get_configuration_runtime


# [LOAD ENVIRONMENT VARIABLES]
###############################################################################
class EnvironmentVariables:
    def __init__(self) -> None:
        self.env_path = get_configuration_runtime().environment().ensure_loaded()

    # -------------------------------------------------------------------------
    def get(self, key: str, default: str | None = None) -> str | None:
        return os.getenv(key, default)


env_variables = EnvironmentVariables()
