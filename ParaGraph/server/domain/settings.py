from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


###############################################################################
@dataclass(frozen=True)
class DatabaseSettings:
    embedded_database: bool
    engine: str | None
    host: str | None
    port: int | None
    database_name: str | None
    username: str | None
    password: str | None
    ssl: bool
    ssl_ca: str | None
    connect_timeout: int
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
    database: DatabaseSettings
    global_settings: GlobalSettings
    jobs: JobsSettings


###############################################################################
class JsonDatabaseSettings(BaseModel):
    embedded_database: bool = True
    engine: str = "postgres"
    host: str | None = None
    port: int = Field(default=5432, ge=1, le=65535)
    name: str | None = None
    user: str | None = None
    password: str | None = None
    ssl: bool = False
    ssl_ca: str | None = None
    connect_timeout: int = Field(default=30, ge=1)
    insert_batch_size: int = Field(default=1000, ge=1)

    @field_validator("host", "name", "user", "password", "ssl_ca", mode="before")
    @classmethod
    def normalize_optional_strings(cls, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @field_validator("engine", mode="before")
    @classmethod
    def normalize_engine(cls, value: Any) -> str:
        text = str(value).strip() if value is not None else ""
        return text or "postgres"

    @model_validator(mode="after")
    def validate_external_database_requirements(self) -> "JsonDatabaseSettings":
        if self.embedded_database:
            return self

        missing: list[str] = []
        if not self.host:
            missing.append("database.host")
        if not self.name:
            missing.append("database.name")
        if not self.user:
            missing.append("database.user")

        if missing:
            joined = ", ".join(missing)
            raise ValueError(f"External database mode requires configuration keys: {joined}")
        return self


###############################################################################
class JsonGlobalSettings(BaseModel):
    seed: int = 42


###############################################################################
class JsonJobsSettings(BaseModel):
    polling_interval: float = 1.0


###############################################################################
class RuntimeConfigurationSettings(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)
    database: JsonDatabaseSettings = Field(default_factory=JsonDatabaseSettings)
    global_settings: JsonGlobalSettings = Field(default_factory=JsonGlobalSettings, alias="global")
    jobs: JsonJobsSettings = Field(default_factory=JsonJobsSettings)

    # -------------------------------------------------------------------------
    def to_server_settings(self) -> ServerSettings:
        db = self.database
        if self.database.embedded_database:
            database_settings = DatabaseSettings(
                embedded_database=True,
                engine=None,
                host=None,
                port=None,
                database_name=None,
                username=None,
                password=None,
                ssl=False,
                ssl_ca=None,
                connect_timeout=db.connect_timeout,
                insert_batch_size=db.insert_batch_size,
            )
        else:
            normalized_engine = db.engine.strip().lower()
            database_settings = DatabaseSettings(
                embedded_database=False,
                engine=normalized_engine,
                host=db.host,
                port=db.port,
                database_name=db.name,
                username=db.user,
                password=db.password,
                ssl=db.ssl,
                ssl_ca=db.ssl_ca,
                connect_timeout=db.connect_timeout,
                insert_batch_size=db.insert_batch_size,
            )

        return ServerSettings(
            database=database_settings,
            global_settings=GlobalSettings(seed=self.global_settings.seed),
            jobs=JobsSettings(polling_interval=self.jobs.polling_interval),
        )
