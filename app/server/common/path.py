from __future__ import annotations

import os
from pathlib import Path

from dotenv import dotenv_values


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
APP_ROOT = REPOSITORY_ROOT / "app"
SERVER_ROOT = APP_ROOT / "server"
CLIENT_ROOT = APP_ROOT / "client"
SETTINGS_ROOT = REPOSITORY_ROOT / "settings"
FRONTEND_DIST_ROOT = CLIENT_ROOT / "dist"
FRONTEND_ASSETS_ROOT = FRONTEND_DIST_ROOT / "assets"
ENV_FILE = SETTINGS_ROOT / ".env"
ENV_EXAMPLE_FILE = SETTINGS_ROOT / ".env.example"
CONFIGURATION_FILE = SETTINGS_ROOT / "configurations.json"

RESOURCES_ENV_KEY = "PARAGRAPH_RESOURCES_DIR"
_DEFAULT_RESOURCES_ROOT = APP_ROOT / "resources"


###############################################################################
def resolve_resources_root() -> Path:
    """Resolve the shared resource root from the local environment settings."""
    configured_root = os.getenv(RESOURCES_ENV_KEY)
    if ENV_FILE.is_file():
        dotenv_settings = dotenv_values(ENV_FILE)
        if RESOURCES_ENV_KEY in dotenv_settings:
            configured_root = dotenv_settings[RESOURCES_ENV_KEY]

    if configured_root is None or not configured_root.strip():
        return _DEFAULT_RESOURCES_ROOT

    resource_root = Path(os.path.expandvars(configured_root.strip())).expanduser()
    if not resource_root.is_absolute():
        resource_root = REPOSITORY_ROOT / resource_root
    return resource_root


RESOURCES_ROOT = resolve_resources_root()
ARTIFACT_ROOT = RESOURCES_ROOT / "artifacts"
LOGS_ROOT = RESOURCES_ROOT / "logs"
MODELS_ROOT = RESOURCES_ROOT / "models"
