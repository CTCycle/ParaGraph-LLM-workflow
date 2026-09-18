from __future__ import annotations

from contextvars import ContextVar, Token
from typing import Any


_EXECUTION_CONTEXT_VAR: ContextVar[dict[str, Any]] = ContextVar(
    "paragraph_node_execution_context",
    default={
        "workflow_id": "",
        "run_id": "",
        "execution_session_id": "",
        "node_id": "",
    },
)

###############################################################################
def get_execution_context() -> dict[str, Any]:
    return dict(_EXECUTION_CONTEXT_VAR.get())

###############################################################################
def set_execution_context(context: dict[str, Any]) -> Token[dict[str, Any]]:
    normalized_context = {
        "workflow_id": str(context.get("workflow_id") or ""),
        "run_id": str(context.get("run_id") or ""),
        "execution_session_id": str(context.get("execution_session_id") or ""),
        "node_id": str(context.get("node_id") or ""),
    }
    for key in ("cancelled", "deadline_monotonic"):
        if key in context:
            normalized_context[key] = context[key]
    return _EXECUTION_CONTEXT_VAR.set(normalized_context)

###############################################################################
def reset_execution_context(token: Token[dict[str, Any]]) -> None:
    _EXECUTION_CONTEXT_VAR.reset(token)
