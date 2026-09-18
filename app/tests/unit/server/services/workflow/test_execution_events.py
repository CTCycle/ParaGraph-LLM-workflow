from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from server.contracts.execution import (
    CompiledExecutionPlan,
    ExecutionBinding,
    ExecutionRunState,
    ExecutionStepPlan,
)
from server.repositories.workflow.execution_run import execution_run_repository
from server.services.runtime.events import EventService, execution_event_service
from server.services.workflow.execution import execution_service

###############################################################################
def _create_event_run(run_id: str) -> None:
    plan = CompiledExecutionPlan(plan_id=f"plan-{run_id}")
    execution_run_repository.create_run(
        ExecutionRunState(run_id=run_id, plan_id=plan.plan_id, plan=plan)
    )

###############################################################################
def test_execution_event_sequence_is_monotonic_for_each_run() -> None:
    _create_event_run("run-a")
    _create_event_run("run-b")

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
    assert [
        event.sequence for event in execution_event_service.get_history("run-a").events
    ] == [1, 2]

###############################################################################
def test_execution_event_history_supports_sequence_pagination() -> None:
    _create_event_run("run-paged")
    for index in range(3):
        execution_event_service.publish(
            run_id="run-paged",
            event_type="execution.step.progress",
            payload={"index": index},
        )

    first_page = execution_event_service.get_history("run-paged", limit=2)
    second_page = execution_event_service.get_history(
        "run-paged", after_sequence=first_page.events[-1].sequence, limit=2
    )

    assert [event.sequence for event in first_page.events] == [1, 2]
    assert [event.sequence for event in second_page.events] == [3]

###############################################################################
def test_concurrent_event_publishers_receive_unique_sequences() -> None:
    _create_event_run("run-concurrent")

    def publish(index: int):
        return execution_event_service.publish(
            run_id="run-concurrent",
            event_type="execution.step.progress",
            payload={"index": index},
        )

    with ThreadPoolExecutor(max_workers=8) as executor:
        events = list(executor.map(publish, range(32)))

    assert sorted(event.sequence for event in events) == list(range(1, 33))
    assert [
        event.sequence
        for event in execution_event_service.get_history("run-concurrent").events
    ] == list(range(1, 33))

###############################################################################
def test_execution_service_emits_expected_event_order_for_prompt_to_output_plan(
    job_state_factory,
) -> None:
    plan = CompiledExecutionPlan(
        plan_id="plan-seq",
        step_order=["prompt_1", "output_1"],
        steps=[
            ExecutionStepPlan(
                step_id="prompt_1",
                node_id="prompt_1",
                node_type="PROMPT",
                node_version=1,
                category="prompt",
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
    result = execution_service.execute_plan_job(
        plan=plan, workflow_id=None, job_id="run-seq"
    )

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
    assert event_types.count("execution.started") == 1
    step_completed = [
        event for event in history if event.event_type == "execution.step.completed"
    ]
    assert [event.payload.get("progress") for event in step_completed] == [50.0, 99.0]

###############################################################################
def test_live_event_delivery_keeps_sequence_order_for_concurrent_publishers() -> None:
    _create_event_run("run-live-order")
    service = EventService()
    subscriber = service.subscribe("run-live-order")

    def publish(index: int):
        return service.publish(
            run_id="run-live-order",
            event_type="execution.step.progress",
            payload={"index": index},
        )

    with ThreadPoolExecutor(max_workers=8) as executor:
        published = list(executor.map(publish, range(32)))

    delivered = [subscriber.get_nowait().sequence for _ in published]
    assert delivered == [event.sequence for event in sorted(published, key=lambda item: item.sequence)]

###############################################################################
def test_replay_handoff_drops_only_snapshot_events() -> None:
    _create_event_run("run-replay-handoff")
    service = EventService()
    subscriber = service.subscribe("run-replay-handoff")
    first = service.publish(
        run_id="run-replay-handoff",
        event_type="execution.queued",
        payload={},
    )
    history = service.get_history("run-replay-handoff")
    second = service.publish(
        run_id="run-replay-handoff",
        event_type="execution.started",
        payload={},
    )

    replay_high_water_mark = history.events[-1].sequence
    live = []
    while not subscriber.empty():
        event = subscriber.get_nowait()
        if event.sequence > replay_high_water_mark:
            live.append(event)

    assert [event.sequence for event in history.events] == [first.sequence]
    assert [event.sequence for event in live] == [second.sequence]

###############################################################################
def test_live_subscriber_queue_marks_overflow_for_replay_recovery() -> None:
    _create_event_run("run-overflow")
    service = EventService(max_subscriber_queue_size=1)
    subscriber = service.subscribe("run-overflow")
    service.publish(
        run_id="run-overflow", event_type="execution.queued", payload={}
    )
    service.publish(
        run_id="run-overflow", event_type="execution.started", payload={}
    )

    assert subscriber.overflowed is True
    assert subscriber.qsize() == 1

###############################################################################
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

###############################################################################
def test_execution_service_skips_cache_key_build_for_non_cacheable_steps(
    job_state_factory, monkeypatch
) -> None:
    plan = CompiledExecutionPlan(
        plan_id="plan-no-cache-key",
        step_order=["prompt_1", "output_1"],
        steps=[
            ExecutionStepPlan(
                step_id="prompt_1",
                node_id="prompt_1",
                node_type="PROMPT",
                node_version=1,
                category="prompt",
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

    def fail_cache_key(*_args, **_kwargs):
        raise AssertionError(
            "_build_cache_key should not be called for non-cacheable steps"
        )

    monkeypatch.setattr(execution_service, "_build_cache_key", fail_cache_key)
    job_state_factory("run-no-cache-key", "workflow")

    result = execution_service.execute_plan_job(
        plan=plan, workflow_id=None, job_id="run-no-cache-key"
    )

    assert result == {"outputs": {"output_1": {"text": "hello"}}}

###############################################################################
def test_execution_service_persists_compact_step_output_payload(
    job_state_factory,
) -> None:
    plan = CompiledExecutionPlan(
        plan_id="plan-compact-output",
        step_order=["prompt_1", "output_1"],
        steps=[
            ExecutionStepPlan(
                step_id="prompt_1",
                node_id="prompt_1",
                node_type="PROMPT",
                node_version=1,
                category="prompt",
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

    job_state_factory("run-compact-output", "workflow")
    execution_service.execute_plan_job(
        plan=plan, workflow_id=None, job_id="run-compact-output"
    )
    run = execution_service.get_run("run-compact-output")

    assert run is not None
    assert all(set(step.output.keys()) == {"inputs", "ports"} for step in run.steps)

###############################################################################
def test_execution_service_uses_json_field_as_prompt_template_variable(
    job_state_factory,
) -> None:
    plan = CompiledExecutionPlan(
        plan_id="plan-json-field-output",
        step_order=["prompt_1", "template_1", "output_1"],
        steps=[
            ExecutionStepPlan(
                step_id="prompt_1",
                node_id="prompt_1",
                node_type="PROMPT",
                node_version=1,
                category="prompt",
                executor_key="prompt",
                parameters={"prompt_text": '{"greeting":"hello"}'},
                bindings=[],
                cacheable=False,
            ),
            ExecutionStepPlan(
                step_id="template_1",
                node_id="template_1",
                node_type="PROMPT_TEMPLATE",
                node_version=1,
                category="prompt",
                executor_key="prompt_template",
                parameters={"template": "{{ greeting }}"},
                bindings=[
                    ExecutionBinding(
                        binding_type="input",
                        input_name="variables",
                        source_node_id="prompt_1",
                        source_output="text",
                    )
                ],
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
                        source_node_id="template_1",
                        source_output="text",
                    )
                ],
                cacheable=False,
            ),
        ],
        metadata={},
    )

    job_state_factory("run-json-field-output", "workflow")
    result = execution_service.execute_plan_job(
        plan=plan, workflow_id=None, job_id="run-json-field-output"
    )

    assert result == {"outputs": {"output_1": {"text": "hello"}}}
