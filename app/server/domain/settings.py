from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off"}


###############################################################################
def _env_text(key: str) -> str | None:
    value = os.getenv(key)
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


###############################################################################
def _env_bool(key: str, default: bool) -> bool:
    value = _env_text(key)
    if value is None:
        return default
    normalized = value.lower()
    if normalized in _TRUE_VALUES:
        return True
    if normalized in _FALSE_VALUES:
        return False
    return default


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
def _database_url_settings(database_url: str) -> dict[str, Any]:
    parsed = urlparse(database_url)
    engine = parsed.scheme.strip().lower()
    database_name = parsed.path.lstrip("/") or None

    settings: dict[str, Any] = {
        "engine": engine or "postgres",
        "host": parsed.hostname or None,
        "port": parsed.port or 5432,
        "name": unquote(database_name) if database_name else None,
        "user": unquote(parsed.username) if parsed.username else None,
        "password": unquote(parsed.password) if parsed.password else None,
    }

    query = parse_qs(parsed.query, keep_blank_values=False)
    ssl_mode = (query.get("sslmode") or [None])[0]
    if ssl_mode:
        settings["ssl"] = ssl_mode.lower() not in {"disable", "false", "off", "0"}

    connect_timeout = (query.get("connect_timeout") or [None])[0]
    if connect_timeout is not None:
        try:
            settings["connect_timeout"] = int(connect_timeout)
        except ValueError:
            pass

    return settings


###############################################################################
def load_database_settings_from_env() -> dict[str, Any]:
    settings: dict[str, Any] = {
        "embedded_database": _env_bool("DATABASE_EMBEDDED", True),
        "engine": "postgres",
        "host": None,
        "port": 5432,
        "name": None,
        "user": None,
        "password": None,
        "ssl": False,
        "ssl_ca": None,
        "connect_timeout": 30,
        "insert_batch_size": 1000,
    }

    database_url = _env_text("DATABASE_URL")
    if database_url:
        settings.update(_database_url_settings(database_url))

    explicit_values: dict[str, Any] = {
        "engine": _env_text("DATABASE_ENGINE"),
        "host": _env_text("DATABASE_HOST"),
        "name": _env_text("DATABASE_NAME"),
        "user": _env_text("DATABASE_USERNAME"),
        "password": _env_text("DATABASE_PASSWORD"),
        "ssl_ca": _env_text("DATABASE_SSL_CA"),
    }
    for key, value in explicit_values.items():
        if value is not None:
            settings[key] = value

    settings["port"] = _env_int("DATABASE_PORT", int(settings["port"]))
    settings["connect_timeout"] = _env_int(
        "DATABASE_CONNECT_TIMEOUT", int(settings["connect_timeout"])
    )
    settings["insert_batch_size"] = _env_int(
        "DATABASE_INSERT_BATCH_SIZE", int(settings["insert_batch_size"])
    )
    settings["ssl"] = _env_bool("DATABASE_SSL", bool(settings["ssl"]))

    return settings


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
            raise ValueError(
                f"External database mode requires configuration keys: {joined}"
            )
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
    global_settings: JsonGlobalSettings = Field(
        default_factory=JsonGlobalSettings, alias="global"
    )
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
