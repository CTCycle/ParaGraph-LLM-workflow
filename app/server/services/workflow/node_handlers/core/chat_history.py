from __future__ import annotations

from typing import Any, cast

from server.contracts.chat_history import (
    ChatHistoryHandle,
    ChatHistoryStorageBackend,
    DEFAULT_CHAT_HISTORY_STORAGE_BACKEND,
)
from server.contracts.node_handler_core import ChatInputParameters
from server.services.workflow.nodes.execution_context import (
    get_execution_context,
)


###############################################################################
def _resolve_context_identifiers() -> tuple[str, str]:
    context = get_execution_context()
    workflow_id = (context.get("workflow_id") or "").strip() or "workflow"
    execution_session_id = (context.get("execution_session_id") or "").strip() or (
        context.get("run_id") or ""
    ).strip()
    if not execution_session_id:
        raise ValueError(
            "CHAT_HISTORY nodes require an execution_session_id in execution context"
        )
    return workflow_id, execution_session_id


###############################################################################
def execute_chat_history_memory(
    parameters: dict[str, Any], inputs: dict[str, Any]
) -> dict[str, Any]:
    _ = inputs
    context = get_execution_context()
    workflow_id, execution_session_id = _resolve_context_identifiers()
    node_id = (context.get("node_id") or "").strip() or "node"
    handle = ChatHistoryHandle(
        node_type="CHAT_HISTORY_MEMORY",
        workflow_id=workflow_id,
        execution_session_id=execution_session_id,
        node_id=node_id,
        max_messages=int(parameters.get("max_messages", 20)),
        separator=str(parameters.get("separator", "\n")),
        keep_prompt_type=bool(parameters.get("keep_prompt_type", True)),
        storage_backend=None,
    )
    return {"history": handle.model_dump(mode="json")}


###############################################################################
def execute_chat_history_persisted(
    parameters: dict[str, Any], inputs: dict[str, Any]
) -> dict[str, Any]:
    _ = inputs
    context = get_execution_context()
    workflow_id, execution_session_id = _resolve_context_identifiers()
    node_id = (context.get("node_id") or "").strip() or "node"
    backend = cast(
        ChatHistoryStorageBackend,
        str(parameters.get("storage_backend", DEFAULT_CHAT_HISTORY_STORAGE_BACKEND))
        .strip()
        .lower(),
    )
    handle = ChatHistoryHandle(
        node_type="CHAT_HISTORY_PERSISTED",
        workflow_id=workflow_id,
        execution_session_id=execution_session_id,
        node_id=node_id,
        max_messages=int(parameters.get("max_messages", 20)),
        separator=str(parameters.get("separator", "\n")),
        keep_prompt_type=bool(parameters.get("keep_prompt_type", True)),
        storage_backend=backend,
    )
    return {"history": handle.model_dump(mode="json")}


###############################################################################
def execute_chat_input(
    parameters: dict[str, Any], inputs: dict[str, Any]
) -> dict[str, Any]:
    parsed = ChatInputParameters.model_validate(parameters)
    message = parsed.message.strip()
    if not message:
        raise ValueError("CHAT_INPUT requires a non-empty message")

    context = get_execution_context()
    workflow_id, execution_session_id = _resolve_context_identifiers()
    node_id = (context.get("node_id") or "").strip() or "node"
    history_input = inputs.get("history")
    try:
        history_handle = ChatHistoryHandle.model_validate(history_input)
    except Exception as exc:  # noqa: BLE001
        raise ValueError(
            "CHAT_INPUT requires a valid connected chat history controller"
        ) from exc

    scoped_handle = history_handle.model_copy(
        update={
            "workflow_id": workflow_id,
            "execution_session_id": execution_session_id,
            "node_id": node_id,
            "execution_owned": True,
        }
    )
    return {
        "text": message,
        "history": scoped_handle.model_dump(mode="json"),
    }
