from __future__ import annotations

import json
import re
from typing import Any


def coerce_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    return json.dumps(value)


def coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def coerce_int(value: Any, default: int) -> int:
    if value is None:
        return default
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def coerce_float(value: Any, default: float) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def parse_json_value(value: Any, label: str) -> Any:
    if isinstance(value, (dict, list, int, float, bool)) or value is None:
        return value
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{label} must not be empty")
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label} must be valid JSON") from exc


def normalize_provider_name(provider: Any, default: str = "ollama") -> str:
    normalized = coerce_text(provider or default).strip().lower()
    if normalized == "anthropic":
        return "claude"
    return normalized or default


def strip_html(text: str) -> str:
    without_scripts = re.sub(r"<script\b[^<]*(?:(?!</script>)<[^<]*)*</script>", " ", text, flags=re.IGNORECASE)
    without_styles = re.sub(r"<style\b[^<]*(?:(?!</style>)<[^<]*)*</style>", " ", without_scripts, flags=re.IGNORECASE)
    without_tags = re.sub(r"<[^>]+>", " ", without_styles)
    return re.sub(r"\s+", " ", without_tags).strip()


def validate_schema_definition(schema: Any, path: str = "$") -> None:
    if not isinstance(schema, dict):
        raise ValueError("response_schema must be a JSON object")

    allowed_keys = {"type", "properties", "required", "items", "additionalProperties", "enum"}
    unsupported = sorted(set(schema) - allowed_keys)
    if unsupported:
        raise ValueError(f"Unsupported JSON Schema keys at {path}: {', '.join(unsupported)}")

    schema_type = schema.get("type")
    if schema_type is not None and schema_type not in {"object", "array", "string", "number", "integer", "boolean", "null"}:
        raise ValueError(f"Unsupported JSON Schema type at {path}: {schema_type}")

    properties = schema.get("properties")
    if properties is not None:
        if not isinstance(properties, dict):
            raise ValueError(f"properties at {path} must be an object")
        for key, value in properties.items():
            validate_schema_definition(value, f"{path}.properties.{key}")

    required = schema.get("required")
    if required is not None:
        if not isinstance(required, list) or not all(isinstance(item, str) for item in required):
            raise ValueError(f"required at {path} must be an array of strings")

    if "items" in schema:
        validate_schema_definition(schema["items"], f"{path}.items")

    additional_properties = schema.get("additionalProperties")
    if additional_properties is not None and not isinstance(additional_properties, bool):
        raise ValueError(f"additionalProperties at {path} must be a boolean")

    enum = schema.get("enum")
    if enum is not None and not isinstance(enum, list):
        raise ValueError(f"enum at {path} must be an array")


def validate_json_against_schema(value: Any, schema: dict[str, Any], path: str = "$") -> None:
    schema_type = schema.get("type")
    if schema_type == "object":
        if not isinstance(value, dict):
            raise ValueError(f"Structured output at {path} must be an object")
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        additional_properties = schema.get("additionalProperties", True)
        for key in required:
            if key not in value:
                raise ValueError(f"Structured output is missing required property '{key}' at {path}")
        if additional_properties is False:
            extra = sorted(set(value) - set(properties))
            if extra:
                raise ValueError(f"Structured output contains unexpected properties at {path}: {', '.join(extra)}")
        for key, child_schema in properties.items():
            if key in value:
                validate_json_against_schema(value[key], child_schema, f"{path}.{key}")
    elif schema_type == "array":
        if not isinstance(value, list):
            raise ValueError(f"Structured output at {path} must be an array")
        item_schema = schema.get("items")
        if item_schema is not None:
            for index, item in enumerate(value):
                validate_json_against_schema(item, item_schema, f"{path}[{index}]")
    elif schema_type == "string":
        if not isinstance(value, str):
            raise ValueError(f"Structured output at {path} must be a string")
    elif schema_type == "number":
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ValueError(f"Structured output at {path} must be a number")
    elif schema_type == "integer":
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValueError(f"Structured output at {path} must be an integer")
    elif schema_type == "boolean":
        if not isinstance(value, bool):
            raise ValueError(f"Structured output at {path} must be a boolean")
    elif schema_type == "null":
        if value is not None:
            raise ValueError(f"Structured output at {path} must be null")

    if "enum" in schema and value not in schema["enum"]:
        raise ValueError(f"Structured output at {path} must match one of the allowed enum values")
