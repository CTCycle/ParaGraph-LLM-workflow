from __future__ import annotations

import json
from typing import Any

from bs4 import BeautifulSoup


class NodeValueService:
    @staticmethod
    def coerce_text(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        if isinstance(value, (int, float, bool)):
            return str(value)
        return json.dumps(value)

    @staticmethod
    def coerce_bool(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        return str(value or "").strip().lower() in {"1", "true", "yes", "on"}

    @staticmethod
    def coerce_int(value: Any, default: int) -> int:
        if value is None:
            return default
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return default

    @staticmethod
    def coerce_float(value: Any, default: float) -> float:
        if value is None:
            return default
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def coerce_text_list(value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [NodeValueService.coerce_text(item) for item in value]
        return [NodeValueService.coerce_text(value)]

    @staticmethod
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

    @classmethod
    def coerce_json_object(cls, value: Any) -> dict[str, Any]:
        parsed = cls.parse_json_if_possible(value)
        if not isinstance(parsed, dict):
            raise ValueError("value must be a JSON object")
        return parsed

    @classmethod
    def coerce_json_array(cls, value: Any) -> list[Any]:
        parsed = cls.parse_json_if_possible(value)
        if not isinstance(parsed, list):
            raise ValueError("value must be a JSON array")
        return parsed

    @classmethod
    def extract_top_level_json_fields(cls, value: Any) -> dict[str, Any]:
        parsed = cls.parse_json_if_possible(value)
        if isinstance(parsed, dict):
            return dict(parsed)
        return {}

    @classmethod
    def merge_named_variables(cls, *payloads: Any) -> dict[str, Any]:
        merged: dict[str, Any] = {}
        for payload in payloads:
            if payload is None:
                continue
            candidates = payload if isinstance(payload, list) else [payload]
            for candidate in candidates:
                fields = cls.extract_top_level_json_fields(candidate)
                for key, value in fields.items():
                    variable_name = str(key).strip()
                    if variable_name:
                        merged[variable_name] = value
        return merged

    @classmethod
    def render_variable_value(cls, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        if isinstance(value, (int, float, bool)):
            return str(value)
        if isinstance(value, list):
            if all(isinstance(item, dict) for item in value):
                text_parts = [
                    cls.coerce_text(item.get("text") or item.get("content") or item.get("chunk") or "").strip()
                    for item in value
                ]
                text_parts = [item for item in text_parts if item]
                if text_parts:
                    return "\n\n".join(text_parts)
        if isinstance(value, dict):
            extracted = cls.coerce_text(
                value.get("text") or value.get("content") or value.get("chunk") or ""
            ).strip()
            if extracted:
                return extracted
        try:
            return json.dumps(value, indent=2, ensure_ascii=True, default=str)
        except Exception:  # noqa: BLE001
            return str(value)

    @staticmethod
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

    @classmethod
    def normalize_provider_name(cls, provider: Any, default: str = "ollama") -> str:
        normalized = cls.coerce_text(provider or default).strip().lower()
        return normalized or default

    @staticmethod
    def strip_html(text: str) -> str:
        soup = BeautifulSoup(text, "html.parser")
        for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
            tag.decompose()
        return " ".join(soup.get_text(" ").split())


class JsonSchemaService:
    @classmethod
    def validate_schema_definition(cls, schema: Any, path: str = "$") -> None:
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
                cls.validate_schema_definition(value, f"{path}.properties.{key}")

        required = schema.get("required")
        if required is not None:
            if not isinstance(required, list) or not all(
                isinstance(item, str) for item in required
            ):
                raise ValueError(f"required at {path} must be an array of strings")

        if "items" in schema:
            cls.validate_schema_definition(schema["items"], f"{path}.items")

        additional_properties = schema.get("additionalProperties")
        if additional_properties is not None and not isinstance(
            additional_properties, bool
        ):
            raise ValueError(f"additionalProperties at {path} must be a boolean")

        enum = schema.get("enum")
        if enum is not None and not isinstance(enum, list):
            raise ValueError(f"enum at {path} must be an array")

    @classmethod
    def validate_json_against_schema(
        cls, value: Any, schema: dict[str, Any], path: str = "$"
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
                    cls.validate_json_against_schema(
                        value[key], child_schema, f"{path}.{key}"
                    )
        elif schema_type == "array":
            if not isinstance(value, list):
                raise ValueError(f"Structured output at {path} must be an array")
            item_schema = schema.get("items")
            if item_schema is not None:
                for index, item in enumerate(value):
                    cls.validate_json_against_schema(
                        item, item_schema, f"{path}[{index}]"
                    )
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
            raise ValueError(
                f"Structured output at {path} must match one of the allowed enum values"
            )


node_value_service = NodeValueService()
json_schema_service = JsonSchemaService()


def coerce_text(value: Any) -> str:
    return node_value_service.coerce_text(value)


def coerce_text_list(value: Any) -> list[str]:
    return node_value_service.coerce_text_list(value)


def coerce_bool(value: Any) -> bool:
    return node_value_service.coerce_bool(value)


def coerce_int(value: Any, default: int) -> int:
    return node_value_service.coerce_int(value, default)


def coerce_float(value: Any, default: float) -> float:
    return node_value_service.coerce_float(value, default)


def parse_json_value(value: Any, label: str) -> Any:
    return node_value_service.parse_json_value(value, label)


def parse_json_if_possible(value: Any) -> Any:
    return node_value_service.parse_json_if_possible(value)


def coerce_json_object(value: Any) -> dict[str, Any]:
    return node_value_service.coerce_json_object(value)


def coerce_json_array(value: Any) -> list[Any]:
    return node_value_service.coerce_json_array(value)


def extract_top_level_json_fields(value: Any) -> dict[str, Any]:
    return node_value_service.extract_top_level_json_fields(value)


def merge_named_variables(*payloads: Any) -> dict[str, Any]:
    return node_value_service.merge_named_variables(*payloads)


def render_variable_value(value: Any) -> str:
    return node_value_service.render_variable_value(value)


def normalize_provider_name(provider: Any, default: str = "ollama") -> str:
    return node_value_service.normalize_provider_name(provider, default)


def strip_html(text: str) -> str:
    return node_value_service.strip_html(text)


def validate_schema_definition(schema: Any, path: str = "$") -> None:
    return json_schema_service.validate_schema_definition(schema, path)


def validate_json_against_schema(
    value: Any, schema: dict[str, Any], path: str = "$"
) -> None:
    return json_schema_service.validate_json_against_schema(value, schema, path)
