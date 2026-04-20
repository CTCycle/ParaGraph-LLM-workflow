from __future__ import annotations

from pathlib import Path
from os.path import abspath, join

# [PATHS]
###############################################################################
ROOT_DIR = abspath(join(__file__, "../../../.."))
PROJECT_DIR = join(ROOT_DIR, "ParaGraph")
SETTING_PATH = join(PROJECT_DIR, "settings")
RESOURCES_PATH = join(PROJECT_DIR, "resources")
ARTIFACT_ROOT = Path(RESOURCES_PATH) / "artifacts"
LOGS_PATH = join(RESOURCES_PATH, "logs")
ENV_FILE_PATH = join(SETTING_PATH, ".env")
MODELS_PATH = join(RESOURCES_PATH, "models")
CHECKPOINT_PATH = join(RESOURCES_PATH, "checkpoints")
DATABASE_FILENAME = "database.db"

###############################################################################
CONFIGURATION_FILE = join(SETTING_PATH, "configurations.json")

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
