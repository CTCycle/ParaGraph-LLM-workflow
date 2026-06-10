from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from server.domain.node_handler_structured import (
    JsonValidateRepairParameters,
    OutputParserParameters,
    StructuredInputParameters,
    StructuredOutputParameters,
)
from server.services.workflow.node_handlers.base import NodeHandler
from server.services.workflow.node_handlers.common import parse_json_if_possible
from server.services.workflow.structured_models import (
    infer_model_from_json,
    model_to_json_schema,
    parse_user_pydantic_model,
    validate_json_with_model,
    validation_error_payload,
)


###############################################################################
def _model_from_parameters(parameters: dict[str, Any], value: dict[str, Any]):
    mode = parameters.get("model_mode", "auto")
    if mode == "pydantic_source":
        return parse_user_pydantic_model(str(parameters.get("model_source") or ""))
    example = parameters.get("example_json") or value
    if not isinstance(example, dict):
        example = value
    return infer_model_from_json("StructuredPayload", example)


###############################################################################
def _validate_payload(value: Any, parameters: dict[str, Any]) -> dict[str, Any]:
    parsed = parse_json_if_possible(value)
    if not isinstance(parsed, dict):
        raise ValueError("structured payload must be a JSON object")
    model = _model_from_parameters(parameters, parsed)
    try:
        result = validate_json_with_model(parsed, model)
        return {
            "result": result,
            "schema": model_to_json_schema(model),
            "valid": True,
            "errors": [],
        }
    except ValidationError as exc:
        payload = validation_error_payload(exc)
        return {
            "result": parsed,
            "schema": model_to_json_schema(model),
            **payload,
        }


###############################################################################
def _structured_input_executor(
    parameters: dict[str, Any], inputs: dict[str, Any]
) -> dict[str, Any]:
    parsed = StructuredInputParameters.model_validate(parameters)
    _ = inputs
    return _validate_payload(parsed.value, parsed.model_dump(mode="json"))


###############################################################################
def _structured_output_executor(
    parameters: dict[str, Any], inputs: dict[str, Any]
) -> dict[str, Any]:
    parsed = StructuredOutputParameters.model_validate(parameters)
    value = inputs.get("value", inputs)
    return _validate_payload(value, parsed.model_dump(mode="json"))


###############################################################################
def _json_validate_repair_executor(
    parameters: dict[str, Any], inputs: dict[str, Any]
) -> dict[str, Any]:
    parsed = JsonValidateRepairParameters.model_validate(parameters)
    value = parse_json_if_possible(inputs.get("value", inputs))
    return _validate_payload(value, parsed.model_dump(mode="json"))


###############################################################################
def _output_parser_executor(
    parameters: dict[str, Any], inputs: dict[str, Any]
) -> dict[str, Any]:
    parsed = OutputParserParameters.model_validate(parameters)
    value = inputs.get("text", inputs.get("value", ""))
    if parsed.output_format == "text":
        return {"result": str(value)}
    result = parse_json_if_possible(value)
    if isinstance(result, str):
        raise ValueError("OUTPUT_PARSER expected valid JSON text")
    return {"result": result}


STRUCTURED_HANDLERS = {
    "structured_input": NodeHandler(
        executor=_structured_input_executor, parameter_model=StructuredInputParameters
    ),
    "structured_output": NodeHandler(
        executor=_structured_output_executor, parameter_model=StructuredOutputParameters
    ),
    "json_validate_repair": NodeHandler(
        executor=_json_validate_repair_executor,
        parameter_model=JsonValidateRepairParameters,
    ),
    "output_parser": NodeHandler(
        executor=_output_parser_executor, parameter_model=OutputParserParameters
    ),
}


__all__ = ["STRUCTURED_HANDLERS"]
