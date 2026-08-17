from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


###############################################################################
def _env_text(key: str) -> str | None:
    value = os.getenv(key)
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None

###############################################################################
def _env_int(key: str, default: int) -> int:
    value = _env_text(key)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default

###############################################################################
def load_sqlite_settings_from_env() -> dict[str, Any]:
    return {
        "insert_batch_size": _env_int("DATABASE_INSERT_BATCH_SIZE", 1000),
    }

###############################################################################
@dataclass(frozen=True)
class SQLiteSettings:
    insert_batch_size: int

###############################################################################
@dataclass(frozen=True)
class GlobalSettings:
    seed: int

###############################################################################
@dataclass(frozen=True)
class JobsSettings:
    polling_interval: float

###############################################################################
@dataclass(frozen=True)
class ServerSettings:
    database: SQLiteSettings
    global_settings: GlobalSettings
    jobs: JobsSettings

###############################################################################
class JsonSQLiteSettings(BaseModel):
    insert_batch_size: int = Field(default=1000, ge=1)

###############################################################################
class JsonGlobalSettings(BaseModel):
    seed: int = 42

###############################################################################
class JsonJobsSettings(BaseModel):
    polling_interval: float = 1.0

###############################################################################
class RuntimeConfigurationSettings(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)
    global_settings: JsonGlobalSettings = Field(
        default_factory=JsonGlobalSettings, alias="global"
    )
    jobs: JsonJobsSettings = Field(default_factory=JsonJobsSettings)

    # -------------------------------------------------------------------------
    def to_server_settings(self, *, database: SQLiteSettings) -> ServerSettings:
        return ServerSettings(
            database=database,
            global_settings=GlobalSettings(seed=self.global_settings.seed),
            jobs=JobsSettings(polling_interval=self.jobs.polling_interval),
        )

###############################################################################
def get_sqlite_settings_from_env() -> SQLiteSettings:
    settings = JsonSQLiteSettings.model_validate(load_sqlite_settings_from_env())
    return SQLiteSettings(insert_batch_size=settings.insert_batch_size)
