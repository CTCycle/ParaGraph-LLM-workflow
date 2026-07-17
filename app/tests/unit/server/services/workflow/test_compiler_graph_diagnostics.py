from __future__ import annotations

from server.domain.workflow_model import (
    WorkflowConnection,
    WorkflowDefinition,
    WorkflowNodeInstance,
)
from server.services.workflow.compiler.service import compiler_service


def _prompt(node_id: str, **overrides: object) -> WorkflowNodeInstance:
    return WorkflowNodeInstance(
        node_id=node_id,
        node_type="PROMPT",
        node_version=1,
        parameters={"prompt_text": "hello"},
        **overrides,
    )


def _text_output(node_id: str = "output") -> WorkflowNodeInstance:
    return WorkflowNodeInstance(
        node_id=node_id,
        node_type="TEXT_OUTPUT",
        node_version=1,
    )


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


def _codes(definition: WorkflowDefinition) -> tuple[bool, set[str]]:
    compiled = compiler_service.compile(definition, require_access_keys=False)
    return compiled.valid, {item.code for item in compiled.diagnostics}


def test_missing_terminal_output_is_a_non_blocking_diagnostic() -> None:
    valid, codes = _codes(
        WorkflowDefinition(schema_version=2, nodes=[_prompt("prompt")])
    )
    assert valid is True
    assert {"missing_terminal_output", "disconnected_node"} <= codes


def test_non_contributing_node_is_reported() -> None:
    definition = WorkflowDefinition(
        schema_version=2,
        nodes=[_prompt("used"), _prompt("unused"), _text_output()],
        connections=[_connection("used", "output")],
    )
    valid, codes = _codes(definition)
    assert valid is True
    assert {"disconnected_node", "node_not_contributing_to_output"} <= codes


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


def test_timeout_and_retries_are_copied_to_execution_plan() -> None:
    definition = WorkflowDefinition(
        schema_version=2,
        nodes=[
            _prompt("prompt", timeout_ms=2500, retries=2),
            _text_output(),
        ],
        connections=[_connection("prompt", "output")],
    )
    compiled = compiler_service.compile(definition, require_access_keys=False)
    assert compiled.valid is True
    assert compiled.plan is not None
    prompt_step = next(
        step for step in compiled.plan.steps if step.node_id == "prompt"
    )
    assert prompt_step.timeout_ms == 2500
    assert prompt_step.retries == 2
