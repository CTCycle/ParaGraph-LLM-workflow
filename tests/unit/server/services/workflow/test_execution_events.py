from __future__ import annotations

from ParaGraph.server.domain.execution import CompiledExecutionPlan, ExecutionBinding, ExecutionStepPlan
from ParaGraph.server.services.runtime.events import execution_event_service
from ParaGraph.server.services.workflow.execution import execution_service



def test_execution_event_sequence_is_monotonic_for_each_run() -> None:
    first = execution_event_service.publish(
        run_id="run-a",
        event_type="execution.queued",
        payload={"state": "queued"},
    )
    second = execution_event_service.publish(
        run_id="run-a",
        event_type="execution.started",
        payload={"state": "running"},
    )
    third = execution_event_service.publish(
        run_id="run-b",
        event_type="execution.queued",
        payload={"state": "queued"},
    )

    assert first.sequence == 1
    assert second.sequence == 2
    assert third.sequence == 1
    assert [event.sequence for event in execution_event_service.get_history("run-a").events] == [1, 2]



def test_execution_service_emits_expected_event_order_for_prompt_to_output_plan(job_state_factory) -> None:
    plan = CompiledExecutionPlan(
        plan_id="plan-seq",
        step_order=["prompt_1", "output_1"],
        steps=[
            ExecutionStepPlan(
                step_id="prompt_1",
                node_id="prompt_1",
                node_type="PROMPT",
                node_version=1,
                category="input",
                executor_key="prompt",
                parameters={"prompt_text": "hello"},
                bindings=[],
                cacheable=False,
            ),
            ExecutionStepPlan(
                step_id="output_1",
                node_id="output_1",
                node_type="TEXT_OUTPUT",
                node_version=1,
                category="output",
                executor_key="text_output",
                parameters={},
                bindings=[
                    ExecutionBinding(
                        binding_type="input",
                        input_name="text",
                        source_node_id="prompt_1",
                        source_output="text",
                    )
                ],
                cacheable=False,
            ),
        ],
        metadata={},
    )

    job_state_factory("run-seq", "workflow")
    result = execution_service.execute_plan_job(plan=plan, workflow_id=None, job_id="run-seq")

    assert result == {"outputs": {"output_1": {"text": "hello"}}}

    history = execution_event_service.get_history("run-seq").events
    event_types = [event.event_type for event in history]
    assert event_types == [
        "execution.queued",
        "execution.started",
        "execution.step.started",
        "execution.step.completed",
        "execution.step.started",
        "execution.step.completed",
        "execution.completed",
    ]
    assert [event.sequence for event in history] == list(range(1, len(history) + 1))
    step_completed = [event for event in history if event.event_type == "execution.step.completed"]
    assert [event.payload.get("progress") for event in step_completed] == [50.0, 99.0]



def test_redact_output_state_masks_nested_sensitive_fields() -> None:
    payload = {
        "inputs": {"text": "hello"},
        "controllers": {
            "credentials": {
                "api_key": "secret-token",
                "nested": {"password": "super-secret", "username": "alice"},
            }
        },
        "ports": {
            "result": {
                "access_token": "internal-token",
                "metadata": [{"authorization": "Bearer abc"}, {"safe": True}],
            }
        },
    }

    redacted = execution_service._redact_output_state(payload)  # noqa: SLF001

    assert redacted["controllers"]["credentials"]["api_key"] == "***"
    assert redacted["controllers"]["credentials"]["nested"]["password"] == "***"
    assert redacted["controllers"]["credentials"]["nested"]["username"] == "alice"
    assert redacted["ports"]["result"]["access_token"] == "***"
    assert redacted["ports"]["result"]["metadata"][0]["authorization"] == "***"
