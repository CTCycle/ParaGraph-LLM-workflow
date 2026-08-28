from __future__ import annotations

from typing import Any

import pytest

from server.contracts.execution import (
    CompiledExecutionPlan,
    ExecutionBinding,
    ExecutionStepPlan,
)
from server.repositories.workflow import in_memory_chat_history_repository
from server.services.jobs import job_manager
from server.services.workflow import node_registry
from server.services.workflow.execution import execution_service

###############################################################################
def _chat_plan() -> CompiledExecutionPlan:
    return CompiledExecutionPlan(
        plan_id="chat-execution-plan",
        step_order=["memory", "chat", "output"],
        steps=[
            ExecutionStepPlan(
                step_id="memory",
                node_id="memory",
                node_type="CHAT_HISTORY_MEMORY",
                node_version=1,
                category="memory",
                executor_key="chat_history_memory",
                parameters={
                    "max_messages": 10,
                    "separator": "\n",
                    "keep_prompt_type": True,
                },
                bindings=[],
                cacheable=False,
            ),
            ExecutionStepPlan(
                step_id="chat",
                node_id="chat",
                node_type="CHAT_INPUT",
                node_version=1,
                category="input",
                executor_key="chat_input",
                parameters={"message": "hello"},
                bindings=[
                    ExecutionBinding(
                        binding_type="controller",
                        input_name="history",
                        source_node_id="memory",
                        source_output="history",
                    )
                ],
                cacheable=False,
            ),
            ExecutionStepPlan(
                step_id="output",
                node_id="output",
                node_type="TEXT_OUTPUT",
                node_version=1,
                category="output",
                executor_key="text_output",
                parameters={},
                bindings=[
                    ExecutionBinding(
                        input_name="text",
                        source_node_id="chat",
                        source_output="text",
                    )
                ],
                cacheable=False,
            ),
        ],
        metadata={"chat_terminal_outputs": {"chat": "output"}},
    )

###############################################################################
def test_successful_chat_execution_persists_user_and_terminal_output(
    job_state_factory,
) -> None:
    job_state_factory("chat-success", "workflow")

    result = execution_service.execute_plan_job(
        _chat_plan(),
        workflow_id="chat-workflow",
        job_id="chat-success",
        execution_session_id="chat-session",
    )

    assert result == {"outputs": {"output": {"text": "hello"}}}
    messages = in_memory_chat_history_repository.get_messages(
        "chat-workflow", "chat-session", "chat"
    )
    assert [(item.role, item.content) for item in messages] == [
        ("user", "hello"),
        ("assistant", "hello"),
    ]

###############################################################################
def test_failed_chat_execution_does_not_persist_history(
    job_state_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    original_execute = node_registry.execute

    def fail_terminal_output(
        node_type: str,
        node_version: int,
        parameters: dict[str, Any],
        inputs: dict[str, Any],
        controllers: dict[str, Any] | None = None,
        context: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        if node_type == "TEXT_OUTPUT":
            raise ValueError("terminal failure")
        return original_execute(
            node_type,
            node_version,
            parameters,
            inputs,
            controllers,
            context=context,
        )

    monkeypatch.setattr(node_registry, "execute", fail_terminal_output)
    job_state_factory("chat-failed", "workflow")

    with pytest.raises(ValueError, match="terminal failure"):
        execution_service.execute_plan_job(
            _chat_plan(),
            workflow_id="chat-workflow",
            job_id="chat-failed",
            execution_session_id="chat-session-failed",
        )

    assert in_memory_chat_history_repository.get_messages(
        "chat-workflow", "chat-session-failed", "chat"
    ) == []

###############################################################################
def test_cancelled_chat_execution_does_not_persist_history(
    job_state_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    original_execute = node_registry.execute

    def cancel_after_chat(
        node_type: str,
        node_version: int,
        parameters: dict[str, Any],
        inputs: dict[str, Any],
        controllers: dict[str, Any] | None = None,
        context: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        result = original_execute(
            node_type,
            node_version,
            parameters,
            inputs,
            controllers,
            context=context,
        )
        if node_type == "CHAT_INPUT" and context:
            job_manager.cancel_job(context["run_id"])
        return result

    monkeypatch.setattr(node_registry, "execute", cancel_after_chat)
    job_state_factory("chat-cancelled", "workflow")

    result = execution_service.execute_plan_job(
        _chat_plan(),
        workflow_id="chat-workflow",
        job_id="chat-cancelled",
        execution_session_id="chat-session-cancelled",
    )

    assert result == {}
    assert in_memory_chat_history_repository.get_messages(
        "chat-workflow", "chat-session-cancelled", "chat"
    ) == []
