from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

# -----------------------------------------------------------------------------
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

# -----------------------------------------------------------------------------
def _validate_schema_keys(schema: dict[str, Any], path: str) -> None:
    allowed_keys = {"type", "properties", "required", "items", "additionalProperties", "enum"}
    unsupported = sorted(set(schema) - allowed_keys)
    if unsupported:
        raise ValueError(f"Unsupported JSON Schema keys at {path}: {', '.join(unsupported)}")


def _validate_schema_type(schema: dict[str, Any], path: str) -> None:
    schema_type = schema.get("type")
    if schema_type is not None and schema_type not in {
        "object",
        "array",
        "string",
        "number",
        "integer",
        "boolean",
        "null",
    }:
        raise ValueError(f"Unsupported JSON Schema type at {path}: {schema_type}")


def _validate_schema_properties(schema: dict[str, Any], path: str) -> None:
    properties = schema.get("properties")
    if properties is None:
        return
    if not isinstance(properties, dict):
        raise ValueError(f"properties at {path} must be an object")
    for key, value in properties.items():
        _validate_schema_definition(value, f"{path}.properties.{key}")


def _validate_schema_required(schema: dict[str, Any], path: str) -> None:
    required = schema.get("required")
    if required is not None and (not isinstance(required, list) or not all(isinstance(item, str) for item in required)):
        raise ValueError(f"required at {path} must be an array of strings")


def _validate_schema_items(schema: dict[str, Any], path: str) -> None:
    if "items" in schema:
        _validate_schema_definition(schema["items"], f"{path}.items")


def _validate_schema_additional_properties(schema: dict[str, Any], path: str) -> None:
    additional_properties = schema.get("additionalProperties")
    if additional_properties is not None and not isinstance(additional_properties, bool):
        raise ValueError(f"additionalProperties at {path} must be a boolean")


def _validate_schema_enum(schema: dict[str, Any], path: str) -> None:
    enum = schema.get("enum")
    if enum is not None and not isinstance(enum, list):
        raise ValueError(f"enum at {path} must be an array")


# -----------------------------------------------------------------------------
def _validate_schema_definition(schema: Any, path: str = "$") -> None:
    if not isinstance(schema, dict):
        raise ValueError("response_schema must be a JSON object")

    _validate_schema_keys(schema, path)
    _validate_schema_type(schema, path)
    _validate_schema_properties(schema, path)
    _validate_schema_required(schema, path)
    _validate_schema_items(schema, path)
    _validate_schema_additional_properties(schema, path)
    _validate_schema_enum(schema, path)


class PromptParameters(BaseModel):
    prompt_text: str = ""


class ImageInputParameters(BaseModel):
    file_path: str = ""


class ModelProviderParameters(BaseModel):
    provider: str = "ollama"
    model_name: str = ""


class ChatParameters(BaseModel):
    provider: str | None = None
    model_name: str | None = None
    context_window: int = Field(default=0, ge=0)
    max_tokens: int = Field(default=512, ge=1)
    use_reasoning: bool = False


class StructuredParameters(ChatParameters):
    response_schema: dict[str, Any]

    @field_validator("response_schema", mode="before")
    @classmethod
    def validate_schema(cls, value: Any) -> dict[str, Any]:
        schema = _parse_json_value(value, "response_schema")
        _validate_schema_definition(schema)
        return schema


class EmbeddingParameters(BaseModel):
    provider: str = "ollama"
    model_name: str = "nomic-embed-text"


class TextSplitParameters(BaseModel):
    delimiter: str = "\n"


class SaveTextParameters(BaseModel):
    output_path: str = ""
    separate_files: bool = False
    extension: str = ".txt"
    client_side_write: bool = False

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_storage_path(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        payload = dict(value)
        if "output_path" not in payload and "storage_path" in payload:
            payload["output_path"] = payload["storage_path"]
        return payload

    @field_validator("extension")
    @classmethod
    def validate_extension(cls, value: str) -> str:
        normalized = str(value or "").strip().lower()
        if normalized not in {".txt", ".md", ".doc", ".pdf"}:
            raise ValueError("extension must be one of: .txt, .md, .doc, .pdf")
        return normalized


class StorageParameters(BaseModel):
    storage_path: str = ""

    @field_validator("storage_path")
    @classmethod
    def validate_storage_path(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("storage_path is required. Select a local path.")
        return normalized


class RouterParameters(BaseModel):
    expected_value: str = ""
