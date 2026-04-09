from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, ClassVar

from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator
from pydantic.fields import FieldInfo
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict

from ParaGraph.server.common.constants import CONFIGURATION_FILE
from ParaGraph.server.configurations.bootstrap import ensure_environment_loaded
from ParaGraph.server.domain.settings import DatabaseSettings, GlobalSettings, JobsSettings, ServerSettings


###############################################################################
class JsonDatabaseSettings(BaseModel):
    embedded_database: bool = True


###############################################################################
class JsonGlobalSettings(BaseModel):
    seed: int = 42


###############################################################################
class JsonJobsSettings(BaseModel):
    polling_interval: float = 1.0


###############################################################################
class JsonConfigurationSettingsSource(PydanticBaseSettingsSource):
    def __init__(self, settings_cls: type[BaseSettings]) -> None:
        super().__init__(settings_cls)
        raw_path = getattr(settings_cls, "_configuration_file", CONFIGURATION_FILE)
        self.configuration_file = Path(raw_path)

    # -------------------------------------------------------------------------
    def get_field_value(self, field: FieldInfo, field_name: str) -> tuple[Any, str, bool]:
        return None, field_name, False

    # -------------------------------------------------------------------------
    def __call__(self) -> dict[str, Any]:
        if not self.configuration_file.exists():
            raise RuntimeError(f"Configuration file not found: {self.configuration_file}")

        try:
            payload = json.loads(self.configuration_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Unable to load configuration from {self.configuration_file}") from exc

        if not isinstance(payload, dict):
            raise RuntimeError("Configuration must be a JSON object.")

        return {
            "database": payload.get("database", {}),
            "global_settings": payload.get("global", {}),
            "jobs": payload.get("jobs", {}),
        }


###############################################################################
class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="",
        case_sensitive=False,
        extra="ignore",
    )

    _configuration_file: ClassVar[str] = CONFIGURATION_FILE

    database: JsonDatabaseSettings = Field(default_factory=JsonDatabaseSettings)
    global_settings: JsonGlobalSettings = Field(default_factory=JsonGlobalSettings)
    jobs: JsonJobsSettings = Field(default_factory=JsonJobsSettings)

    fastapi_host: str = "127.0.0.1"
    fastapi_port: int = Field(default=8000, ge=1, le=65535)
    ui_host: str = "127.0.0.1"
    ui_port: int = Field(default=8001, ge=1, le=65535)
    vite_api_base_url: str = "/api"
    paragraph_deployment_mode: str = "local"
    paragraph_cloud_mode: str | None = None
    reload: bool = True

    db_engine: str = "postgres"
    db_host: str | None = None
    db_port: int = Field(default=5432, ge=1, le=65535)
    db_name: str | None = None
    db_user: str | None = None
    db_password: str | None = None
    db_ssl: bool = False
    db_ssl_ca: str | None = None
    db_connect_timeout: int = Field(default=10, ge=1)
    db_insert_batch_size: int = Field(default=1000, ge=1)

    llm_timeout_s: float = Field(default=30.0, gt=0)

    @field_validator(
        "fastapi_host",
        "ui_host",
        "vite_api_base_url",
        "paragraph_deployment_mode",
        "paragraph_cloud_mode",
        "db_engine",
        "db_host",
        "db_name",
        "db_user",
        "db_password",
        "db_ssl_ca",
        mode="before",
    )
    @classmethod
    def normalize_optional_strings(cls, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @model_validator(mode="after")
    def validate_external_database_requirements(self) -> "AppSettings":
        if self.database.embedded_database:
            return self

        missing: list[str] = []
        if not self.db_host:
            missing.append("DB_HOST")
        if not self.db_name:
            missing.append("DB_NAME")
        if not self.db_user:
            missing.append("DB_USER")

        if missing:
            joined = ", ".join(missing)
            raise ValueError(f"External database mode requires environment keys: {joined}")
        return self

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        _ = dotenv_settings
        return (
            init_settings,
            env_settings,
            JsonConfigurationSettingsSource(settings_cls),
            file_secret_settings,
        )

    # -------------------------------------------------------------------------
    def to_server_settings(self) -> ServerSettings:
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
                connect_timeout=10,
                insert_batch_size=self.db_insert_batch_size,
            )
        else:
            normalized_engine = (self.db_engine or "postgres").strip().lower()
            database_settings = DatabaseSettings(
                embedded_database=False,
                engine=normalized_engine,
                host=self.db_host,
                port=self.db_port,
                database_name=self.db_name,
                username=self.db_user,
                password=self.db_password,
                ssl=self.db_ssl,
                ssl_ca=self.db_ssl_ca,
                connect_timeout=self.db_connect_timeout,
                insert_batch_size=self.db_insert_batch_size,
            )

        return ServerSettings(
            database=database_settings,
            global_settings=GlobalSettings(seed=self.global_settings.seed),
            jobs=JobsSettings(polling_interval=self.jobs.polling_interval),
        )


# -----------------------------------------------------------------------------
def _build_path_scoped_settings_class(config_path: str) -> type[AppSettings]:
    class PathScopedAppSettings(AppSettings):
        _configuration_file: ClassVar[str] = config_path

    return PathScopedAppSettings


# -----------------------------------------------------------------------------
def _load_app_settings(settings_cls: type[AppSettings]) -> AppSettings:
    ensure_environment_loaded()
    try:
        return settings_cls()
    except ValidationError as exc:
        raise RuntimeError(f"Invalid application settings: {exc}") from exc


###############################################################################
@lru_cache(maxsize=1)
def get_app_settings() -> AppSettings:
    return _load_app_settings(AppSettings)


# -----------------------------------------------------------------------------
def get_server_settings(config_path: str | None = None) -> ServerSettings:
    if config_path:
        scoped_class = _build_path_scoped_settings_class(config_path=config_path)
        return _load_app_settings(scoped_class).to_server_settings()
    return get_app_settings().to_server_settings()


# -----------------------------------------------------------------------------
def reload_settings_for_tests() -> AppSettings:
    get_app_settings.cache_clear()
    return get_app_settings()
