from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any
from server.services.jobs import job_manager
from server.contracts.workflow_model import WorkflowConnection, WorkflowDefinition, WorkflowNodeInstance
from server.services.workflow.compiler.service import compiler_service
import pytest
from server.services.workflow.node_handlers.control import _cache_node_executor, _human_review_gate_executor, _if_text_contains_executor, _reduce_chunks_executor, _trace_debug_viewer_executor
from server.contracts.execution import CompiledExecutionPlan, ExecutionBinding, ExecutionRunState, ExecutionStepPlan, ExecutionStepState
from server.repositories.workflow.execution_run import ExecutionRunRepository, execution_run_repository
from server.services.workflow.execution import execution_service
from server.services.workflow.nodes import node_registry
from datetime import datetime, timedelta, timezone
from server.services.runtime.events import EventService, execution_event_service
from concurrent.futures import ThreadPoolExecutor

# Job service

###############################################################################
class RecordingJobRunner:

    # -------------------------------------------------------------------------
    def __init__(self) -> None:
        self.observed: dict[str, str] = {}

    # -------------------------------------------------------------------------
    def __call__(self, *, job_id: str) -> dict[str, Any]:
        self.observed["job_id"] = job_id
        job_manager.update_result(job_id, {"stage": "running"})
        return {"success": True}

###############################################################################
def cancellable_runner(*, job_id: str) -> dict[str, Any]:
    while not job_manager.should_stop(job_id):
        time.sleep(0.01)
    return {"success": False}

###############################################################################
def test_start_job_injects_job_id_and_merges_results(
    wait_for_job: Callable[[str, float], dict[str, object]],
) -> None:
    runner = RecordingJobRunner()

    job_id = job_manager.start_job(job_type="unit", runner=runner)
    payload = wait_for_job(job_id)

    assert runner.observed["job_id"] == job_id
    assert payload["status"] == "completed"
    assert payload["progress"] == 100.0
    assert payload["result"] == {"stage": "running", "success": True}

###############################################################################
def test_cancel_job_marks_running_job_cancelled(
    wait_for_job: Callable[[str, float], dict[str, object]],
) -> None:
    job_id = job_manager.start_job(job_type="unit", runner=cancellable_runner)

    assert job_manager.cancel_job(job_id) is True

    payload = wait_for_job(job_id)

    assert payload["status"] == "cancelled"
    assert payload["result"] is None

###############################################################################
def test_cancel_job_returns_false_for_unknown_job() -> None:
    assert job_manager.cancel_job("missing-job") is False

# Compiler graph diagnostics

###############################################################################
def _prompt(node_id: str, **overrides: object) -> WorkflowNodeInstance:
    return WorkflowNodeInstance(
        node_id=node_id,
        node_type="PROMPT",
        node_version=1,
        parameters={"prompt_text": "hello"},
        **overrides,
    )

###############################################################################
def _text_output(node_id: str = "output") -> WorkflowNodeInstance:
    return WorkflowNodeInstance(
        node_id=node_id,
        node_type="TEXT_OUTPUT",
        node_version=1,
    )

###############################################################################
def _chat(node_id: str = "chat") -> WorkflowNodeInstance:
    return WorkflowNodeInstance(
        node_id=node_id,
        node_type="CHAT_INPUT",
        node_version=1,
        parameters={"message": "hello"},
    )

###############################################################################
def _memory(node_id: str = "memory") -> WorkflowNodeInstance:
    return WorkflowNodeInstance(
        node_id=node_id,
        node_type="CHAT_HISTORY_MEMORY",
        node_version=1,
        parameters={"max_messages": 10, "separator": "\n", "keep_prompt_type": True},
    )

###############################################################################
def _connection(
    source: str,
    target: str,
    *,
    output: str = "text",
    input_name: str = "text",
) -> WorkflowConnection:
    return WorkflowConnection(
        from_node=source,
        to_node=target,
        from_output=output,
        to_input=input_name,
    )

###############################################################################
def _codes(definition: WorkflowDefinition) -> tuple[bool, set[str]]:
    compiled = compiler_service.compile(
        definition, require_provider_configuration=False
    )
    return compiled.valid, {item.code for item in compiled.diagnostics}

###############################################################################
def test_missing_terminal_output_is_a_non_blocking_diagnostic() -> None:
    valid, codes = _codes(
        WorkflowDefinition(schema_version=2, nodes=[_prompt("prompt")])
    )
    assert valid is True
    assert {"missing_terminal_output", "disconnected_node"} <= codes

###############################################################################
def test_non_contributing_node_is_reported() -> None:
    definition = WorkflowDefinition(
        schema_version=2,
        nodes=[_prompt("used"), _prompt("unused"), _text_output()],
        connections=[_connection("used", "output")],
    )
    valid, codes = _codes(definition)
    assert valid is False
    assert {
        "disconnected_execution_component",
        "disconnected_node",
        "node_not_contributing_to_output",
    } <= codes

###############################################################################
def test_disconnected_side_effecting_node_blocks_plan_creation() -> None:
    definition = WorkflowDefinition(
        schema_version=2,
        nodes=[
            _prompt("prompt"),
            _text_output(),
            WorkflowNodeInstance(
                node_id="save",
                node_type="SAVE_AS_FILE",
                node_version=1,
                parameters={"output_path": "unsafe.txt", "extension": ".txt"},
            ),
        ],
        connections=[_connection("prompt", "output")],
    )

    compiled = compiler_service.compile(
        definition, require_provider_configuration=False
    )

    assert compiled.valid is False
    assert compiled.plan is None
    codes = {item.code for item in compiled.diagnostics}
    assert {
        "disconnected_execution_component",
        "disconnected_side_effecting_node",
    } <= codes

###############################################################################
def test_conditional_branch_connection_is_reported() -> None:
    definition = WorkflowDefinition(
        schema_version=2,
        nodes=[
            _prompt("prompt"),
            WorkflowNodeInstance(
                node_id="branch",
                node_type="IF_TEXT_CONTAINS",
                node_version=1,
                parameters={"keyword": "hello"},
            ),
            _text_output(),
        ],
        connections=[
            _connection("prompt", "branch"),
            _connection("branch", "output", output="true"),
        ],
    )
    valid, codes = _codes(definition)
    assert valid is True
    assert "conditional_output_connection" in codes

###############################################################################
def test_invalid_timeout_and_retry_values_block_compilation() -> None:
    definition = WorkflowDefinition(
        schema_version=2,
        nodes=[
            _prompt("prompt", timeout_ms=0, retries=-1),
            _text_output(),
        ],
        connections=[_connection("prompt", "output")],
    )
    valid, codes = _codes(definition)
    assert valid is False
    assert {"invalid_timeout", "invalid_retries"} <= codes

###############################################################################
def test_side_effect_retry_requires_an_idempotency_contract() -> None:
    definition = WorkflowDefinition(
        schema_version=2,
        nodes=[
            _prompt("prompt"),
            WorkflowNodeInstance(
                node_id="save",
                node_type="SAVE_AS_FILE",
                node_version=1,
                parameters={"output_path": "phase3.txt", "extension": ".txt"},
                retries=1,
            ),
        ],
        connections=[_connection("prompt", "save")],
    )
    valid, codes = _codes(definition)
    assert valid is False
    assert "unsafe_side_effect_retry" in codes

###############################################################################
def test_idempotent_side_effect_carries_effect_metadata_into_plan() -> None:
    definition = WorkflowDefinition(
        schema_version=2,
        nodes=[
            WorkflowNodeInstance(
                node_id="store",
                node_type="VECTOR_STORE",
                node_version=2,
                parameters={"storage_path": "vectorstores"},
            ),
            WorkflowNodeInstance(
                node_id="lifecycle",
                node_type="VECTOR_STORE_LIFECYCLE",
                node_version=1,
                parameters={"operation": "inspect"},
                retries=1,
            ),
        ],
        connections=[
            WorkflowConnection(
                from_node="store",
                to_node="lifecycle",
                connection_type="controller",
                from_controller="store",
                to_controller="store",
            )
        ],
    )

    compiled = compiler_service.compile(
        definition, require_provider_configuration=False
    )

    assert compiled.valid is True
    assert compiled.plan is not None
    lifecycle = next(
        step for step in compiled.plan.steps if step.node_id == "lifecycle"
    )
    assert lifecycle.side_effecting is True
    assert lifecycle.destructive is True
    assert lifecycle.idempotent is True

###############################################################################
def test_timeout_and_retries_are_copied_to_execution_plan() -> None:
    definition = WorkflowDefinition(
        schema_version=2,
        nodes=[
            _prompt("prompt", timeout_ms=2500, retries=2),
            _text_output(),
        ],
        connections=[_connection("prompt", "output")],
    )
    compiled = compiler_service.compile(
        definition, require_provider_configuration=False
    )
    assert compiled.valid is True
    assert compiled.plan is not None
    prompt_step = next(step for step in compiled.plan.steps if step.node_id == "prompt")
    assert prompt_step.timeout_ms == 2500
    assert prompt_step.retries == 2

###############################################################################
def test_chat_requires_one_reachable_terminal_output_and_records_it() -> None:
    definition = WorkflowDefinition(
        schema_version=2,
        nodes=[_memory(), _chat(), _text_output()],
        connections=[
            WorkflowConnection(
                from_node="memory",
                to_node="chat",
                connection_type="controller",
                from_controller="history",
                to_controller="history",
            ),
            _connection("chat", "output"),
        ],
    )

    compiled = compiler_service.compile(
        definition, require_provider_configuration=False
    )

    assert compiled.valid is True
    assert compiled.plan is not None
    assert compiled.plan.metadata["chat_terminal_outputs"] == {"chat": "output"}

###############################################################################
def test_chat_without_terminal_output_is_a_blocking_diagnostic() -> None:
    definition = WorkflowDefinition(
        schema_version=2,
        nodes=[_memory(), _chat()],
        connections=[
            WorkflowConnection(
                from_node="memory",
                to_node="chat",
                connection_type="controller",
                from_controller="history",
                to_controller="history",
            )
        ],
    )

    valid, codes = _codes(definition)

    assert valid is False
    assert "chat_terminal_output_count" in codes

###############################################################################
def test_chat_with_multiple_reachable_terminal_outputs_is_a_blocking_diagnostic() -> (
    None
):
    definition = WorkflowDefinition(
        schema_version=2,
        nodes=[
            _memory(),
            _chat(),
            _text_output("output-one"),
            _text_output("output-two"),
        ],
        connections=[
            WorkflowConnection(
                from_node="memory",
                to_node="chat",
                connection_type="controller",
                from_controller="history",
                to_controller="history",
            ),
            _connection("chat", "output-one"),
            _connection("chat", "output-two"),
        ],
    )

    valid, codes = _codes(definition)

    assert valid is False
    assert "chat_terminal_output_count" in codes

# Control nodes

###############################################################################
def test_if_text_contains_selects_true_and_false_branch() -> None:
    assert (
        _if_text_contains_executor({"keyword": "yes"}, {"text": "yes"})["selected"]
        == "true"
    )
    assert (
        _if_text_contains_executor({"keyword": "yes"}, {"text": "no"})["selected"]
        == "false"
    )

###############################################################################
def test_reduce_chunks_joins_text() -> None:
    assert _reduce_chunks_executor({}, {"chunks": ["a", "b"]})["result"] == "a\nb"

###############################################################################
def test_cache_node_returns_cached_deterministic_output() -> None:
    assert "cache_key" in _cache_node_executor({}, {"value": "x"})

###############################################################################
def test_human_review_gate_pauses_run_payload() -> None:
    assert _human_review_gate_executor({}, {"value": "x"})["paused"] is True

###############################################################################
def test_invalid_persisted_pause_state_fails_closed() -> None:
    plan = CompiledExecutionPlan(plan_id="invalid-pause-plan")
    execution_run_repository.create_run(
        ExecutionRunState(
            run_id="invalid-pause-run",
            plan_id=plan.plan_id,
            plan=plan,
            status="paused",
            pause_payload={"reason": "legacy"},
            resume_token="resume-token",
            steps=[
                ExecutionStepState(
                    step_id="review",
                    node_id="review",
                    node_type="HUMAN_REVIEW_GATE",
                    status="paused",
                )
            ],
        )
    )

    with pytest.raises(ValueError, match="Persisted pause checkpoint is invalid"):
        ExecutionRunRepository().get_run("invalid-pause-run")

###############################################################################
def test_trace_debug_viewer_redacts_sensitive_payload_fields() -> None:
    result = _trace_debug_viewer_executor({}, {"api_key": "secret"})
    assert result["result"]["inputs"]["api_key"] == "[REDACTED]"

###############################################################################
def test_execution_skips_unselected_branch_and_pauses_run(monkeypatch) -> None:
    execution_run_repository.reset_for_tests()
    outputs = {
        "branch": {"true": "yes"},
        "gate": {"paused": True, "pause_payload": {"reason": "review"}},
    }

    def fake_execute_step(**kwargs):
        step = kwargs["step"]
        kwargs["outputs_by_step"][step.step_id] = outputs[step.step_id]
        return {"inputs": {}, "ports": outputs[step.step_id]}

    monkeypatch.setattr(execution_service, "_execute_step", fake_execute_step)
    monkeypatch.setattr(execution_service, "_cancelled", lambda job_id: False)
    plan = CompiledExecutionPlan(
        plan_id="p",
        step_order=["branch", "false_step", "gate"],
        steps=[
            ExecutionStepPlan(
                step_id="branch",
                node_id="branch",
                node_type="IF_TEXT_CONTAINS",
                node_version=1,
                category="control",
                executor_key="if_text_contains",
            ),
            ExecutionStepPlan(
                step_id="false_step",
                node_id="false_step",
                node_type="TEXT_OUTPUT",
                node_version=1,
                category="output",
                executor_key="text_output",
                bindings=[
                    ExecutionBinding(
                        input_name="text",
                        source_node_id="branch",
                        source_output="false",
                    )
                ],
            ),
            ExecutionStepPlan(
                step_id="gate",
                node_id="gate",
                node_type="HUMAN_REVIEW_GATE",
                node_version=1,
                category="control",
                executor_key="human_review_gate",
            ),
        ],
    )
    execution_service.execute_plan_job(plan, None, "run-1")
    run = execution_run_repository.get_run("run-1")
    assert run is not None
    assert run.status == "paused"
    assert (
        next(step for step in run.steps if step.step_id == "false_step").status
        == "skipped"
    )

###############################################################################
def test_human_review_pause_survives_reload_and_injects_reviewed_payload(
    job_state_factory, wait_for_job, monkeypatch
) -> None:
    captured: dict[str, object] = {}
    original_execute = node_registry.execute

    def spy_execute(*args, **kwargs):
        if args and args[0] == "JOIN_MERGE_TEXT":
            captured.update(args[3])
        return original_execute(*args, **kwargs)

    monkeypatch.setattr(node_registry, "execute", spy_execute)
    plan = CompiledExecutionPlan(
        plan_id="review-plan",
        step_order=["gate", "merge"],
        steps=[
            ExecutionStepPlan(
                step_id="gate",
                node_id="gate",
                node_type="HUMAN_REVIEW_GATE",
                node_version=1,
                category="control",
                executor_key="human_review_gate",
                parameters={},
            ),
            ExecutionStepPlan(
                step_id="merge",
                node_id="merge",
                node_type="JOIN_MERGE_TEXT",
                node_version=1,
                category="processing",
                executor_key="join_merge_text",
                bindings=[
                    ExecutionBinding(
                        input_name="value",
                        source_node_id="gate",
                        source_output="result",
                    )
                ],
            ),
        ],
    )
    job_state_factory("review-run", "workflow")

    execution_service.execute_plan_job(plan, None, "review-run")
    paused = execution_run_repository.get_run("review-run")
    assert paused is not None
    assert paused.status == "paused"
    assert paused.resume_token
    assert paused.pause_checkpoint is not None
    assert paused.pause_checkpoint.node_id == "gate"
    assert (
        next(step for step in paused.steps if step.step_id == "gate").status == "paused"
    )

    reloaded = ExecutionRunRepository().get_run("review-run")
    assert reloaded is not None
    assert reloaded.pause_checkpoint == paused.pause_checkpoint

    token = paused.resume_token
    assert token is not None
    execution_service.resume("review-run", token, {"approved": True})
    wait_for_job("review-run")

    completed = execution_run_repository.get_run("review-run")
    assert completed is not None
    assert completed.status == "completed"
    assert captured["value"] == {"approved": True}
    with pytest.raises(ValueError, match="not paused or resume token is invalid"):
        execution_service.resume("review-run", token, {"approved": True})

# Execution durability

###############################################################################
def _plan(*, retries: int = 0, timeout_ms: int | None = None) -> CompiledExecutionPlan:
    step = ExecutionStepPlan(
        step_id="step",
        node_id="node",
        node_type="PROMPT",
        node_version=1,
        category="prompt",
        executor_key="prompt",
        parameters={},
        retries=retries,
        timeout_ms=timeout_ms,
    )
    return CompiledExecutionPlan(
        plan_id="durable-plan", step_order=["step"], steps=[step]
    )

###############################################################################
def test_run_steps_and_events_survive_repository_reinstantiation() -> None:
    plan = _plan()
    execution_run_repository.create_run(
        ExecutionRunState(
            run_id="durable-run",
            plan_id=plan.plan_id,
            plan=plan,
            steps=[
                ExecutionStepState(step_id="step", node_id="node", node_type="PROMPT")
            ],
        )
    )
    execution_run_repository.update_step(
        "durable-run",
        "step",
        status="completed",
        output={"ports": {"text": "persisted"}},
    )
    execution_event_service.publish(
        run_id="durable-run", event_type="execution.queued", payload={}
    )

    fresh_repository = ExecutionRunRepository()
    fresh_events = EventService().get_history("durable-run")

    restored = fresh_repository.get_run("durable-run")
    assert restored is not None
    assert restored.plan == plan
    assert restored.steps[0].output["ports"]["text"] == "persisted"
    assert [event.sequence for event in fresh_events.events] == [1]

###############################################################################
def test_list_recoverable_batches_run_and_step_loading(monkeypatch) -> None:
    plan = _plan()
    for run_id, status in (("recoverable-queued", "queued"), ("recoverable-running", "running")):
        execution_run_repository.create_run(
            ExecutionRunState(
                run_id=run_id,
                plan_id=plan.plan_id,
                plan=plan,
                status=status,
                steps=[
                    ExecutionStepState(
                        step_id="step", node_id="node", node_type="PROMPT"
                    )
                ],
            )
        )

    def unexpected_get_run(*args, **kwargs):
        raise AssertionError("list_recoverable must batch-load run state")

    monkeypatch.setattr(execution_run_repository, "get_run", unexpected_get_run)

    recoverable = execution_run_repository.list_recoverable()

    assert {run.run_id for run in recoverable} == {
        "recoverable-queued",
        "recoverable-running",
    }
    assert all(len(run.steps) == 1 for run in recoverable)

###############################################################################
def test_retry_succeeds_without_restarting_prior_steps(
    job_state_factory, monkeypatch
) -> None:
    calls = 0

    def flaky(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("transient")
        return {"text": "ok"}

    monkeypatch.setattr(node_registry, "execute", flaky)
    job_state_factory("retry-run", "workflow")
    result = execution_service.execute_plan_job(_plan(retries=1), None, "retry-run")

    assert result == {"outputs": {}}
    assert calls == 2
    run = execution_run_repository.get_run("retry-run")
    assert run is not None and run.steps[0].attempt_count == 2
    assert run.status == "completed"

###############################################################################
def test_retry_exhaustion_records_final_failure(job_state_factory, monkeypatch) -> None:
    monkeypatch.setattr(
        node_registry,
        "execute",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("always")),
    )
    job_state_factory("failed-retry", "workflow")

    try:
        execution_service.execute_plan_job(_plan(retries=1), None, "failed-retry")
    except RuntimeError:
        pass

    run = execution_run_repository.get_run("failed-retry")
    assert run is not None and run.status == "failed"
    assert run.steps[0].attempt_count == 2

###############################################################################
def test_timeout_late_result_cannot_overwrite_terminal_state(
    job_state_factory, monkeypatch
) -> None:
    def slow(*_args, **_kwargs):
        time.sleep(0.1)
        return {"text": "late"}

    monkeypatch.setattr(node_registry, "execute", slow)
    job_state_factory("timeout-run", "workflow")
    try:
        execution_service.execute_plan_job(_plan(timeout_ms=10), None, "timeout-run")
    except TimeoutError:
        pass
    time.sleep(0.15)

    run = execution_run_repository.get_run("timeout-run")
    assert run is not None and run.status == "failed"
    assert run.steps[0].status == "failed"
    assert run.steps[0].output == {}

###############################################################################
def test_timeout_retries_safe_attempt_and_ignores_late_local_result(
    job_state_factory, monkeypatch
) -> None:
    calls = 0

    def slow_then_fast(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            time.sleep(0.1)
            return {"text": "late"}
        return {"text": "ok"}

    monkeypatch.setattr(node_registry, "execute", slow_then_fast)
    job_state_factory("timeout-retry-run", "workflow")
    result = execution_service.execute_plan_job(
        _plan(retries=1, timeout_ms=10), None, "timeout-retry-run"
    )
    time.sleep(0.15)

    assert result == {"outputs": {}}
    assert calls == 2
    run = execution_run_repository.get_run("timeout-retry-run")
    assert run is not None and run.status == "completed"
    assert run.steps[0].output["ports"] == {"text": "ok"}
    event_types = [
        event.event_type
        for event in execution_event_service.get_history("timeout-retry-run").events
    ]
    assert event_types.count("execution.step.timeout") == 1
    assert event_types.count("execution.step.retry.failed") == 1
    assert event_types.count("execution.step.retry.started") == 1

###############################################################################
def test_handler_timeout_error_is_not_misclassified_as_step_timeout(
    job_state_factory, monkeypatch
) -> None:
    def provider_timeout(*_args, **_kwargs):
        raise TimeoutError("provider timeout")

    monkeypatch.setattr(node_registry, "execute", provider_timeout)
    job_state_factory("provider-timeout-run", "workflow")
    try:
        execution_service.execute_plan_job(
            _plan(timeout_ms=100), None, "provider-timeout-run"
        )
    except TimeoutError as exc:
        assert str(exc) == "provider timeout"
    else:
        raise AssertionError("Expected provider timeout to be propagated")

    run = execution_run_repository.get_run("provider-timeout-run")
    assert run is not None and run.error == "provider timeout"
    event_types = [
        event.event_type
        for event in execution_event_service.get_history("provider-timeout-run").events
    ]
    assert "execution.step.timeout" not in event_types

###############################################################################
def test_cancel_before_start_and_retention_cleanup() -> None:
    plan = _plan()
    execution_service._initialize_run(plan, None, None, "cancel-run", request_id=None)  # noqa: SLF001
    cancelled = execution_service.cancel("cancel-run")
    assert cancelled is not None and cancelled.status == "cancelled"

    removed = execution_run_repository.cleanup_completed_before(
        datetime.now(timezone.utc) + timedelta(seconds=1)
    )
    assert removed == 1
    assert execution_run_repository.get_run("cancel-run") is None

# Execution events

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

# Execution security

###############################################################################
def test_redact_output_state_masks_sensitive_controller_fields() -> None:
    output_state = {
        "inputs": {"prompt": "hello"},
        "controllers": {
            "connection": {
                "engine": "postgresql",
                "username": "analyst",
                "password": "super-secret",
                "api_key": "token-value",
            }
        },
        "ports": {"result": "ok"},
    }

    redacted = execution_service._redact_output_state(output_state)  # noqa: SLF001

    assert redacted["controllers"]["connection"]["password"] == "***"
    assert redacted["controllers"]["connection"]["api_key"] == "***"
    assert redacted["controllers"]["connection"]["username"] == "analyst"
