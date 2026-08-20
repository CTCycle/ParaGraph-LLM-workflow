from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from server.contracts.chat_history import ChatHistoryHandle
from server.contracts.node_catalog import ProviderModelDefinition
from server.repositories.workflow import (
    database_chat_history_repository,
    file_chat_history_repository,
    in_memory_chat_history_repository,
)
from server.services.workflow import node_registry, provider_service

###############################################################################
def _model_handle() -> dict[str, Any]:
    return ProviderModelDefinition(
        provider="ollama",
        model="llama3.2",
        label="ollama:llama3.2",
        supports_image=False,
        supports_embeddings=False,
        supports_reasoning=False,
        supports_structured_output=True,
        timeout_s=30.0,
    ).model_dump(mode="json")

###############################################################################
def _history_context(
    *, workflow_id: str, session_id: str, run_id: str, node_id: str
) -> dict[str, str]:
    return {
        "workflow_id": workflow_id,
        "execution_session_id": session_id,
        "run_id": run_id,
        "node_id": node_id,
    }

###############################################################################
def _build_history_handle(
    *,
    node_type: str,
    parameters: dict[str, Any],
    context: dict[str, str],
) -> ChatHistoryHandle:
    payload = node_registry.execute(
        node_type,
        1,
        parameters,
        {},
        context=context,
    )
    return ChatHistoryHandle.model_validate(payload["history"])

###############################################################################
def test_in_memory_history_reuses_same_session_and_isolates_different_sessions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[list[dict[str, Any]]] = []

    monkeypatch.setattr(
        provider_service, "validate_model_request", lambda **kwargs: None
    )

    def _chat(**kwargs: Any) -> str:
        calls.append(kwargs["messages"])
        return f"reply-{len(calls)}"

    monkeypatch.setattr(provider_service, "chat", _chat)

    params = {"max_messages": 4, "separator": "\n", "keep_prompt_type": True}
    handle_s1 = _build_history_handle(
        node_type="CHAT_HISTORY_MEMORY",
        parameters=params,
        context=_history_context(
            workflow_id="wf-memory",
            session_id="session-1",
            run_id="run-1",
            node_id="history_node",
        ),
    )

    node_registry.execute(
        "LLM_CHAT",
        1,
        {"context_window": 0, "max_tokens": 32, "use_reasoning": False},
        {"user_prompt": "hello"},
        {"model": _model_handle(), "history": handle_s1.model_dump(mode="json")},
    )
    node_registry.execute(
        "LLM_CHAT",
        1,
        {"context_window": 0, "max_tokens": 32, "use_reasoning": False},
        {"user_prompt": "again"},
        {"model": _model_handle(), "history": handle_s1.model_dump(mode="json")},
    )

    assert len(calls) == 2
    history_message = calls[1][0]
    assert history_message["role"] == "system"
    assert "user: hello" in str(history_message["content"])
    assert "assistant: reply-1" in str(history_message["content"])

    handle_s2 = _build_history_handle(
        node_type="CHAT_HISTORY_MEMORY",
        parameters=params,
        context=_history_context(
            workflow_id="wf-memory",
            session_id="session-2",
            run_id="run-2",
            node_id="history_node",
        ),
    )
    node_registry.execute(
        "LLM_CHAT",
        1,
        {"context_window": 0, "max_tokens": 32, "use_reasoning": False},
        {"user_prompt": "fresh"},
        {"model": _model_handle(), "history": handle_s2.model_dump(mode="json")},
    )

    assert len(calls) == 3
    assert "user: hello" not in json.dumps(calls[2])

###############################################################################
def test_in_memory_history_trims_max_messages_and_keeps_labels(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        provider_service, "validate_model_request", lambda **kwargs: None
    )
    monkeypatch.setattr(provider_service, "chat", lambda **kwargs: "fixed-reply")

    handle = _build_history_handle(
        node_type="CHAT_HISTORY_MEMORY",
        parameters={"max_messages": 2, "separator": "\n", "keep_prompt_type": True},
        context=_history_context(
            workflow_id="wf-trim",
            session_id="trim-session",
            run_id="run-trim",
            node_id="history_node",
        ),
    )

    node_registry.execute(
        "LLM_CHAT",
        1,
        {"context_window": 0, "max_tokens": 16, "use_reasoning": False},
        {"user_prompt": "first"},
        {"model": _model_handle(), "history": handle.model_dump(mode="json")},
    )
    node_registry.execute(
        "LLM_CHAT",
        1,
        {"context_window": 0, "max_tokens": 16, "use_reasoning": False},
        {"user_prompt": "second"},
        {"model": _model_handle(), "history": handle.model_dump(mode="json")},
    )

    messages = in_memory_chat_history_repository.get_messages(
        "wf-trim", "trim-session", "history_node"
    )
    assert len(messages) == 2
    assert messages[0].role == "user"
    assert messages[0].content == "second"
    assert messages[1].role == "assistant"
    assert messages[1].content == "fixed-reply"

###############################################################################
def test_file_persisted_history_saves_reloads_and_trims(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        provider_service, "validate_model_request", lambda **kwargs: None
    )
    monkeypatch.setattr(provider_service, "chat", lambda **kwargs: "file-reply")

    handle = _build_history_handle(
        node_type="CHAT_HISTORY_PERSISTED",
        parameters={
            "max_messages": 2,
            "separator": "\n",
            "keep_prompt_type": True,
            "storage_backend": "file",
        },
        context=_history_context(
            workflow_id="wf-file",
            session_id="file-session",
            run_id="run-file",
            node_id="history_file_node",
        ),
    )

    node_registry.execute(
        "LLM_CHAT",
        1,
        {"context_window": 0, "max_tokens": 16, "use_reasoning": False},
        {"user_prompt": "first"},
        {"model": _model_handle(), "history": handle.model_dump(mode="json")},
    )
    node_registry.execute(
        "LLM_CHAT",
        1,
        {"context_window": 0, "max_tokens": 16, "use_reasoning": False},
        {"user_prompt": "second"},
        {"model": _model_handle(), "history": handle.model_dump(mode="json")},
    )

    messages = file_chat_history_repository.get_messages(
        "wf-file", "file-session", "history_file_node"
    )
    assert len(messages) == 2
    assert messages[0].content == "second"
    assert messages[1].content == "file-reply"

    root = Path(getattr(file_chat_history_repository, "_root"))
    expected_file = root / "wf-file" / "file-session" / "history_file_node.json"
    assert expected_file.exists()

###############################################################################
def test_database_persisted_history_saves_reloads_and_trims(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        provider_service, "validate_model_request", lambda **kwargs: None
    )
    monkeypatch.setattr(provider_service, "chat", lambda **kwargs: "db-reply")

    handle = _build_history_handle(
        node_type="CHAT_HISTORY_PERSISTED",
        parameters={
            "max_messages": 2,
            "separator": "\n",
            "keep_prompt_type": True,
            "storage_backend": "database",
        },
        context=_history_context(
            workflow_id="wf-db",
            session_id="db-session",
            run_id="run-db",
            node_id="history_db_node",
        ),
    )

    node_registry.execute(
        "LLM_CHAT",
        1,
        {"context_window": 0, "max_tokens": 16, "use_reasoning": False},
        {"user_prompt": "first"},
        {"model": _model_handle(), "history": handle.model_dump(mode="json")},
    )
    node_registry.execute(
        "LLM_CHAT",
        1,
        {"context_window": 0, "max_tokens": 16, "use_reasoning": False},
        {"user_prompt": "second"},
        {"model": _model_handle(), "history": handle.model_dump(mode="json")},
    )

    messages = database_chat_history_repository.get_messages(
        "wf-db", "db-session", "history_db_node"
    )
    assert len(messages) == 2
    assert messages[0].content == "second"
    assert messages[1].content == "db-reply"

###############################################################################
def test_llm_structured_uses_history_and_serializes_assistant_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        provider_service, "validate_model_request", lambda **kwargs: None
    )
    monkeypatch.setattr(provider_service, "chat", lambda **kwargs: '{"value":7}')

    handle = _build_history_handle(
        node_type="CHAT_HISTORY_MEMORY",
        parameters={"max_messages": 10, "separator": "\n", "keep_prompt_type": False},
        context=_history_context(
            workflow_id="wf-structured",
            session_id="structured-session",
            run_id="run-structured",
            node_id="history_structured_node",
        ),
    )

    payload = node_registry.execute(
        "LLM_STRUCTURED",
        1,
        {
            "context_window": 0,
            "max_tokens": 16,
            "use_reasoning": False,
            "response_schema": {
                "type": "object",
                "properties": {"value": {"type": "integer"}},
                "required": ["value"],
            },
        },
        {
            "user_prompt": "give json",
        },
        {"model": _model_handle(), "history": handle.model_dump(mode="json")},
    )

    assert payload["result"] == {"value": 7}
    messages = in_memory_chat_history_repository.get_messages(
        "wf-structured", "structured-session", "history_structured_node"
    )
    assert messages[-1].content == '{"value":7}'

###############################################################################
def test_failed_llm_execution_does_not_append_history(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        provider_service, "validate_model_request", lambda **kwargs: None
    )
    monkeypatch.setattr(provider_service, "chat", lambda **kwargs: "ok")

    handle = _build_history_handle(
        node_type="CHAT_HISTORY_MEMORY",
        parameters={"max_messages": 10, "separator": "\n", "keep_prompt_type": True},
        context=_history_context(
            workflow_id="wf-fail",
            session_id="fail-session",
            run_id="run-fail",
            node_id="history_fail_node",
        ),
    )

    node_registry.execute(
        "LLM_CHAT",
        1,
        {"context_window": 0, "max_tokens": 16, "use_reasoning": False},
        {"user_prompt": "before fail"},
        {"model": _model_handle(), "history": handle.model_dump(mode="json")},
    )
    baseline = in_memory_chat_history_repository.get_messages(
        "wf-fail", "fail-session", "history_fail_node"
    )

    monkeypatch.setattr(
        provider_service,
        "chat",
        lambda **kwargs: (_ for _ in ()).throw(ValueError("boom")),
    )

    with pytest.raises(ValueError, match="boom"):
        node_registry.execute(
            "LLM_CHAT",
            1,
            {"context_window": 0, "max_tokens": 16, "use_reasoning": False},
            {"user_prompt": "should fail"},
            {"model": _model_handle(), "history": handle.model_dump(mode="json")},
        )

    after_failure = in_memory_chat_history_repository.get_messages(
        "wf-fail", "fail-session", "history_fail_node"
    )
    assert [item.model_dump(mode="json") for item in after_failure] == [
        item.model_dump(mode="json") for item in baseline
    ]
