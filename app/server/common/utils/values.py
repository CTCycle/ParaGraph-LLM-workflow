from __future__ import annotations

import json
from typing import Any


###############################################################################
def coerce_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    return json.dumps(value)


###############################################################################
def coerce_text_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [coerce_text(item) for item in value]
    return [coerce_text(value)]


###############################################################################
def coerce_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
    return default


###############################################################################
def coerce_int(
    value: Any, default: int, minimum: int | None = None, maximum: int | None = None
) -> int:
    if value is None:
        candidate = default
    else:
        try:
            candidate = int(float(value))
        except (TypeError, ValueError):
            candidate = default
    if minimum is not None and candidate < minimum:
        candidate = minimum
    if maximum is not None and candidate > maximum:
        candidate = maximum
    return candidate


###############################################################################
def coerce_float(
    value: Any,
    default: float,
    minimum: float | None = None,
    maximum: float | None = None,
) -> float:
    if value is None:
        candidate = default
    else:
        try:
            candidate = float(value)
        except (TypeError, ValueError):
            candidate = default
    if minimum is not None and candidate < minimum:
        candidate = minimum
    if maximum is not None and candidate > maximum:
        candidate = maximum
    return candidate


###############################################################################
def coerce_str_or_none(value: Any) -> str | None:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return None


###############################################################################
def parse_json_if_possible(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    text = value.strip()
    if not text:
        return value
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return value


###############################################################################
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


###############################################################################
def coerce_json_object(value: Any) -> dict[str, Any]:
    parsed = parse_json_if_possible(value)
    if not isinstance(parsed, dict):
        raise ValueError("value must be a JSON object")
    return parsed


###############################################################################
def coerce_json_array(value: Any) -> list[Any]:
    parsed = parse_json_if_possible(value)
    if not isinstance(parsed, list):
        raise ValueError("value must be a JSON array")
    return parsed


###############################################################################
def extract_top_level_json_fields(value: Any) -> dict[str, Any]:
    parsed = parse_json_if_possible(value)
    if isinstance(parsed, dict):
        return dict(parsed)
    return {}


###############################################################################
def merge_named_variables(*payloads: Any) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for payload in payloads:
        if payload is None:
            continue
        candidates = payload if isinstance(payload, list) else [payload]
        for candidate in candidates:
            fields = extract_top_level_json_fields(candidate)
            for key, value in fields.items():
                variable_name = str(key).strip()
                if variable_name:
                    merged[variable_name] = value
    return merged


###############################################################################
def render_variable_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, list) and all(isinstance(item, dict) for item in value):
        text_parts = [
            coerce_text(
                item.get("text") or item.get("content") or item.get("chunk") or ""
            ).strip()
            for item in value
        ]
        text_parts = [item for item in text_parts if item]
        if text_parts:
            return "\n\n".join(text_parts)
    if isinstance(value, dict):
        extracted = coerce_text(
            value.get("text") or value.get("content") or value.get("chunk") or ""
        ).strip()
        if extracted:
            return extracted
    try:
        return json.dumps(value, indent=2, ensure_ascii=True, default=str)
    except Exception:  # noqa: BLE001
        return str(value)


###############################################################################
def normalize_provider_name(provider: Any, default: str = "ollama") -> str:
    normalized = coerce_text(provider or default).strip().lower()
    return normalized or default


###############################################################################
def validate_schema_definition(schema: Any, path: str = "$") -> None:
    if not isinstance(schema, dict):
        raise ValueError("response_schema must be a JSON object")

    allowed_keys = {
        "type",
        "properties",
        "required",
        "items",
        "additionalProperties",
        "enum",
    }
    unsupported = sorted(set(schema) - allowed_keys)
    if unsupported:
        raise ValueError(
            f"Unsupported JSON Schema keys at {path}: {', '.join(unsupported)}"
        )

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

    properties = schema.get("properties")
    if properties is not None:
        if not isinstance(properties, dict):
            raise ValueError(f"properties at {path} must be an object")
        for key, value in properties.items():
            validate_schema_definition(value, f"{path}.properties.{key}")

    required = schema.get("required")
    if required is not None:
        if not isinstance(required, list) or not all(
            isinstance(item, str) for item in required
        ):
            raise ValueError(f"required at {path} must be an array of strings")

    if "items" in schema:
        validate_schema_definition(schema["items"], f"{path}.items")

    additional_properties = schema.get("additionalProperties")
    if additional_properties is not None and not isinstance(
        additional_properties, bool
    ):
        raise ValueError(f"additionalProperties at {path} must be a boolean")

    enum = schema.get("enum")
    if enum is not None and not isinstance(enum, list):
        raise ValueError(f"enum at {path} must be an array")


###############################################################################
def validate_json_against_schema(
    value: Any, schema: dict[str, Any], path: str = "$"
) -> None:
    schema_type = schema.get("type")
    if schema_type == "object":
        if not isinstance(value, dict):
            raise ValueError(f"Structured output at {path} must be an object")
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        additional_properties = schema.get("additionalProperties", True)
        for key in required:
            if key not in value:
                raise ValueError(
                    f"Structured output is missing required property '{key}' at {path}"
                )
        if additional_properties is False:
            extra = sorted(set(value) - set(properties))
            if extra:
                raise ValueError(
                    f"Structured output contains unexpected properties at {path}: {', '.join(extra)}"
                )
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
    elif schema_type == "null" and value is not None:
        raise ValueError(f"Structured output at {path} must be null")

    if "enum" in schema and value not in schema["enum"]:
        raise ValueError(
            f"Structured output at {path} must match one of the allowed enum values"
        )
