from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field

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
    retention_days: int

###############################################################################
@dataclass(frozen=True)
class ServerSettings:
    database: SQLiteSettings
    global_settings: GlobalSettings
    jobs: JobsSettings

###############################################################################
class JsonGlobalSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    seed: int = 42

###############################################################################
class JsonJobsSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    polling_interval: float = 1.0
    retention_days: int = Field(default=30, ge=1)

###############################################################################
class RuntimeConfigurationSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    global_settings: JsonGlobalSettings = Field(
        default_factory=JsonGlobalSettings, alias="global"
    )
    jobs: JsonJobsSettings = Field(default_factory=JsonJobsSettings)

    # -------------------------------------------------------------------------
    def to_server_settings(self, *, database: SQLiteSettings) -> ServerSettings:
        return ServerSettings(
            database=database,
            global_settings=GlobalSettings(seed=self.global_settings.seed),
            jobs=JobsSettings(
                polling_interval=self.jobs.polling_interval,
                retention_days=self.jobs.retention_days,
            ),
        )
