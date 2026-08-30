from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from server.common.utils.values import parse_json_if_possible


StructuredModelMode = Literal["auto", "pydantic_source"]


###############################################################################
class PydanticModelParameters(BaseModel):
    model_mode: StructuredModelMode = "auto"
    model_source: str = ""
    example_json: dict[str, Any] = Field(default_factory=dict)

    # -------------------------------------------------------------------------
    @field_validator("example_json", mode="before")
    @classmethod
    def validate_example_json(cls, value: Any) -> dict[str, Any]:
        parsed = parse_json_if_possible(value)
        if parsed is None:
            return {}
        if not isinstance(parsed, dict):
            raise ValueError("example_json must be a JSON object")
        return parsed


###############################################################################
class StructuredInputParameters(PydanticModelParameters):
    value: dict[str, Any] = Field(default_factory=dict)

    # -------------------------------------------------------------------------
    @field_validator("value", mode="before")
    @classmethod
    def validate_value(cls, value: Any) -> dict[str, Any]:
        parsed = parse_json_if_possible(value)
        if not isinstance(parsed, dict):
            raise ValueError("value must be a JSON object")
        return parsed


###############################################################################
class StructuredOutputParameters(PydanticModelParameters):
    pass


###############################################################################
class OutputParserParameters(BaseModel):
    output_format: Literal["json", "text"] = "json"
