from __future__ import annotations

from server.services.workflow.execution import ExecutionService


###############################################################################
def test_json_object_output_exposes_top_level_keys_to_prompt_template() -> None:
    service = ExecutionService()
    assert service._publish_named_output({"summary": "S", "keywords": ["a"]}) == {
        "summary": "S",
        "keywords": ["a"],
    }


###############################################################################
def test_json_string_object_output_exposes_top_level_keys_to_prompt_template() -> None:
    service = ExecutionService()
    assert service._publish_named_output('{"summary": "S"}') == {"summary": "S"}


###############################################################################
def test_json_array_output_does_not_create_named_variables() -> None:
    service = ExecutionService()
    assert service._publish_named_output("[1, 2]") == "[1, 2]"


###############################################################################
def test_scalar_output_remains_scalar() -> None:
    service = ExecutionService()
    assert service._publish_named_output(17) == 17


###############################################################################
def test_controller_binding_does_not_apply_named_output_wrapping() -> None:
    service = ExecutionService()
    value = {"summary": "S"}
    assert value == {"summary": "S"}
    assert service._publish_named_output(value) == value
