from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

from server.domain.execution import (
    CompiledExecutionPlan,
    ExecutionRunState,
    ExecutionStepPlan,
    ExecutionStepState,
)
from server.repositories.workflow.execution_run import (
    ExecutionRunRepository,
    execution_run_repository,
)
from server.services.runtime.events import EventService, execution_event_service
from server.services.workflow.execution import execution_service
from server.services.workflow.nodes import node_registry


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
