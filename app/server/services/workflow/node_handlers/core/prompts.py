from __future__ import annotations

import re
from typing import Any

from jinja2 import StrictUndefined, Undefined
from jinja2.sandbox import SandboxedEnvironment

from server.domain.node_handler_core import PromptTemplateParameters
from server.services.workflow.node_handlers.common import (
    coerce_text,
    merge_named_variables,
    render_variable_value,
)


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
    return render_variable_value(value)


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


def _build_prompt_template_context(
    inputs: dict[str, Any],
    controllers: dict[str, Any],
    parameters: PromptTemplateParameters,
) -> dict[str, Any]:
    context = merge_named_variables(inputs.get("variables"))
    for payload in (inputs, controllers):
        for key, value in payload.items():
            if key == "variables":
                continue
            context[str(key)] = value
            if isinstance(value, dict):
                context.update(value)
    context["blocks"] = dict(parameters.reusable_blocks)
    return context


def _render_jinja_template(
    template: str,
    context: dict[str, Any],
    strict_variables: bool,
) -> str:
    environment = SandboxedEnvironment(
        autoescape=False,
        undefined=StrictUndefined if strict_variables else Undefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    try:
        return environment.from_string(template).render(context)
    except Exception as exc:  # noqa: BLE001
        raise ValueError(
            f"PROMPT_TEMPLATE failed to render Jinja template: {exc}"
        ) from exc


def _prompt_template_executor(
    parameters: dict[str, Any], inputs: dict[str, Any]
) -> dict[str, Any]:
    parsed = PromptTemplateParameters.model_validate(parameters)
    use_legacy_format = parsed.template_engine == "format" or (
        parsed.template
        and "{{" not in parsed.template
        and not parsed.system_template.strip()
        and not parsed.user_template.strip()
    )
    if not use_legacy_format:
        context = _build_prompt_template_context(inputs, {}, parsed)
        system = _render_jinja_template(
            parsed.system_template, context, parsed.strict_variables
        ).strip()
        user_source = parsed.user_template or parsed.template
        user = _render_jinja_template(
            user_source, context, parsed.strict_variables
        ).strip()
        rendered = "\n\n".join(part for part in (system, user) if part)
        return {
            "text": rendered,
            "system": system,
            "user": user,
            "variables": context,
        }

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
    return {
        "text": rendered,
        "system": "",
        "user": rendered,
        "variables": merged_variables,
    }


def _image_input_executor(
    parameters: dict[str, Any], inputs: dict[str, Any]
) -> dict[str, Any]:
    _ = inputs
    return {"image": {"path": coerce_text(parameters.get("file_path", "")).strip()}}


__all__ = ["_image_input_executor", "_prompt_executor", "_prompt_template_executor"]
