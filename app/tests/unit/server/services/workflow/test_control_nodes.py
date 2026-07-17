from __future__ import annotations

from server.services.workflow.node_handlers.control import (
    _cache_node_executor,
    _human_review_gate_executor,
    _if_text_contains_executor,
    _reduce_chunks_executor,
    _trace_debug_viewer_executor,
)
from server.domain.execution import (
    CompiledExecutionPlan,
    ExecutionBinding,
    ExecutionStepPlan,
)
from server.repositories.workflow.execution_run import execution_run_repository
from server.services.workflow.execution import execution_service

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
