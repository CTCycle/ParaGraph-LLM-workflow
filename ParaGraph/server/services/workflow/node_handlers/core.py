from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
except ImportError:  # Optional dependency for Hugging Face provider.
    torch = None
    AutoModelForCausalLM = None
    AutoTokenizer = None
from pydantic import BaseModel, Field, ValidationError, field_validator

from ParaGraph.server.common.constants import RESOURCES_PATH
from ParaGraph.server.entities.nodecatalog import ProviderModelDefinition
from ParaGraph.server.services.configuration import configuration_service
from ParaGraph.server.services.workflow.node_handlers.base import NodeHandler
from ParaGraph.server.services.workflow.node_handlers.common import (
    coerce_bool,
    coerce_int,
    coerce_text,
    normalize_provider_name,
    parse_json_value,
    validate_json_against_schema,
    validate_schema_definition,
)
from ParaGraph.server.services.workflow.provider import provider_service


ARTIFACT_ROOT = Path(RESOURCES_PATH) / "artifacts"
_HF_MODEL_CACHE: dict[str, tuple[Any, Any]] = {}


class PromptParameters(BaseModel):
    prompt_text: str = ""


class ImageInputParameters(BaseModel):
    file_path: str = ""


class ModelProviderParameters(BaseModel):
    provider: str = "ollama"
    model_name: str = ""


class ChatParameters(BaseModel):
    provider: str | None = None
    model_name: str | None = None
    context_window: int = Field(default=0, ge=0)
    max_tokens: int = Field(default=512, ge=1)
    use_reasoning: bool = False


class StructuredParameters(ChatParameters):
    response_schema: dict[str, Any]

    @field_validator("response_schema", mode="before")
    @classmethod
    def validate_schema(cls, value: Any) -> dict[str, Any]:
        schema = parse_json_value(value, "response_schema")
        validate_schema_definition(schema)
        return schema


class EmbeddingParameters(BaseModel):
    provider: str = "ollama"
    model_name: str = "nomic-embed-text"


class TextSplitParameters(BaseModel):
    delimiter: str = "\n"


class TemplateParameters(BaseModel):
    template: str = "{input}"


class StorageParameters(BaseModel):
    storage_path: str = ""


class RouterParameters(BaseModel):
    expected_value: str = ""


def _resolve_storage_file_path(raw_path: Any) -> Path:
    storage_path = coerce_text(raw_path).strip()
    if not storage_path:
        raise ValueError("storage_path is required. Select a local file path.")
    candidate = Path(storage_path).expanduser()
    if candidate.is_absolute():
        return candidate.resolve()
    # Keep legacy relative paths rooted in artifacts for existing workflows.
    return (ARTIFACT_ROOT / candidate).resolve()


def _prompt_executor(parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    _ = inputs
    return {"text": coerce_text(parameters.get("prompt_text", "")).strip()}


def _image_input_executor(parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    _ = inputs
    return {"image": {"path": coerce_text(parameters.get("file_path", "")).strip()}}


def _build_messages(parameters: dict[str, Any], inputs: dict[str, Any], *, structured_schema: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    user_prompt = coerce_text(inputs.get("user_prompt") or parameters.get("prompt") or parameters.get("prompt_text") or "").strip()
    system_prompt = coerce_text(inputs.get("system_prompt") or parameters.get("system_prompt") or "").strip()
    image_input = inputs.get("image")
    image_path = coerce_text(image_input.get("path") if isinstance(image_input, dict) else "").strip()

    if not user_prompt and not image_path:
        raise ValueError("Model nodes require a user prompt or an image input")

    messages: list[dict[str, Any]] = []
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


def _build_generation_options(parameters: dict[str, Any], *, include_context_window: bool) -> dict[str, Any]:
    max_tokens = max(1, coerce_int(parameters.get("max_tokens"), 512))
    options: dict[str, Any] = {"max_output_tokens": max_tokens}
    if include_context_window:
        context_window = max(0, coerce_int(parameters.get("context_window"), 0))
        if context_window > 0:
            options["num_ctx"] = context_window
    return options


def _resolve_model_selection(parameters: dict[str, Any], inputs: dict[str, Any]) -> ProviderModelDefinition:
    _ = parameters
    model_input = inputs.get("model")
    if model_input is None:
        raise ValueError("LLM nodes require a connected model provider controller")
    try:
        return ProviderModelDefinition.model_validate(model_input)
    except ValidationError as exc:
        raise ValueError("model controller must be a valid model handle") from exc


def _run_huggingface_chat(
    *,
    model_name: str,
    messages: list[dict[str, Any]],
    max_tokens: int,
    context_window: int,
    access_token: str,
) -> str:

    if torch is None or AutoTokenizer is None or AutoModelForCausalLM is None:
        raise ValueError("Hugging Face support requires installing torch and transformers")
    if model_name not in _HF_MODEL_CACHE:
        tokenizer = AutoTokenizer.from_pretrained(model_name, token=access_token)
        model = AutoModelForCausalLM.from_pretrained(
            model_name,
            token=access_token,
            torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
            device_map="auto" if torch.cuda.is_available() else None,
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
        return decoded[len(prompt_text):].strip()
    return decoded.strip()


def _execute_model_node(
    *,
    provider: str,
    model_name: str,
    parameters: dict[str, Any],
    inputs: dict[str, Any],
    structured_output: bool,
) -> dict[str, Any]:
    schema = parameters.get("response_schema") if structured_output else None
    messages = _build_messages(parameters, inputs, structured_schema=schema)
    include_context_window = provider in {"ollama", "huggingface"}
    options = _build_generation_options(parameters, include_context_window=include_context_window)
    max_tokens = int(options.get("max_output_tokens", 512))
    context_window = int(options.get("num_ctx", 0))
    image_input = inputs.get("image")
    requires_image = bool(coerce_text(image_input.get("path") if isinstance(image_input, dict) else "").strip())
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
        )

    if structured_output:
        parsed = parse_json_value(text, "structured response")
        if not isinstance(schema, dict):
            raise ValueError("Structured response schema is required")
        validate_json_against_schema(parsed, schema)
        return {"result": parsed}
    return {"response": text}


def _model_provider_executor(parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    _ = inputs
    provider = normalize_provider_name(parameters.get("provider"), default="ollama")
    model_name = coerce_text(parameters.get("model_name")).strip()
    if not model_name and provider == "ollama":
        model_name = coerce_text(configuration_service.load_configuration().ollama.chat_model).strip()
    if not model_name:
        raise ValueError("MODEL_PROVIDER requires a model_name")
    return {"model": provider_service.build_model_definition(provider, model_name).model_dump(mode="json")}


def _llm_chat_executor(parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    selection = _resolve_model_selection(parameters, inputs)
    return _execute_model_node(
        provider=selection.provider,
        model_name=selection.model,
        parameters=parameters,
        inputs=inputs,
        structured_output=False,
    )


def _llm_structured_executor(parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    selection = _resolve_model_selection(parameters, inputs)
    return _execute_model_node(
        provider=selection.provider,
        model_name=selection.model,
        parameters=parameters,
        inputs=inputs,
        structured_output=True,
    )


def _embedding_executor(parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    text = coerce_text(inputs.get("text") or "").strip()
    if not text:
        raise ValueError("EMBEDDING_MODEL requires text input")
    provider = normalize_provider_name(parameters.get("provider"), default="ollama")
    model_name = coerce_text(parameters.get("model_name") or "nomic-embed-text").strip() or "nomic-embed-text"
    return {"embedding": provider_service.embed_text(provider=provider, model=model_name, text=text)}


def _tokenize_executor(parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    _ = parameters
    text = coerce_text(inputs.get("text") or "")
    tokens = [index for index, part in enumerate(text.split(), start=1) if part]
    return {"tokens": tokens}


def _text_split_executor(parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    text = coerce_text(inputs.get("text") or "")
    delimiter = coerce_text(parameters.get("delimiter") or "\n")
    return {"segments": [segment.strip() for segment in text.split(delimiter) if segment.strip()]}


def _template_format_executor(parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    template = coerce_text(parameters.get("template") or "{input}")
    value = coerce_text(inputs.get("input") or "")
    return {"text": template.replace("{input}", value)}


def _save_text_executor(parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    text = coerce_text(inputs.get("text") or "")
    destination = _resolve_storage_file_path(parameters.get("storage_path"))
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(text, encoding="utf-8")
    artifact_root = ARTIFACT_ROOT.resolve()
    try:
        output_path = str(destination.relative_to(artifact_root))
    except ValueError:
        output_path = str(destination)
    return {"artifact": {"path": output_path}}


def _load_text_executor(parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    _ = inputs
    source = _resolve_storage_file_path(parameters.get("storage_path"))
    if not source.exists():
        raise ValueError(f"Text file not found: {source}")
    return {"text": source.read_text(encoding="utf-8")}


def _if_executor(parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    _ = parameters
    return {"result": inputs.get("true_value") if bool(inputs.get("condition")) else inputs.get("false_value")}


def _router_executor(parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    value = inputs.get("value")
    expected = coerce_text(parameters.get("expected_value") or "")
    if coerce_text(value) == expected:
        return {"matched": value, "unmatched": None}
    return {"matched": None, "unmatched": value}


CORE_HANDLERS = {
    "prompt": NodeHandler(executor=_prompt_executor, parameter_model=PromptParameters),
    "user_prompt": NodeHandler(executor=_prompt_executor, parameter_model=PromptParameters),
    "system_prompt": NodeHandler(executor=_prompt_executor, parameter_model=PromptParameters),
    "image_input": NodeHandler(executor=_image_input_executor, parameter_model=ImageInputParameters),
    "model_provider": NodeHandler(executor=_model_provider_executor, parameter_model=ModelProviderParameters),
    "llm_chat": NodeHandler(executor=_llm_chat_executor, parameter_model=ChatParameters),
    "llm_structured": NodeHandler(executor=_llm_structured_executor, parameter_model=StructuredParameters),
    "embedding_model": NodeHandler(executor=_embedding_executor, parameter_model=EmbeddingParameters),
    "tokenize": NodeHandler(executor=_tokenize_executor),
    "text_split": NodeHandler(executor=_text_split_executor, parameter_model=TextSplitParameters),
    "template_format": NodeHandler(executor=_template_format_executor, parameter_model=TemplateParameters),
    "save_text": NodeHandler(executor=_save_text_executor, parameter_model=StorageParameters),
    "load_text": NodeHandler(executor=_load_text_executor, parameter_model=StorageParameters),
    "if": NodeHandler(executor=_if_executor),
    "router": NodeHandler(executor=_router_executor, parameter_model=RouterParameters),
}


