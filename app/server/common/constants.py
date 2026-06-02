from __future__ import annotations

from pathlib import Path

# [PATHS]
###############################################################################
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
APP_ROOT = REPOSITORY_ROOT / "app"
SERVER_ROOT = APP_ROOT / "server"
CLIENT_ROOT = APP_ROOT / "client"
SETTINGS_ROOT = REPOSITORY_ROOT / "settings"
RESOURCES_ROOT = APP_ROOT / "resources"
FRONTEND_DIST_ROOT = CLIENT_ROOT / "dist"
FRONTEND_ASSETS_ROOT = FRONTEND_DIST_ROOT / "assets"
ARTIFACT_ROOT = RESOURCES_ROOT / "artifacts"

ROOT_DIR = str(REPOSITORY_ROOT)
PROJECT_DIR = str(APP_ROOT)
SETTING_PATH = str(SETTINGS_ROOT)
RESOURCES_PATH = str(RESOURCES_ROOT)
LOGS_PATH = str(RESOURCES_ROOT / "logs")
ENV_FILE_PATH = str(SETTINGS_ROOT / ".env")
MODELS_PATH = str(RESOURCES_ROOT / "models")
CHECKPOINT_PATH = str(RESOURCES_ROOT / "checkpoints")
DATABASE_FILENAME = "database.db"

###############################################################################
CONFIGURATION_FILE = str(SETTINGS_ROOT / "configurations.json")

# [FASTAPI METADATA]
###############################################################################
FASTAPI_TITLE = "ParaGraph Backend"
FASTAPI_DESCRIPTION = "ParaGraph workflow backend"
FASTAPI_VERSION = "1.0.0"

# [DATA TABLES]
###############################################################################
DATASETS_TABLE = "datasets"
DATASET_RECORDS_TABLE = "dataset_records"
PROCESSING_RUNS_TABLE = "processing_runs"
TRAINING_SAMPLES_TABLE = "training_samples"
VALIDATION_RUNS_TABLE = "validation_runs"
CHECKPOINTS_TABLE = "checkpoints"
INFERENCE_RUNS_TABLE = "inference_runs"
INFERENCE_REPORTS_TABLE = "inference_reports"

TABLE_REQUIRED_COLUMNS: dict[str, list[str]] = {
    DATASETS_TABLE: ["name", "created_at"],
    DATASET_RECORDS_TABLE: [
        "dataset_id",
        "asset_name",
        "asset_path",
        "content",
        "row_order",
    ],
    PROCESSING_RUNS_TABLE: ["dataset_id", "config_hash", "executed_at"],
    TRAINING_SAMPLES_TABLE: [
        "processing_run_id",
        "record_id",
        "split",
        "features_json",
    ],
    VALIDATION_RUNS_TABLE: ["dataset_id", "executed_at", "metrics_json"],
    CHECKPOINTS_TABLE: ["name", "path", "created_at"],
    INFERENCE_RUNS_TABLE: ["checkpoint_id", "request_id", "executed_at"],
    INFERENCE_REPORTS_TABLE: ["inference_run_id", "input_name", "output_text"],
}

