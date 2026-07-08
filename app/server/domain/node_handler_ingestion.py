from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


SUPPORTED_DOCUMENT_EXTENSIONS = {
    ".txt",
    ".md",
    ".markdown",
    ".html",
    ".htm",
    ".json",
    ".pdf",
    ".docx",
}
LOAD_DOCUMENTS_SUPPORTED_EXTENSIONS = {
    ".txt",
    ".md",
    ".markdown",
    ".pdf",
    ".docx",
    ".rtf",
    ".html",
    ".htm",
    ".json",
    ".csv",
    ".tsv",
    ".log",
    ".xml",
    ".yaml",
    ".yml",
}
SUPPORTED_DATABASE_ENGINES = {"sqlite", "postgres", "postgresql", "mysql"}
POSTGRES_ENGINES = {"postgres", "postgresql"}

###############################################################################
def _parse_json_value(value: Any, label: str) -> Any:
    if isinstance(value, (dict, list, int, float, bool)) or value is None:
        return value
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{label} must not be empty")
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label} must be valid JSON") from exc

###############################################################################
def normalize_database_engine(value: Any, *, label: str = "engine") -> str:
    normalized = str(value or "").strip().lower()
    if normalized in POSTGRES_ENGINES:
        return "postgresql"
    if normalized == "mysql":
        return "mysql"
    if normalized == "sqlite":
        return "sqlite"
    raise ValueError(
        f"{label} must be one of: {', '.join(sorted(SUPPORTED_DATABASE_ENGINES))}"
    )

###############################################################################
class DirectoryLoaderParameters(BaseModel):
    directory_path: str
    recursive: bool = True
    include_extensions: list[str] = Field(
        default_factory=lambda: sorted(SUPPORTED_DOCUMENT_EXTENSIONS)
    )

    # -------------------------------------------------------------------------
    @field_validator("directory_path")
    @classmethod
    def validate_directory_path(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("directory_path must not be empty")
        return normalized

    # -------------------------------------------------------------------------
    @field_validator("include_extensions", mode="before")
    @classmethod
    def validate_extensions(cls, value: Any) -> list[str]:
        parsed = (
            _parse_json_value(value, "include_extensions")
            if isinstance(value, str)
            else value
        )
        if not isinstance(parsed, list) or not all(
            isinstance(item, str) for item in parsed
        ):
            raise ValueError(
                "include_extensions must be a JSON array of file extensions"
            )
        return [
            item.lower() if item.startswith(".") else f".{item.lower()}"
            for item in parsed
        ]

###############################################################################
class LoadDocumentsParameters(BaseModel):
    folder_path: str
    recursive: bool = True

    # -------------------------------------------------------------------------
    @field_validator("folder_path")
    @classmethod
    def validate_folder_path(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("folder_path must not be empty")
        return normalized

###############################################################################
class DocumentTextExtractorParameters(BaseModel):
    include_empty_pages: bool = False

###############################################################################
class DatabaseConnectionParameters(BaseModel):
    engine: str = "sqlite"
    database_name: str = ""
    host: str = ""
    port: int | None = 5432
    username: str = ""
    password: str = ""
    file_path: str = ""
    options: dict[str, Any] = Field(default_factory=dict)
    connect_timeout_s: float = Field(default=5.0, ge=1.0, le=60.0)

    # -------------------------------------------------------------------------
    @field_validator("engine")
    @classmethod
    def validate_engine(cls, value: str) -> str:
        return normalize_database_engine(value, label="engine")

    # -------------------------------------------------------------------------
    @field_validator("options", mode="before")
    @classmethod
    def validate_options(cls, value: Any) -> dict[str, Any]:
        if value in (None, "", {}):
            return {}
        parsed = (
            _parse_json_value(value, "options") if isinstance(value, str) else value
        )
        if not isinstance(parsed, dict):
            raise ValueError("options must be a JSON object")
        return parsed

    # -------------------------------------------------------------------------
    @model_validator(mode="after")
    def validate_engine_specific_fields(self) -> "DatabaseConnectionParameters":
        if self.engine == "sqlite":
            if not self.file_path.strip():
                raise ValueError("sqlite connections require file_path")
            return self

        if not self.host.strip():
            raise ValueError(f"{self.engine} connections require host")
        if not self.database_name.strip():
            raise ValueError(f"{self.engine} connections require database_name")
        if not self.username.strip():
            raise ValueError(f"{self.engine} connections require username")
        if self.port is None:
            raise ValueError(f"{self.engine} connections require port")
        return self

###############################################################################
class SQLDatabaseParameters(BaseModel):
    db_engine: str = "postgres"
    db_host: str = "127.0.0.1"
    db_port: int = Field(default=5432, ge=1, le=65535)
    db_name: str = ""
    db_user: str = "postgres"
    db_password: str = "change_me"
    db_ssl: bool = False
    db_ssl_ca: str = ""
    db_connect_timeout: float = Field(default=30.0, ge=1.0, le=120.0)

    # -------------------------------------------------------------------------
    @field_validator("db_engine")
    @classmethod
    def validate_db_engine(cls, value: str) -> str:
        normalized = str(value or "").strip().lower()
        if normalized not in {"postgres", "mysql"}:
            raise ValueError("db_engine must be one of: postgres, mysql")
        return normalized

    # -------------------------------------------------------------------------
    @field_validator("db_host", "db_name", "db_user")
    @classmethod
    def validate_required_text_fields(cls, value: str, info: Any) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError(f"{info.field_name} must not be empty")
        return normalized

###############################################################################
class SQLFileDatabaseParameters(BaseModel):
    db_path: str = ""
    db_connect_timeout: float = Field(default=30.0, ge=1.0, le=120.0)

    # -------------------------------------------------------------------------
    @field_validator("db_path")
    @classmethod
    def validate_db_path(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("db_path must not be empty")
        return normalized
