from __future__ import annotations

import pytest

from server.domain.node_catalog import ProviderModelDefinition
from server.domain.workflow_payloads import ToolCallSelection, ToolCollectionHandle
from server.services.workflow.node_handlers.core import tools as tools_module
from server.services.workflow.nodes import node_registry
from server.services.workflow.provider import provider_service

###############################################################################
def _model() -> dict[str, object]:
    return ProviderModelDefinition(
        provider="openai",
        model="test-model",
        label="test-model",
    ).model_dump(mode="json")

###############################################################################
def _build_collection(code: str, run_id: str) -> ToolCollectionHandle:
    result = node_registry.execute(
        "TOOL_COLLECTION",
        1,
        {"source_type": "inline_python", "inline_code": code},
        {},
        context={"run_id": run_id},
    )
    return ToolCollectionHandle.model_validate(result["tools"])

###############################################################################
def _call_tool(
    handle: ToolCollectionHandle, run_id: str
) -> dict[str, object]:
    result = node_registry.execute(
        "TOOL_CALL",
        1,
        {"provider_tool_mode": "auto", "execute_tool": True},
        {},
        {"model": _model(), "tools": handle.model_dump(mode="json")},
        context={"run_id": run_id},
    )
    return result["result"]

###############################################################################
def test_identically_named_tools_are_scoped_to_their_run(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        tools_module,
        "_select_tool_with_structured_model",
        lambda **_: ToolCallSelection(
            tool_name="lookup", arguments={"value": "item"}
        ),
    )
    run_a = "tool-run-a"
    run_b = "tool-run-b"
    handle_a = _build_collection(
        "def lookup(value: str):\n    return 'a:' + value\n", run_a
    )
    handle_b = _build_collection(
        "def lookup(value: str):\n    return 'b:' + value\n", run_b
    )

    try:
        result_a = _call_tool(handle_a, run_a)
        result_b = _call_tool(handle_b, run_b)
    finally:
        tools_module.release_run_tool_resources(run_a)
        tools_module.release_run_tool_resources(run_b)

    assert result_a["result"] == "a:item"
    assert result_b["result"] == "b:item"
    assert result_a["metadata"] == {
        "executed": True,
        "execution_state": "executable",
        "mode": "prompt_emulated",
    }

###############################################################################
def test_async_tool_is_awaited(monkeypatch) -> None:
    monkeypatch.setattr(
        tools_module,
        "_select_tool_with_structured_model",
        lambda **_: ToolCallSelection(
            tool_name="lookup", arguments={"value": "item"}
        ),
    )
    run_id = "async-tool-run"
    handle = _build_collection(
        "async def lookup(value: str):\n    return 'async:' + value\n", run_id
    )

    try:
        result = _call_tool(handle, run_id)
    finally:
        tools_module.release_run_tool_resources(run_id)

    assert result["result"] == "async:item"
    assert result["metadata"]["executed"] is True

###############################################################################
def test_schema_only_tool_cannot_be_executed(monkeypatch) -> None:
    monkeypatch.setattr(
        tools_module,
        "_select_tool_with_structured_model",
        lambda **_: ToolCallSelection(
            tool_name="lookup", arguments={"value": "item"}
        ),
    )
    run_id = "schema-tool-run"
    collection = node_registry.execute(
        "TOOL_COLLECTION",
        1,
        {
            "source_type": "json_schema",
            "schema_json": {
                "name": "lookup",
                "parameters": {
                    "type": "object",
                    "properties": {"value": {"type": "string"}},
                    "required": ["value"],
                },
            },
        },
        {},
        context={"run_id": run_id},
    )
    handle = ToolCollectionHandle.model_validate(collection["tools"])

    try:
        with pytest.raises(ValueError, match="schema_only"):
            _call_tool(handle, run_id)
    finally:
        tools_module.release_run_tool_resources(run_id)

###############################################################################
def test_provider_tool_capabilities_distinguish_selection_from_native_protocol() -> None:
    assert provider_service.supports_tool_selection("openai") is True
    assert provider_service.supports_native_tool_protocol("openai") is False
    assert provider_service.supports_native_tools("openai") is False
