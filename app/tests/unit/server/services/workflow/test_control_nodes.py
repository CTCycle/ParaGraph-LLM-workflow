from __future__ import annotations

import pytest

from server.services.workflow.node_handlers.control import (
    _cache_node_executor,
    _human_review_gate_executor,
    _if_text_contains_executor,
    _reduce_chunks_executor,
    _trace_debug_viewer_executor,
)
from server.contracts.execution import (
    CompiledExecutionPlan,
    ExecutionBinding,
    ExecutionRunState,
    ExecutionStepPlan,
    ExecutionStepState,
)
from server.repositories.workflow.execution_run import (
    ExecutionRunRepository,
    execution_run_repository,
)
from server.services.workflow.execution import execution_service
from server.services.workflow.nodes import node_registry


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
