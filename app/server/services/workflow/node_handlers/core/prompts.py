from __future__ import annotations

import json
import re
from typing import Any

from server.domain.node_handler_core import PromptTemplateParameters
from server.services.workflow.node_handlers.common import coerce_text


def _prompt_executor(
    parameters: dict[str, Any], inputs: dict[str, Any]
) -> dict[str, Any]:
    _ = inputs
    return {"text": coerce_text(parameters.get("prompt_text", "")).strip()}


def _extract_template_record_text(record: dict[str, Any]) -> str:
    candidate = coerce_text(
        record.get("text") or record.get("content") or record.get("chunk") or ""
    )
    return candidate


def _coerce_template_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, list):
        if all(isinstance(item, dict) for item in value):
            parts = [_extract_template_record_text(item).strip() for item in value]
            text_parts = [item for item in parts if item]
            if text_parts:
                return "\n\n".join(text_parts)
        try:
            return json.dumps(value, indent=2, ensure_ascii=True, default=str)
        except Exception:  # noqa: BLE001
            return str(value)
    if isinstance(value, dict):
        extracted = _extract_template_record_text(value).strip()
        if extracted:
            return extracted
        try:
            return json.dumps(value, indent=2, ensure_ascii=True, default=str)
        except Exception:  # noqa: BLE001
            return str(value)
    try:
        return json.dumps(value, indent=2, ensure_ascii=True, default=str)
    except Exception:  # noqa: BLE001
        return str(value)


_PROMPT_TEMPLATE_PATTERN = re.compile(r"\{([A-Za-z_]\w*)\}")


def _collect_prompt_template_variable_maps(raw_variables: Any) -> list[dict[str, Any]]:
    if raw_variables is None:
        return []
    if isinstance(raw_variables, list):
        candidates = raw_variables
    else:
        candidates = [raw_variables]

    variable_maps: list[dict[str, Any]] = []
    for index, candidate in enumerate(candidates, start=1):
        if candidate is None:
            continue
        if not isinstance(candidate, dict):
            raise ValueError(
                f"PROMPT_TEMPLATE variables input #{index} must be an object"
            )
        variable_maps.append(candidate)
    return variable_maps


def _prompt_template_executor(
    parameters: dict[str, Any], inputs: dict[str, Any]
) -> dict[str, Any]:
    parsed = PromptTemplateParameters.model_validate(parameters)
    variable_maps = _collect_prompt_template_variable_maps(inputs.get("variables"))
    merged_variables: dict[str, str] = {}

    for variable_map in variable_maps:
        for key, raw_value in variable_map.items():
            variable_name = str(key).strip()
            if not variable_name:
                raise ValueError("PROMPT_TEMPLATE variables must use non-empty keys")
            if variable_name in merged_variables:
                raise ValueError(
                    f"PROMPT_TEMPLATE duplicate variable key: {variable_name}"
                )
            merged_variables[variable_name] = _coerce_template_value(raw_value)

    referenced_variables = set(_PROMPT_TEMPLATE_PATTERN.findall(parsed.template))
    missing_variables = sorted(
        name for name in referenced_variables if name not in merged_variables
    )
    if missing_variables:
        raise ValueError(
            f"PROMPT_TEMPLATE missing variable values for: {', '.join(missing_variables)}"
        )

    rendered = _PROMPT_TEMPLATE_PATTERN.sub(
        lambda match: merged_variables[match.group(1)],
        parsed.template,
    )
    return {"text": rendered}


def _image_input_executor(
    parameters: dict[str, Any], inputs: dict[str, Any]
) -> dict[str, Any]:
    _ = inputs
    return {"image": {"path": coerce_text(parameters.get("file_path", "")).strip()}}


__all__ = ["_image_input_executor", "_prompt_executor", "_prompt_template_executor"]

