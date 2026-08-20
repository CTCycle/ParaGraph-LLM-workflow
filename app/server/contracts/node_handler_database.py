from __future__ import annotations

import re
import json
from typing import Any

from pydantic import BaseModel, Field, field_validator

###############################################################################
def _parse_json_object(value: Any, label: str) -> dict[str, Any]:
    if value in (None, ""):
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{label} must be valid JSON") from exc
        if isinstance(parsed, dict):
            return parsed
    raise ValueError(f"{label} must be a JSON object")

###############################################################################
def _parse_columns(value: Any) -> list[str]:
    if value in (None, ""):
        return []
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return [item.strip() for item in value if item.strip()]
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    raise ValueError("columns must be a comma-separated string or an array of strings")

###############################################################################
class _TableParameters(BaseModel):
    table: str
    schema_name: str = ""

    # -------------------------------------------------------------------------
    @field_validator("table")
    @classmethod
    def validate_table(cls, value: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError("table is required")
        return normalized

###############################################################################
class CrudCreateParameters(_TableParameters):
    values: dict[str, Any] = Field(default_factory=dict)

    # -------------------------------------------------------------------------
    @field_validator("values", mode="before")
    @classmethod
    def validate_values(cls, value: Any) -> dict[str, Any]:
        return _parse_json_object(value, "values")

###############################################################################
class CrudReadParameters(_TableParameters):
    columns: list[str] = Field(default_factory=list)
    filters: dict[str, Any] = Field(default_factory=dict)
    limit: int = Field(default=100, ge=1, le=1_000)
    offset: int = Field(default=0, ge=0)
    order_by: str = ""

    # -------------------------------------------------------------------------
    @field_validator("columns", mode="before")
    @classmethod
    def validate_columns(cls, value: Any) -> list[str]:
        return _parse_columns(value)

    # -------------------------------------------------------------------------
    @field_validator("filters", mode="before")
    @classmethod
    def validate_filters(cls, value: Any) -> dict[str, Any]:
        return _parse_json_object(value, "filters")

###############################################################################
class CrudUpdateParameters(_TableParameters):
    values: dict[str, Any] = Field(default_factory=dict)
    filters: dict[str, Any] = Field(default_factory=dict)
    version_column: str = ""
    expected_version: Any = None
    increment_version: bool = False

    # -------------------------------------------------------------------------
    @field_validator("values", mode="before")
    @classmethod
    def validate_values(cls, value: Any) -> dict[str, Any]:
        return _parse_json_object(value, "values")

    # -------------------------------------------------------------------------
    @field_validator("filters", mode="before")
    @classmethod
    def validate_filters(cls, value: Any) -> dict[str, Any]:
        return _parse_json_object(value, "filters")

###############################################################################
class CrudDeleteParameters(_TableParameters):
    filters: dict[str, Any] = Field(default_factory=dict)
    version_column: str = ""
    expected_version: Any = None

    # -------------------------------------------------------------------------
    @field_validator("filters", mode="before")
    @classmethod
    def validate_filters(cls, value: Any) -> dict[str, Any]:
        return _parse_json_object(value, "filters")

###############################################################################
class CustomSqlQueryParameters(BaseModel):
    sql: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    read_only: bool = False

    # -------------------------------------------------------------------------
    @field_validator("parameters", mode="before")
    @classmethod
    def validate_parameters(cls, value: Any) -> dict[str, Any]:
        return _parse_json_object(value, "parameters")

    # -------------------------------------------------------------------------
    @field_validator("sql")
    @classmethod
    def validate_sql(cls, value: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError("sql is required")
        without_strings = re.sub(r"'(?:''|[^'])*'|\"(?:\"\"|[^\"])*\"", "", normalized)
        if ";" in without_strings.rstrip(";"):
            raise ValueError("sql must contain a single statement")
        return normalized.rstrip(";")

###############################################################################
class CrudUpsertParameters(_TableParameters):
    conflict_columns: list[str]
    insert_values: dict[str, Any]
    update_values: dict[str, Any]

    # -------------------------------------------------------------------------
    @field_validator("conflict_columns", mode="before")
    @classmethod
    def validate_conflict_columns(cls, value: Any) -> list[str]:
        return _parse_columns(value)

    # -------------------------------------------------------------------------
    @field_validator("insert_values", "update_values", mode="before")
    @classmethod
    def validate_upsert_values(cls, value: Any) -> dict[str, Any]:
        return _parse_json_object(value, "upsert values")
