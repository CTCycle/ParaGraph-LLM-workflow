from __future__ import annotations

from contextvars import ContextVar, Token


_EXECUTION_CONTEXT_VAR: ContextVar[dict[str, str]] = ContextVar(
    "paragraph_node_execution_context",
    default={
        "workflow_id": "",
        "run_id": "",
        "execution_session_id": "",
        "node_id": "",
    },
)


def get_execution_context() -> dict[str, str]:
    return dict(_EXECUTION_CONTEXT_VAR.get())


def set_execution_context(context: dict[str, str]) -> Token[dict[str, str]]:
    normalized_context = {
        "workflow_id": str(context.get("workflow_id") or ""),
        "run_id": str(context.get("run_id") or ""),
        "execution_session_id": str(context.get("execution_session_id") or ""),
        "node_id": str(context.get("node_id") or ""),
    }
    return _EXECUTION_CONTEXT_VAR.set(normalized_context)


def reset_execution_context(token: Token[dict[str, str]]) -> None:
    _EXECUTION_CONTEXT_VAR.reset(token)
