from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "app/client/src/workflow/schema/apiTypes.generated.ts"
IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_$][A-Za-z0-9_$]*$")


###############################################################################
def _load_openapi_schemas() -> dict[str, dict[str, Any]]:
    sys.path.insert(0, str(ROOT / "app"))
    from server.app import app

    schemas = app.openapi().get("components", {}).get("schemas", {})
    if not isinstance(schemas, dict):
        raise RuntimeError("FastAPI OpenAPI document has no component schemas.")
    return schemas


###############################################################################
def _ref_name(reference: str) -> str:
    return reference.rsplit("/", 1)[-1]


###############################################################################
def _literal(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


###############################################################################
def _schema_type(schema: dict[str, Any]) -> str:
    if "$ref" in schema:
        return _ref_name(str(schema["$ref"]))

    if "const" in schema:
        return _literal(schema["const"])

    if "enum" in schema:
        values = schema["enum"]
        if isinstance(values, list) and values:
            return " | ".join(_literal(value) for value in values)

    for key in ("anyOf", "oneOf"):
        variants = schema.get(key)
        if isinstance(variants, list):
            types = [_schema_type(item) for item in variants if isinstance(item, dict)]
            unique_types = list(dict.fromkeys(types))
            if unique_types:
                return " | ".join(unique_types)

    all_of = schema.get("allOf")
    if isinstance(all_of, list):
        types = [_schema_type(item) for item in all_of if isinstance(item, dict)]
        if types:
            return " & ".join(types)

    schema_type = schema.get("type")
    if schema_type == "array":
        items = schema.get("items")
        item_type = _schema_type(items) if isinstance(items, dict) else "unknown"
        if " | " in item_type or " & " in item_type:
            item_type = f"({item_type})"
        return f"{item_type}[]"
    if schema_type == "object":
        properties = schema.get("properties")
        if isinstance(properties, dict) and properties:
            return _inline_object_type(schema)
        additional_properties = schema.get("additionalProperties")
        if isinstance(additional_properties, dict):
            return f"Record<string, {_schema_type(additional_properties)}>"
        return "Record<string, unknown>"
    if schema_type in {"integer", "number"}:
        return "number"
    if schema_type == "boolean":
        return "boolean"
    if schema_type == "string":
        return "string"
    if schema_type == "null":
        return "null"
    return "unknown"


###############################################################################
def _property_name(name: str) -> str:
    return name if IDENTIFIER_PATTERN.fullmatch(name) else _literal(name)


###############################################################################
def _is_optional_property(name: str, property_schema: dict[str, Any], required: set[str]) -> bool:
    if name in required or "default" in property_schema:
        return False
    variants = property_schema.get("anyOf")
    return isinstance(variants, list) and any(
        isinstance(variant, dict) and variant.get("type") == "null"
        for variant in variants
    )


###############################################################################
def _inline_object_type(schema: dict[str, Any]) -> str:
    properties = schema.get("properties", {})
    required = set(schema.get("required", []))
    lines = ["{\n"]
    for name, property_schema in properties.items():
        if not isinstance(property_schema, dict):
            continue
        optional = "?" if _is_optional_property(str(name), property_schema, required) else ""
        lines.append(
            f"        {_property_name(str(name))}{optional}: {_schema_type(property_schema)};\n"
        )
    lines.append("    }")
    return "".join(lines)


###############################################################################
def _render_schema(name: str, schema: dict[str, Any]) -> list[str]:
    if schema.get("type") == "object" and isinstance(schema.get("properties"), dict):
        required = set(schema.get("required", []))
        lines = [f"export interface {name} {{"]
        for property_name, property_schema in schema["properties"].items():
            if not isinstance(property_schema, dict):
                continue
            optional = "?" if _is_optional_property(str(property_name), property_schema, required) else ""
            lines.append(
                f"    {_property_name(str(property_name))}{optional}: {_schema_type(property_schema)}"
            )
        lines.append("}")
        return lines
    return [f"export type {name} = {_schema_type(schema)}"]


###############################################################################
def render_contracts(schemas: dict[str, dict[str, Any]]) -> str:
    lines = [
        "// This file is generated from the FastAPI OpenAPI component schemas.",
        "// Do not edit it manually. Run app/scripts/generate_frontend_api_contracts.py.",
        "",
    ]
    for name, schema in schemas.items():
        lines.extend(_render_schema(name, schema))
        lines.append("")
    return "\n".join(lines)


###############################################################################
def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    expected = render_contracts(_load_openapi_schemas())
    if args.check:
        actual = OUTPUT.read_text(encoding="utf-8") if OUTPUT.exists() else None
        if actual != expected:
            print(f"Generated frontend API contracts are stale: {OUTPUT}", file=sys.stderr)
            return 1
        return 0

    OUTPUT.write_text(expected, encoding="utf-8", newline="\n")
    print(f"Generated {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
