from __future__ import annotations

from server.services.workflow.execution import ExecutionService


###############################################################################
def test_json_object_output_exposes_top_level_keys_to_prompt_template() -> None:
    service = ExecutionService()
    assert service._publish_named_output({"summary": "S", "keywords": ["a"]}, None) == {
        "summary": "S",
        "keywords": ["a"],
    }


###############################################################################
def test_json_string_object_output_exposes_top_level_keys_to_prompt_template() -> None:
    service = ExecutionService()
    assert service._publish_named_output('{"summary": "S"}', None) == {"summary": "S"}


###############################################################################
def test_json_array_output_does_not_create_named_variables() -> None:
    service = ExecutionService()
    assert service._publish_named_output("[1, 2]", None) == "[1, 2]"


###############################################################################
def test_output_name_alias_still_available_for_json_object() -> None:
    service = ExecutionService()
    assert service._publish_named_output({"summary": "S"}, "payload") == {
        "summary": "S",
        "payload": {"summary": "S"},
    }


###############################################################################
def test_output_name_collision_uses_alias_and_preserves_json_fields() -> None:
    service = ExecutionService()
    assert service._publish_named_output({"payload": "field"}, "payload") == {
        "payload": {"payload": "field"},
        "__json_fields__": {"payload": "field"},
    }


###############################################################################
def test_controller_binding_does_not_apply_named_output_wrapping() -> None:
    service = ExecutionService()
    value = {"summary": "S"}
    assert value == {"summary": "S"}
    assert service._publish_named_output(value, None) == value
