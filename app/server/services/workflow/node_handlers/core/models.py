from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from server.contracts.chat_history import ChatHistoryHandle
from server.contracts.node_catalog import ProviderModelDefinition
from server.contracts.node_handler_core import ModelProviderParameters
from server.services.configuration import configuration_service
from server.services.workflow.chat_history import chat_history_service
from server.common.utils.values import (
    coerce_bool,
    coerce_int,
    coerce_text,
    normalize_provider_name,
    parse_json_value,
    validate_json_against_schema,
)
from server.services.workflow.structured_models import (
    infer_model_from_json,
    model_to_json_schema,
    parse_user_pydantic_model,
    validate_json_with_model,
    validation_error_payload,
)
from server.services.workflow.node_handlers.core.huggingface_runtime import (
    load_huggingface_modules,
)
from server.services.workflow.provider import provider_service


_HF_MODEL_CACHE: dict[str, tuple[Any, Any]] = {}

###############################################################################
def _extract_prompt_inputs(
    parameters: dict[str, Any], inputs: dict[str, Any]
) -> tuple[str, str, str]:
    user_prompt = coerce_text(
        inputs.get("user_prompt")
        or parameters.get("prompt")
        or parameters.get("prompt_text")
        or ""
    ).strip()
    system_prompt = coerce_text(
        inputs.get("system_prompt") or parameters.get("system_prompt") or ""
    ).strip()
    image_input = inputs.get("image")
    image_path = coerce_text(
        image_input.get("path") if isinstance(image_input, dict) else ""
    ).strip()
    return user_prompt, system_prompt, image_path

###############################################################################
def _build_messages(
    parameters: dict[str, Any],
    inputs: dict[str, Any],
    *,
    structured_schema: dict[str, Any] | None = None,
    history_text: str = "",
) -> list[dict[str, Any]]:
    user_prompt, system_prompt, image_path = _extract_prompt_inputs(parameters, inputs)

    if not user_prompt and not image_path:
        raise ValueError("Model nodes require a user prompt or an image input")

    messages: list[dict[str, Any]] = []
    if history_text:
        messages.append({"role": "system", "content": history_text})
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})

    if coerce_bool(parameters.get("use_reasoning", False)):
        messages.append(
            {
                "role": "system",
                "content": "Reason carefully before responding, but return only the final answer in the expected format.",
            }
        )

    if structured_schema is not None:
        schema_text = json.dumps(structured_schema, sort_keys=True)
        messages.append(
            {
                "role": "system",
                "content": f"Return only valid JSON that conforms exactly to this JSON Schema: {schema_text}",
            }
        )

    user_content: list[dict[str, str]] = []
    if user_prompt:
        user_content.append({"type": "text", "text": user_prompt})
    if image_path:
        user_content.append({"type": "image_path", "path": image_path})

    if len(user_content) == 1 and user_content[0]["type"] == "text":
        messages.append({"role": "user", "content": user_content[0]["text"]})
    else:
        messages.append({"role": "user", "content": user_content})
    return messages

###############################################################################
def _build_generation_options(
    parameters: dict[str, Any], *, include_context_window: bool
) -> dict[str, Any]:
    max_tokens = max(1, coerce_int(parameters.get("max_tokens"), 512))
    options: dict[str, Any] = {"max_output_tokens": max_tokens}
    options["use_reasoning"] = coerce_bool(parameters.get("use_reasoning", False))
    if include_context_window:
        context_window = max(0, coerce_int(parameters.get("context_window"), 0))
        if context_window > 0:
            options["num_ctx"] = context_window
    return options

###############################################################################
def _resolve_model_selection(
    parameters: dict[str, Any], inputs: dict[str, Any]
) -> ProviderModelDefinition:
    _ = parameters
    model_input = inputs.get("model")
    if model_input is None:
        raise ValueError("LLM nodes require a connected model provider controller")
    try:
        return ProviderModelDefinition.model_validate(model_input)
    except ValidationError as exc:
        raise ValueError("model controller must be a valid model handle") from exc

###############################################################################
def _run_huggingface_chat(
    *,
    model_name: str,
    messages: list[dict[str, Any]],
    max_tokens: int,
    context_window: int,
    access_token: str,
) -> str:
    torch_module, auto_model_for_causal_lm, auto_tokenizer = load_huggingface_modules()
    if model_name not in _HF_MODEL_CACHE:
        tokenizer = auto_tokenizer.from_pretrained(model_name, token=access_token)
        model = auto_model_for_causal_lm.from_pretrained(
            model_name,
            token=access_token,
            torch_dtype=torch_module.float16
            if torch_module.cuda.is_available()
            else torch_module.float32,
            device_map="auto" if torch_module.cuda.is_available() else None,
        )
        _HF_MODEL_CACHE[model_name] = (tokenizer, model)

    tokenizer, model = _HF_MODEL_CACHE[model_name]
    prompt_text = "\n\n".join(
        f"{str(message.get('role', 'user')).upper()}: {coerce_text(message.get('content', ''))}"
        for message in messages
    )
    encoded = tokenizer(prompt_text, return_tensors="pt")
    if context_window > 0:
        encoded = {key: value[:, -context_window:] for key, value in encoded.items()}

    target_device = getattr(model, "device", None)
    if target_device is not None:
        encoded = {key: value.to(target_device) for key, value in encoded.items()}
    generated = model.generate(**encoded, max_new_tokens=max_tokens)
    decoded = tokenizer.decode(generated[0], skip_special_tokens=True)
    if decoded.startswith(prompt_text):
        return decoded[len(prompt_text) :].strip()
    return decoded.strip()

###############################################################################
def _execute_model_node(
    *,
    provider: str,
    model_name: str,
    parameters: dict[str, Any],
    inputs: dict[str, Any],
    structured_output: bool,
    timeout_s: float | None,
) -> dict[str, Any]:
    schema = parameters.get("response_schema") if structured_output else None
    history_handle_input = inputs.get("history")
    history_handle: ChatHistoryHandle | None = None
    if history_handle_input is not None:
        try:
            history_handle = ChatHistoryHandle.model_validate(history_handle_input)
        except ValidationError as exc:
            raise ValueError(
                "history controller must be a valid chat history handle"
            ) from exc

    history_text = (
        chat_history_service.format_history_for_prompt(history_handle)
        if history_handle is not None
        else ""
    )
    user_prompt, system_prompt, _image_path = _extract_prompt_inputs(parameters, inputs)
    messages = _build_messages(
        parameters,
        inputs,
        structured_schema=schema,
        history_text=history_text,
    )
    include_context_window = provider in {"ollama", "huggingface", "lmstudio", "llama"}
    options = _build_generation_options(
        parameters, include_context_window=include_context_window
    )
    max_tokens = int(options.get("max_output_tokens", 512))
    context_window = int(options.get("num_ctx", 0))
    image_input = inputs.get("image")
    requires_image = bool(
        coerce_text(
            image_input.get("path") if isinstance(image_input, dict) else ""
        ).strip()
    )
    use_reasoning = coerce_bool(parameters.get("use_reasoning", False))

    provider_service.validate_model_request(
        provider=provider,
        model=model_name,
        structured_output=structured_output,
        requires_image=requires_image,
        use_reasoning=use_reasoning,
    )

    if provider == "huggingface":
        access_keys = configuration_service.load_configuration().access_keys
        hf_token = ""
        for item in access_keys:
            if item.provider.lower() == "huggingface" and item.api_key:
                hf_token = item.api_key
                break
        text = _run_huggingface_chat(
            model_name=model_name,
            messages=messages,
            max_tokens=max_tokens,
            context_window=context_window,
            access_token=hf_token,
        )
    else:
        text = provider_service.chat(
            provider=provider,
            model=model_name,
            messages=messages,
            response_format="json" if structured_output else None,
            options=options,
            timeout_s=timeout_s,
        )

    if structured_output:
        parsed = parse_json_value(text, "structured response")
        model_mode = str(parameters.get("model_mode") or "schema")
        validation_errors: list[dict[str, Any]] = []
        if model_mode == "pydantic_source":
            model = parse_user_pydantic_model(str(parameters.get("model_source") or ""))
            try:
                parsed = validate_json_with_model(parsed, model)
            except ValidationError as exc:
                payload = validation_error_payload(exc)
                validation_errors = payload["errors"]
            schema = model_to_json_schema(model)
        elif model_mode == "auto" and isinstance(parsed, dict):
            model = infer_model_from_json("StructuredResponse", parsed)
            parsed = validate_json_with_model(parsed, model)
            schema = model_to_json_schema(model)
        else:
            if not isinstance(schema, dict):
                raise ValueError("Structured response schema is required")
            validate_json_against_schema(parsed, schema)
        if history_handle is not None and not history_handle.execution_owned:
            chat_history_service.append_exchange(
                history_handle,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                assistant_output=chat_history_service.serialize_structured_output(
                    parsed
                ),
            )
        return {
            "result": parsed,
            "schema": schema,
            "valid": not validation_errors,
            "errors": validation_errors,
        }
    if history_handle is not None and not history_handle.execution_owned:
        chat_history_service.append_exchange(
            history_handle,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            assistant_output=text,
        )
    return {"response": text}

###############################################################################
def _model_provider_executor(
    parameters: dict[str, Any], inputs: dict[str, Any]
) -> dict[str, Any]:
    _ = inputs
    parsed = ModelProviderParameters.model_validate(parameters)
    provider = normalize_provider_name(parsed.provider, default="ollama")
    model_name = coerce_text(parsed.model_name).strip()
    timeout_seconds = float(parsed.timeout_seconds)
    if not model_name and provider == "ollama":
        model_name = coerce_text(
            configuration_service.load_configuration().ollama.chat_model
        ).strip()
    if not model_name and provider in {"lmstudio", "llama"}:
        for item in configuration_service.load_configuration().access_keys:
            if item.provider == provider and isinstance(item.metadata, dict):
                model_name = coerce_text(item.metadata.get("chat_model")).strip()
                break
    if not model_name:
        raise ValueError("MODEL_PROVIDER requires a model_name")
    return {
        "model": provider_service.build_model_definition(
            provider,
            model_name,
            timeout_s=timeout_seconds,
        ).model_dump(mode="json")
    }

###############################################################################
def _llm_chat_executor(
    parameters: dict[str, Any], inputs: dict[str, Any]
) -> dict[str, Any]:
    selection = _resolve_model_selection(parameters, inputs)
    return _execute_model_node(
        provider=selection.provider,
        model_name=selection.model,
        parameters=parameters,
        inputs=inputs,
        structured_output=False,
        timeout_s=selection.timeout_s,
    )

###############################################################################
def _llm_structured_executor(
    parameters: dict[str, Any], inputs: dict[str, Any]
) -> dict[str, Any]:
    selection = _resolve_model_selection(parameters, inputs)
    return _execute_model_node(
        provider=selection.provider,
        model_name=selection.model,
        parameters=parameters,
        inputs=inputs,
        structured_output=True,
        timeout_s=selection.timeout_s,
    )


__all__ = [
    "_llm_chat_executor",
    "_llm_structured_executor",
    "_model_provider_executor",
]
