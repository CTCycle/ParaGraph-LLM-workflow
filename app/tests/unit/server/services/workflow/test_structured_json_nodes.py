from __future__ import annotations

import pytest

from server.services.workflow.node_handlers.structured import (
    _structured_input_executor,
    _structured_output_executor,
)
from server.services.workflow.structured_models import (
    infer_model_from_json,
    parse_user_pydantic_model,
    validate_json_with_model,
)

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
