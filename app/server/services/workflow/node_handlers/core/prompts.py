from __future__ import annotations

from typing import Any

from jinja2 import StrictUndefined, Undefined
from jinja2.sandbox import SandboxedEnvironment

from server.domain.node_handler_core import PromptTemplateParameters
from server.common.utils.values import coerce_text, merge_named_variables

###############################################################################
def _prompt_executor(
    parameters: dict[str, Any], inputs: dict[str, Any]
) -> dict[str, Any]:
    _ = inputs
    return {"text": coerce_text(parameters.get("prompt_text", "")).strip()}

###############################################################################
def _extract_template_record_text(record: dict[str, Any]) -> str:
    candidate = coerce_text(
        record.get("text") or record.get("content") or record.get("chunk") or ""
    )
    return candidate

###############################################################################
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

###############################################################################
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

###############################################################################
def _prompt_template_executor(
    parameters: dict[str, Any], inputs: dict[str, Any]
) -> dict[str, Any]:
    parsed = PromptTemplateParameters.model_validate(parameters)
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

###############################################################################
def _image_input_executor(
    parameters: dict[str, Any], inputs: dict[str, Any]
) -> dict[str, Any]:
    _ = inputs
    return {"image": {"path": coerce_text(parameters.get("file_path", "")).strip()}}


__all__ = ["_image_input_executor", "_prompt_executor", "_prompt_template_executor"]
