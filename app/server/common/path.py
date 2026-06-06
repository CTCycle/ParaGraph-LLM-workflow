from __future__ import annotations

from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
APP_ROOT = REPOSITORY_ROOT / "app"
SERVER_ROOT = APP_ROOT / "server"
CLIENT_ROOT = APP_ROOT / "client"
SETTINGS_ROOT = REPOSITORY_ROOT / "settings"
RESOURCES_ROOT = APP_ROOT / "resources"
FRONTEND_DIST_ROOT = CLIENT_ROOT / "dist"
FRONTEND_ASSETS_ROOT = FRONTEND_DIST_ROOT / "assets"
ARTIFACT_ROOT = RESOURCES_ROOT / "artifacts"
LOGS_ROOT = RESOURCES_ROOT / "logs"
MODELS_ROOT = RESOURCES_ROOT / "models"
CHECKPOINTS_ROOT = RESOURCES_ROOT / "checkpoints"
ENV_FILE = SETTINGS_ROOT / ".env"
CONFIGURATION_FILE = SETTINGS_ROOT / "configurations.json"
