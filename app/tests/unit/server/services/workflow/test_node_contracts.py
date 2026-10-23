from __future__ import annotations

from server.common.utils.values import coerce_float, coerce_json_object, extract_top_level_json_fields, parse_json_if_possible
from server.services.workflow.execution import ExecutionService
import pytest
from server.services.workflow import node_registry
from server.services.workflow.node_handlers.core.prompts import _prompt_template_executor
from server.services.workflow.node_handlers.structured import _structured_input_executor, _structured_output_executor
from server.services.workflow.structured_models import infer_model_from_json, parse_user_pydantic_model, validate_json_with_model

# Node handler common behavior

###############################################################################
def test_json_object_parsing_from_dict_and_string() -> None:
    assert coerce_json_object({"summary": "ok"}) == {"summary": "ok"}
    assert coerce_json_object('{"summary": "ok"}') == {"summary": "ok"}

###############################################################################
def test_non_object_json_does_not_expose_top_level_fields() -> None:
    assert extract_top_level_json_fields("[1, 2]") == {}

###############################################################################
def test_invalid_json_returns_original_text_where_required() -> None:
    assert parse_json_if_possible("{bad json") == "{bad json"

###############################################################################
def test_coerce_float_handles_invalid_value() -> None:
    assert coerce_float("not-a-number", 1.5) == 1.5

# Named JSON variables

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

# Prompt nodes

###############################################################################
def test_prompt_template_renders_jinja_variables() -> None:
    payload = node_registry.execute(
        "PROMPT_TEMPLATE",
        1,
        {"template": "Hello {{ name }} from {{ city }}."},
        {
            "variables": [
                {"name": "Alice"},
                {"city": "Rome"},
            ]
        },
    )

    assert payload["text"] == "Hello Alice from Rome."

###############################################################################
def test_prompt_template_fails_when_jinja_variable_is_missing() -> None:
    with pytest.raises(ValueError, match="failed to render Jinja template"):
        node_registry.execute(
            "PROMPT_TEMPLATE",
            1,
            {"template": "A={{ known }} B={{ missing }}"},
            {"variables": {"known": "ok"}},
        )

###############################################################################
def test_prompt_template_merges_multiple_input_maps() -> None:
    payload = node_registry.execute(
        "PROMPT_TEMPLATE",
        1,
        {"template": "{{ first }} {{ second }} {{ third }}"},
        {"variables": [{"first": "A"}, {"second": "B", "third": "C"}]},
    )

    assert payload["text"] == "A B C"

# Prompt template rendering

###############################################################################
def test_render_summary_from_upstream_json_object() -> None:
    result = _prompt_template_executor(
        {"template": "{{ summary }}"},
        {"variables": {"summary": "Done"}},
    )
    assert result["text"] == "Done"

###############################################################################
def test_render_list_variable_with_join_filter() -> None:
    result = _prompt_template_executor(
        {"template": "{{ keywords | join(', ') }}"},
        {"variables": {"keywords": ["alpha", "beta"]}},
    )
    assert result["text"] == "alpha, beta"

###############################################################################
def test_render_system_and_user_sections() -> None:
    result = _prompt_template_executor(
        {
            "system_template": "System {{ role }}",
            "user_template": "User {{ task }}",
        },
        {"variables": {"role": "R", "task": "T"}},
    )
    assert result["system"] == "System R"
    assert result["user"] == "User T"

###############################################################################
def test_strict_missing_variable_raises_clear_validation_error() -> None:
    with pytest.raises(ValueError, match="failed to render Jinja template"):
        _prompt_template_executor({"template": "{{ missing }}"}, {"variables": {}})

###############################################################################
def test_legacy_format_syntax_is_not_interpolated() -> None:
    result = _prompt_template_executor(
        {"template": "Hello {name}"},
        {"variables": {"name": "World"}},
    )
    assert result["text"] == "Hello {name}"

# Structured JSON nodes

###############################################################################
def test_auto_model_inference_from_json() -> None:
    model = infer_model_from_json("Payload", {"summary": "x", "count": 1})
    assert validate_json_with_model({"summary": "x", "count": 1}, model) == {
        "summary": "x",
        "count": 1,
    }

###############################################################################
def test_pasted_pydantic_model_validation_success() -> None:
    model = parse_user_pydantic_model("class Payload(BaseModel):\n    summary: str")
    assert validate_json_with_model({"summary": "ok"}, model) == {"summary": "ok"}

###############################################################################
def test_pasted_pydantic_model_missing_field_error() -> None:
    model = parse_user_pydantic_model("class Payload(BaseModel):\n    summary: str")
    with pytest.raises(Exception):
        validate_json_with_model({}, model)

###############################################################################
def test_pasted_pydantic_model_incompatible_field_error() -> None:
    model = parse_user_pydantic_model("class Payload(BaseModel):\n    count: int")
    with pytest.raises(Exception):
        validate_json_with_model({"count": "bad"}, model)

###############################################################################
def test_unsupported_annotation_error() -> None:
    with pytest.raises(ValueError) as error:
        parse_user_pydantic_model("class Payload(BaseModel):\n    x: set[str]")
    assert "unsupported_annotation" in str(error.value)

###############################################################################
def test_structured_output_exposes_top_level_keys_through_result() -> None:
    result = _structured_output_executor({}, {"value": {"summary": "ok"}})
    assert result["result"]["summary"] == "ok"
    assert result["valid"] is True

###############################################################################
def test_structured_input_exposes_configured_json_object() -> None:
    value = {"vectors": [{"id": "point-1", "vector": [1.0, 0.0]}]}

    result = _structured_input_executor({"value": value}, {})

    assert result["result"] == value
    assert result["valid"] is True

###############################################################################
def test_structured_input_passes_through_json_array() -> None:
    value = [{"id": "point-1", "vector": [1.0, 0.0]}]

    result = _structured_input_executor({"value": value}, {})

    assert result["result"] == value
    assert result["schema"] == {}
    assert result["valid"] is True
