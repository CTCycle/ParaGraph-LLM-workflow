from __future__ import annotations

import ast
from typing import Any, Literal, Optional

from pydantic import BaseModel, ValidationError, create_model


_SCALARS: dict[str, Any] = {
    "str": str,
    "int": int,
    "float": float,
    "bool": bool,
    "dict": dict,
    "list": list,
    "Any": Any,
    "Optional": Optional,
    "Literal": Literal,
}

###############################################################################
def infer_model_from_json(name: str, value: dict[str, Any]) -> type[BaseModel]:
    fields: dict[str, tuple[Any, Any]] = {}
    for key, item in value.items():
        annotation: Any
        if isinstance(item, bool):
            annotation = bool
        elif isinstance(item, int):
            annotation = int
        elif isinstance(item, float):
            annotation = float
        elif isinstance(item, str):
            annotation = str
        elif isinstance(item, list):
            annotation = list
        elif isinstance(item, dict):
            annotation = dict
        elif item is None:
            annotation = Any
        else:
            annotation = type(item)
        fields[str(key)] = (annotation, ...)
    return create_model(name, **fields)

###############################################################################
def model_to_json_schema(model: type[BaseModel]) -> dict[str, Any]:
    return model.model_json_schema()

###############################################################################
def _annotation_to_type(node: ast.AST, *, field: str) -> Any:
    if isinstance(node, ast.Name):
        if node.id in _SCALARS:
            return _SCALARS[node.id]
        raise ValueError(
            {"code": "unsupported_annotation", "field": field, "annotation": node.id}
        )
    if isinstance(node, ast.Constant) and node.value is None:
        return type(None)
    if isinstance(node, ast.Subscript):
        base = _annotation_to_type(node.value, field=field)
        args_node = node.slice
        args = list(args_node.elts) if isinstance(args_node, ast.Tuple) else [args_node]
        parsed_args = tuple(_annotation_to_type(arg, field=field) for arg in args)
        if base is list and len(parsed_args) == 1:
            return list[parsed_args[0]]
        if base is dict and parsed_args == (str, Any):
            return dict[str, Any]
        if getattr(base, "__name__", "") == "Optional" and len(parsed_args) == 1:
            return Optional[parsed_args[0]]
        if getattr(base, "__name__", "") == "Literal":
            literal_values = []
            for arg in args:
                if not isinstance(arg, ast.Constant):
                    raise ValueError(
                        {
                            "code": "unsupported_annotation",
                            "field": field,
                            "annotation": ast.unparse(node),
                        }
                    )
                literal_values.append(arg.value)
            return Literal.__getitem__(tuple(literal_values))
    raise ValueError(
        {
            "code": "unsupported_annotation",
            "field": field,
            "annotation": ast.unparse(node),
        }
    )

###############################################################################
def parse_user_pydantic_model(model_source: str) -> type[BaseModel]:
    tree = ast.parse(model_source)
    class_node = next(
        (node for node in tree.body if isinstance(node, ast.ClassDef)),
        None,
    )
    if class_node is None:
        raise ValueError("model_source must define a Pydantic model class")
    fields: dict[str, tuple[Any, Any]] = {}
    for item in class_node.body:
        if not isinstance(item, ast.AnnAssign) or not isinstance(item.target, ast.Name):
            continue
        field_name = item.target.id
        annotation = _annotation_to_type(item.annotation, field=field_name)
        default: Any = ...
        if item.value is not None:
            default = ast.literal_eval(item.value)
        fields[field_name] = (annotation, default)
    if not fields:
        raise ValueError("model_source must define at least one annotated field")
    return create_model(class_node.name, **fields)

###############################################################################
def validate_json_with_model(value: Any, model: type[BaseModel]) -> dict[str, Any]:
    instance = model.model_validate(value)
    return instance.model_dump(mode="json")

###############################################################################
def validation_error_payload(error: ValidationError) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    for issue in error.errors():
        loc = ".".join(str(part) for part in issue.get("loc", ()))
        errors.append(
            {
                "field": loc,
                "message": issue.get("msg", "Invalid value"),
                "expected": issue.get("type"),
                "received": issue.get("input"),
            }
        )
    return {"valid": False, "errors": errors}
