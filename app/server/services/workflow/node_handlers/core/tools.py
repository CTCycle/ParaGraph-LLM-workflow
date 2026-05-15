from __future__ import annotations

import ast
import importlib.util
import inspect
import json
from typing import Any, Callable

from pydantic import ValidationError

from server.domain.node_catalog import ProviderModelDefinition
from server.domain.node_handler_core import ToolCallParameters, ToolCollectionParameters
from server.domain.workflow_payloads import (
    ToolCallResult,
    ToolCallSelection,
    ToolCollectionHandle,
    ToolDefinition,
)
from server.services.workflow.node_handlers.common import validate_json_against_schema
from server.services.workflow.node_handlers.core.models import _execute_model_node
from server.services.workflow.node_handlers.ingestion import resolve_local_path
from server.services.workflow.provider import provider_service

_TOOL_CALLABLES: dict[str, Callable[..., Any]] = {}


def _json_type(annotation: Any) -> str:
    if annotation in {int}:
        return "integer"
    if annotation in {float}:
        return "number"
    if annotation in {bool}:
        return "boolean"
    if annotation in {dict}:
        return "object"
    if annotation in {list, tuple, set}:
        return "array"
    return "string"


def _schema_from_callable_signature(function: Callable[..., Any]) -> dict[str, Any]:
    signature = inspect.signature(function)
    properties: dict[str, Any] = {}
    required: list[str] = []
    for name, parameter in signature.parameters.items():
        if parameter.kind in {
            inspect.Parameter.VAR_KEYWORD,
            inspect.Parameter.VAR_POSITIONAL,
        }:
            continue
        properties[name] = {"type": _json_type(parameter.annotation)}
        if parameter.default is inspect.Parameter.empty:
            required.append(name)
    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


def _register_callable_tool(
    function: Callable[..., Any], source_type: str, source_ref: str = ""
) -> ToolDefinition:
    schema = _schema_from_callable_signature(function)
    name = function.__name__
    _TOOL_CALLABLES[name] = function
    return ToolDefinition(
        name=name,
        description=inspect.getdoc(function) or "",
        parameters_schema=schema,
        source_type=source_type,
        source_ref=source_ref,
        callable_name=name,
    )


def _safe_load_inline_tool_module(code: str) -> dict[str, Any]:
    tree = ast.parse(code)
    if any(not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Import, ast.ImportFrom)) for node in tree.body):
        raise ValueError("inline_python tools may contain only imports and function definitions")
    namespace: dict[str, Any] = {"__builtins__": __builtins__}
    exec(compile(tree, "<inline_tools>", "exec"), namespace)  # noqa: S102
    return namespace


def _parse_inline_python_tools(code: str) -> list[ToolDefinition]:
    namespace = _safe_load_inline_tool_module(code)
    return [
        _register_callable_tool(value, "inline_python")
        for name, value in namespace.items()
        if callable(value) and not name.startswith("_")
    ]


def _load_tool_module_from_file(file_path: str) -> dict[str, Any]:
    path = resolve_local_path(file_path)
    if path.suffix.lower() != ".py":
        raise ValueError("python_file tools require a .py file")
    spec = importlib.util.spec_from_file_location(f"paragraph_tool_{path.stem}", path)
    if spec is None or spec.loader is None:
        raise ValueError(f"Unable to load tool file: {file_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return vars(module)


def _parse_python_file_tools(file_path: str, entrypoint: str = "") -> list[ToolDefinition]:
    namespace = _load_tool_module_from_file(file_path)
    names = [entrypoint] if entrypoint else [
        name for name, value in namespace.items() if callable(value) and not name.startswith("_")
    ]
    return [
        _register_callable_tool(namespace[name], "python_file", source_ref=file_path)
        for name in names
        if callable(namespace.get(name))
    ]


def _parse_signature_tools(signature_text: str) -> list[ToolDefinition]:
    tools: list[ToolDefinition] = []
    for line in signature_text.splitlines():
        text = line.strip()
        if not text:
            continue
        node = ast.parse(f"def {text}: ...").body[0]
        if not isinstance(node, ast.FunctionDef):
            continue
        args = {}
        defaults = len(node.args.defaults)
        required_count = len(node.args.args) - defaults
        required: list[str] = []
        for index, arg in enumerate(node.args.args):
            args[arg.arg] = {"type": "string"}
            if index < required_count:
                required.append(arg.arg)
        tools.append(
            ToolDefinition(
                name=node.name,
                description="",
                parameters_schema={
                    "type": "object",
                    "properties": args,
                    "required": required,
                    "additionalProperties": False,
                },
                source_type="signature",
                callable_name=node.name,
            )
        )
    return tools


def _normalize_tool_schema(schema: dict[str, Any], tool_name: str = "", description: str = "") -> ToolDefinition:
    payload = schema.get("function") if isinstance(schema.get("function"), dict) else schema
    name = str(payload.get("name") or tool_name or "").strip()
    parameters = payload.get("parameters") or payload.get("parameters_schema") or schema
    if not name:
        raise ValueError("tool schema requires a name")
    if not isinstance(parameters, dict):
        raise ValueError("tool schema requires parameters JSON schema")
    return ToolDefinition(
        name=name,
        description=str(payload.get("description") or description or ""),
        parameters_schema=parameters,
        source_type="json_schema",
        callable_name=name,
    )


def _parse_json_schema_tools(schema: dict[str, Any], tool_name: str = "", description: str = "") -> list[ToolDefinition]:
    if isinstance(schema.get("tools"), list):
        return [_normalize_tool_schema(item, tool_name, description) for item in schema["tools"] if isinstance(item, dict)]
    return [_normalize_tool_schema(schema, tool_name, description)]


def _tool_collection_executor(
    parameters: dict[str, Any], inputs: dict[str, Any]
) -> dict[str, Any]:
    parsed = ToolCollectionParameters.model_validate(parameters)
    if parsed.source_type == "inline_python":
        tools = _parse_inline_python_tools(str(inputs.get("code") or parsed.inline_code))
    elif parsed.source_type == "python_file":
        tools = _parse_python_file_tools(parsed.file_path, parsed.entrypoint)
    elif parsed.source_type == "signature":
        tools = _parse_signature_tools(parsed.signature_text)
    else:
        schema = (
            inputs.get("schema")
            if isinstance(inputs.get("schema"), dict)
            else parsed.schema_definition
        )
        tools = _parse_json_schema_tools(schema, parsed.tool_name, parsed.description)
    if not tools:
        raise ValueError("TOOL_COLLECTION did not find any tools")
    handle = ToolCollectionHandle(tools=tools)
    return {"tools": handle.model_dump(mode="json")}


def _build_tool_choice_schema(tools: list[ToolDefinition]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "tool_name": {"type": "string", "enum": [tool.name for tool in tools]},
            "arguments": {"type": "object", "additionalProperties": True},
        },
        "required": ["tool_name", "arguments"],
        "additionalProperties": False,
    }


def _validate_tool_arguments(tool: ToolDefinition, arguments: dict[str, Any]) -> None:
    validate_json_against_schema(arguments, tool.parameters_schema)


def _execute_selected_tool(selection: ToolCallSelection) -> Any:
    function = _TOOL_CALLABLES.get(selection.tool_name)
    if function is None:
        return None
    return function(**selection.arguments)


def _select_tool_with_structured_model(
    *, selection: ProviderModelDefinition, tools: list[ToolDefinition], parameters: dict[str, Any], inputs: dict[str, Any]
) -> ToolCallSelection:
    instruction = str(inputs.get("instruction") or parameters.get("instruction") or "").strip()
    prompt = (
        f"{instruction}\n\nAvailable tools:\n"
        f"{json.dumps([tool.model_dump(mode='json') for tool in tools], sort_keys=True)}"
    )
    result = _execute_model_node(
        provider=selection.provider,
        model_name=selection.model,
        parameters={**parameters, "prompt": prompt, "response_schema": _build_tool_choice_schema(tools)},
        inputs={"model": selection.model_dump(mode="json"), "user_prompt": prompt},
        structured_output=True,
        timeout_s=selection.timeout_s,
    )["result"]
    return ToolCallSelection.model_validate({**result, "raw_model_response": result})


def _select_tool_with_native_provider_tools(
    *, selection: ProviderModelDefinition, tools: list[ToolDefinition], parameters: dict[str, Any], inputs: dict[str, Any]
) -> ToolCallSelection:
    response = provider_service.chat_with_tools(
        provider=selection.provider,
        model=selection.model,
        messages=[{"role": "user", "content": str(inputs.get("instruction") or parameters.get("instruction") or "")}],
        tools=[tool.model_dump(mode="json") for tool in tools],
        tool_choice=str(parameters.get("tool_choice") or "auto"),
        options={"max_output_tokens": int(parameters.get("max_tokens") or 512)},
        timeout_s=selection.timeout_s,
    )
    return ToolCallSelection.model_validate(response)


def _tool_call_executor(
    parameters: dict[str, Any], inputs: dict[str, Any]
) -> dict[str, Any]:
    parsed = ToolCallParameters.model_validate(parameters)
    try:
        model = ProviderModelDefinition.model_validate(inputs.get("model"))
        tools_handle = ToolCollectionHandle.model_validate(inputs.get("tools"))
    except ValidationError as exc:
        raise ValueError("TOOL_CALL requires model and tools controllers") from exc

    native_supported = provider_service.supports_native_tools(model.provider, model.model)
    if parsed.provider_tool_mode == "native" and not native_supported:
        raise ValueError(f"Provider '{model.provider}' does not support native tool calling")
    use_native = native_supported and parsed.provider_tool_mode in {"auto", "native"}
    selection = (
        _select_tool_with_native_provider_tools(
            selection=model, tools=tools_handle.tools, parameters=parameters, inputs=inputs
        )
        if use_native
        else _select_tool_with_structured_model(
            selection=model, tools=tools_handle.tools, parameters=parameters, inputs=inputs
        )
    )
    tool = next((item for item in tools_handle.tools if item.name == selection.tool_name), None)
    if tool is None:
        raise ValueError(f"Model selected unknown tool: {selection.tool_name}")
    _validate_tool_arguments(tool, selection.arguments)
    result = _execute_selected_tool(selection) if parsed.execute_tool else None
    output = ToolCallResult(
        tool_name=selection.tool_name,
        arguments=selection.arguments,
        result=result,
        raw_model_response=selection.raw_model_response,
        metadata={"executed": parsed.execute_tool, "mode": "native" if use_native else "structured_json"},
    ).model_dump(mode="json")
    return {"result": output, "json": output}


__all__ = [
    "_tool_call_executor",
    "_tool_collection_executor",
    "_parse_inline_python_tools",
    "_parse_json_schema_tools",
    "_parse_python_file_tools",
    "_parse_signature_tools",
]
