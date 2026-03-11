from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from ParaGraph.server.common.constants import RESOURCES_PATH
from ParaGraph.server.entities.nodecatalog import NodeCatalogResponse, NodeManifest
from ParaGraph.server.services.configuration import configuration_service
from ParaGraph.server.services.workflow.provider import provider_service


Executor = Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]]

NODE_ROOT = Path(RESOURCES_PATH) / "nodes"
ARTIFACT_ROOT = Path(RESOURCES_PATH) / "artifacts"
_HF_MODEL_CACHE: dict[str, tuple[Any, Any]] = {}

MODEL_NODE_IDS = {
    "OLLAMA_LLM_CHAT",
    "CLOUD_LLM_CHAT",
    "HUGGINGFACE_LLM_CHAT",
    "OLLAMA_STRUCTURED_RESPONSE",
    "CLOUD_STRUCTURED_RESPONSE",
    "HUGGINGFACE_STRUCTURED_RESPONSE",
}
STRUCTURED_NODE_IDS = {
    "OLLAMA_STRUCTURED_RESPONSE",
    "CLOUD_STRUCTURED_RESPONSE",
    "HUGGINGFACE_STRUCTURED_RESPONSE",
}


def _coerce_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    return json.dumps(value)


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _coerce_int(value: Any, default: int) -> int:
    if value is None:
        return default
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _parse_json_value(value: Any, label: str) -> Any:
    if isinstance(value, (dict, list, int, float, bool)) or value is None:
        return value
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{label} must not be empty")
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label} must be valid JSON") from exc


def _validate_schema_definition(schema: Any, path: str = "$") -> None:
    if not isinstance(schema, dict):
        raise ValueError("response_schema must be a JSON object")

    allowed_keys = {"type", "properties", "required", "items", "additionalProperties", "enum"}
    unsupported = sorted(set(schema) - allowed_keys)
    if unsupported:
        raise ValueError(f"Unsupported JSON Schema keys at {path}: {', '.join(unsupported)}")

    schema_type = schema.get("type")
    if schema_type is not None and schema_type not in {"object", "array", "string", "number", "integer", "boolean", "null"}:
        raise ValueError(f"Unsupported JSON Schema type at {path}: {schema_type}")

    properties = schema.get("properties")
    if properties is not None:
        if not isinstance(properties, dict):
            raise ValueError(f"properties at {path} must be an object")
        for key, value in properties.items():
            _validate_schema_definition(value, f"{path}.properties.{key}")

    required = schema.get("required")
    if required is not None:
        if not isinstance(required, list) or not all(isinstance(item, str) for item in required):
            raise ValueError(f"required at {path} must be an array of strings")

    if "items" in schema:
        _validate_schema_definition(schema["items"], f"{path}.items")

    additional_properties = schema.get("additionalProperties")
    if additional_properties is not None and not isinstance(additional_properties, bool):
        raise ValueError(f"additionalProperties at {path} must be a boolean")

    enum = schema.get("enum")
    if enum is not None and not isinstance(enum, list):
        raise ValueError(f"enum at {path} must be an array")


def _validate_json_against_schema(value: Any, schema: dict[str, Any], path: str = "$") -> None:
    schema_type = schema.get("type")
    if schema_type == "object":
        if not isinstance(value, dict):
            raise ValueError(f"Structured output at {path} must be an object")
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        additional_properties = schema.get("additionalProperties", True)
        for key in required:
            if key not in value:
                raise ValueError(f"Structured output is missing required property '{key}' at {path}")
        if additional_properties is False:
            extra = sorted(set(value) - set(properties))
            if extra:
                raise ValueError(f"Structured output contains unexpected properties at {path}: {', '.join(extra)}")
        for key, child_schema in properties.items():
            if key in value:
                _validate_json_against_schema(value[key], child_schema, f"{path}.{key}")
    elif schema_type == "array":
        if not isinstance(value, list):
            raise ValueError(f"Structured output at {path} must be an array")
        item_schema = schema.get("items")
        if item_schema is not None:
            for index, item in enumerate(value):
                _validate_json_against_schema(item, item_schema, f"{path}[{index}]")
    elif schema_type == "string":
        if not isinstance(value, str):
            raise ValueError(f"Structured output at {path} must be a string")
    elif schema_type == "number":
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ValueError(f"Structured output at {path} must be a number")
    elif schema_type == "integer":
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValueError(f"Structured output at {path} must be an integer")
    elif schema_type == "boolean":
        if not isinstance(value, bool):
            raise ValueError(f"Structured output at {path} must be a boolean")
    elif schema_type == "null":
        if value is not None:
            raise ValueError(f"Structured output at {path} must be null")

    if "enum" in schema and value not in schema["enum"]:
        raise ValueError(f"Structured output at {path} must match one of the allowed enum values")


def _prompt_executor(parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    _ = inputs
    return {"text": _coerce_text(parameters.get("prompt_text", "")).strip()}


def _image_input_executor(parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    _ = inputs
    path = _coerce_text(parameters.get("file_path", "")).strip()
    return {"image": {"path": path}}


def _build_messages(parameters: dict[str, Any], inputs: dict[str, Any], *, structured_schema: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    user_prompt = _coerce_text(inputs.get("user_prompt") or parameters.get("prompt") or parameters.get("prompt_text") or "").strip()
    system_prompt = _coerce_text(inputs.get("system_prompt") or parameters.get("system_prompt") or "").strip()
    image_input = inputs.get("image")
    image_path = _coerce_text(image_input.get("path") if isinstance(image_input, dict) else "").strip()

    if not user_prompt and not image_path:
        raise ValueError("Model nodes require a user prompt or an image input")

    messages: list[dict[str, Any]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})

    if _coerce_bool(parameters.get("use_reasoning", False)):
        messages.append(
            {
                "role": "system",
                "content": (
                    "Reason carefully before responding, but return only the final answer in the expected format."
                ),
            }
        )

    if structured_schema is not None:
        schema_text = json.dumps(structured_schema, sort_keys=True)
        messages.append(
            {
                "role": "system",
                "content": (
                    "Return only valid JSON that conforms exactly to this JSON Schema: "
                    f"{schema_text}"
                ),
            }
        )

    user_content: list[dict[str, str]] = []
    if user_prompt:
        user_content.append({"type": "text", "text": user_prompt})
    if image_path:
        user_content.append({"type": "image_path", "path": image_path})

    if not user_content:
        raise ValueError("Unable to build the user message content")
    if len(user_content) == 1 and user_content[0]["type"] == "text":
        messages.append({"role": "user", "content": user_content[0]["text"]})
    else:
        messages.append({"role": "user", "content": user_content})
    return messages


def _build_generation_options(parameters: dict[str, Any], *, include_context_window: bool) -> dict[str, Any]:
    max_tokens = max(1, _coerce_int(parameters.get("max_tokens"), 512))
    options: dict[str, Any] = {"max_output_tokens": max_tokens}
    if include_context_window:
        context_window = max(0, _coerce_int(parameters.get("context_window"), 0))
        if context_window > 0:
            options["num_ctx"] = context_window
    return options


def _get_schema(parameters: dict[str, Any]) -> dict[str, Any]:
    schema = _parse_json_value(parameters.get("response_schema"), "response_schema")
    _validate_schema_definition(schema)
    return schema


def _run_huggingface_chat(
    *,
    model_name: str,
    messages: list[dict[str, Any]],
    max_tokens: int,
    context_window: int,
    access_token: str,
) -> str:
    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except ImportError as exc:
        raise ValueError(
            "HuggingFace execution requires the optional dependencies 'transformers' and 'torch'"
        ) from exc

    cache_key = model_name
    if cache_key not in _HF_MODEL_CACHE:
        tokenizer = AutoTokenizer.from_pretrained(model_name, token=access_token)
        model = AutoModelForCausalLM.from_pretrained(
            model_name,
            token=access_token,
            torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
            device_map="auto" if torch.cuda.is_available() else None,
        )
        _HF_MODEL_CACHE[cache_key] = (tokenizer, model)

    tokenizer, model = _HF_MODEL_CACHE[cache_key]
    prompt_text = "\n\n".join(
        f"{str(message.get('role', 'user')).upper()}: {_coerce_text(message.get('content', ''))}"
        for message in messages
    )
    encoded = tokenizer(prompt_text, return_tensors="pt")
    if context_window > 0:
        encoded = {
            key: value[:, -context_window:]
            for key, value in encoded.items()
        }

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
    schema = _get_schema(parameters) if structured_output else None
    messages = _build_messages(parameters, inputs, structured_schema=schema)
    include_context_window = provider in {"ollama", "huggingface"}
    options = _build_generation_options(parameters, include_context_window=include_context_window)
    max_tokens = int(options.get("max_output_tokens", 512))
    context_window = int(options.get("num_ctx", 0))
    requires_image = bool(_coerce_text((inputs.get("image") or {}).get("path") if isinstance(inputs.get("image"), dict) else "").strip())
    use_reasoning = _coerce_bool(parameters.get("use_reasoning", False))

    provider_service.validate_model_request(
        provider=provider,
        model=model_name,
        structured_output=structured_output,
        requires_image=requires_image,
        use_reasoning=use_reasoning,
    )

    if provider == "huggingface":
        access_key = configuration_service.load_configuration().access_keys
        hf_token = ""
        for item in access_key:
            if item.provider in {"huggingface", "HUGGINGFACE"} and item.api_key:
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
        parsed = _parse_json_value(text, "structured response")
        if schema is None:
            raise ValueError("Structured response schema is required")
        _validate_json_against_schema(parsed, schema)
        return {"result": parsed}
    return {"response": text}


def _ollama_llm_chat_executor(parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    model_name = _coerce_text(parameters.get("model_name") or configuration_service.load_configuration().ollama.chat_model).strip()
    if not model_name:
        raise ValueError("OLLAMA_LLM_CHAT requires a model_name")
    return _execute_model_node(
        provider="ollama",
        model_name=model_name,
        parameters=parameters,
        inputs=inputs,
        structured_output=False,
    )


def _cloud_llm_chat_executor(parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    provider = _coerce_text(parameters.get("provider", "openai")).strip().lower()
    if provider == "anthropic":
        provider = "claude"
    model_name = _coerce_text(parameters.get("model_name")).strip()
    if not model_name:
        raise ValueError("CLOUD_LLM_CHAT requires a model_name")
    return _execute_model_node(
        provider=provider,
        model_name=model_name,
        parameters=parameters,
        inputs=inputs,
        structured_output=False,
    )


def _huggingface_llm_chat_executor(parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    model_name = _coerce_text(parameters.get("model_name")).strip()
    if not model_name:
        raise ValueError("HUGGINGFACE_LLM_CHAT requires a model_name")
    return _execute_model_node(
        provider="huggingface",
        model_name=model_name,
        parameters=parameters,
        inputs=inputs,
        structured_output=False,
    )


def _ollama_structured_response_executor(parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    model_name = _coerce_text(parameters.get("model_name") or configuration_service.load_configuration().ollama.chat_model).strip()
    if not model_name:
        raise ValueError("OLLAMA_STRUCTURED_RESPONSE requires a model_name")
    return _execute_model_node(
        provider="ollama",
        model_name=model_name,
        parameters=parameters,
        inputs=inputs,
        structured_output=True,
    )


def _cloud_structured_response_executor(parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    provider = _coerce_text(parameters.get("provider", "openai")).strip().lower()
    if provider == "anthropic":
        provider = "claude"
    model_name = _coerce_text(parameters.get("model_name")).strip()
    if not model_name:
        raise ValueError("CLOUD_STRUCTURED_RESPONSE requires a model_name")
    return _execute_model_node(
        provider=provider,
        model_name=model_name,
        parameters=parameters,
        inputs=inputs,
        structured_output=True,
    )


def _huggingface_structured_response_executor(parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    model_name = _coerce_text(parameters.get("model_name")).strip()
    if not model_name:
        raise ValueError("HUGGINGFACE_STRUCTURED_RESPONSE requires a model_name")
    return _execute_model_node(
        provider="huggingface",
        model_name=model_name,
        parameters=parameters,
        inputs=inputs,
        structured_output=True,
    )


def _embedding_executor(parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    text = _coerce_text(inputs.get("text") or "").strip()
    if not text:
        raise ValueError("EMBEDDING_MODEL requires text input")
    provider = _coerce_text(parameters.get("provider", "ollama")).lower()
    model_name = _coerce_text(parameters.get("model_name", "nomic-embed-text"))
    return {"embedding": provider_service.embed_text(provider=provider, model=model_name, text=text)}


def _tokenize_executor(parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    _ = parameters
    text = _coerce_text(inputs.get("text") or "")
    tokens = [index for index, part in enumerate(text.split(), start=1) if part]
    return {"tokens": tokens}


def _text_split_executor(parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    text = _coerce_text(inputs.get("text") or "")
    delimiter = _coerce_text(parameters.get("delimiter", "\n"))
    segments = [segment.strip() for segment in text.split(delimiter) if segment.strip()]
    return {"segments": segments}


def _template_format_executor(parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    template = _coerce_text(parameters.get("template", "{input}"))
    value = _coerce_text(inputs.get("input") or "")
    return {"text": template.replace("{input}", value)}


def _save_text_executor(parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    text = _coerce_text(inputs.get("text") or "")
    storage_path = _coerce_text(parameters.get("storage_path", "saved_text.txt")).strip() or "saved_text.txt"
    destination = (ARTIFACT_ROOT / storage_path).resolve()
    if ARTIFACT_ROOT.resolve() not in destination.parents and destination != ARTIFACT_ROOT.resolve():
        raise ValueError("storage_path must stay inside ParaGraph/resources/artifacts")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(text, encoding="utf-8")
    return {"artifact": {"path": str(destination.relative_to(ARTIFACT_ROOT.resolve()))}}


def _load_text_executor(parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    _ = inputs
    storage_path = _coerce_text(parameters.get("storage_path", "saved_text.txt")).strip() or "saved_text.txt"
    source = (ARTIFACT_ROOT / storage_path).resolve()
    if ARTIFACT_ROOT.resolve() not in source.parents and source != ARTIFACT_ROOT.resolve():
        raise ValueError("storage_path must stay inside ParaGraph/resources/artifacts")
    if not source.exists():
        raise ValueError(f"Text artifact not found: {storage_path}")
    return {"text": source.read_text(encoding="utf-8")}


def _text_output_executor(parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    _ = parameters
    return {"result": _coerce_text(inputs.get("text") or "")}


def _image_output_executor(parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    _ = parameters
    image = inputs.get("image") or {}
    return {"result": image}


def _if_executor(parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    _ = parameters
    condition = bool(inputs.get("condition"))
    return {"result": inputs.get("true_value") if condition else inputs.get("false_value")}


def _router_executor(parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    value = inputs.get("value")
    expected = _coerce_text(parameters.get("expected_value", ""))
    if _coerce_text(value) == expected:
        return {"matched": value, "unmatched": None}
    return {"matched": None, "unmatched": value}


EXECUTORS: dict[str, Executor] = {
    "user_prompt": _prompt_executor,
    "system_prompt": _prompt_executor,
    "image_input": _image_input_executor,
    "ollama_llm_chat": _ollama_llm_chat_executor,
    "cloud_llm_chat": _cloud_llm_chat_executor,
    "huggingface_llm_chat": _huggingface_llm_chat_executor,
    "ollama_structured_response": _ollama_structured_response_executor,
    "cloud_structured_response": _cloud_structured_response_executor,
    "huggingface_structured_response": _huggingface_structured_response_executor,
    "embedding_model": _embedding_executor,
    "tokenize": _tokenize_executor,
    "text_split": _text_split_executor,
    "template_format": _template_format_executor,
    "save_text": _save_text_executor,
    "load_text": _load_text_executor,
    "text_output": _text_output_executor,
    "image_output": _image_output_executor,
    "if": _if_executor,
    "router": _router_executor,
}


class NodeRegistry:
    def __init__(self) -> None:
        self._definitions: dict[tuple[str, int], NodeManifest] = {}
        NODE_ROOT.mkdir(parents=True, exist_ok=True)
        ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
        self.reload()

    def reload(self) -> None:
        definitions: dict[tuple[str, int], NodeManifest] = {}
        for path in sorted(NODE_ROOT.glob('*.json')):
            manifest = NodeManifest.model_validate_json(path.read_text(encoding='utf-8'))
            key = (manifest.id, manifest.version)
            if key in definitions:
                raise ValueError(f"Duplicate node manifest detected for {manifest.id} v{manifest.version}")
            self._assert_executor_known(manifest)
            definitions[key] = manifest
        self._definitions = definitions

    def _assert_executor_known(self, manifest: NodeManifest) -> None:
        if manifest.runtime.executor_key not in EXECUTORS:
            raise ValueError(f"Unknown executor_key '{manifest.runtime.executor_key}' for node '{manifest.id}'")

    def get(self, node_type: str, version: int | None = None) -> NodeManifest | None:
        if version is not None:
            return self._definitions.get((node_type, version))
        matching = [manifest for (manifest_id, _), manifest in self._definitions.items() if manifest_id == node_type]
        if not matching:
            return None
        return sorted(matching, key=lambda item: item.version)[-1]

    def list(self) -> list[NodeManifest]:
        return sorted(self._definitions.values(), key=lambda item: (item.category, item.name, item.version))

    def catalog_response(self) -> NodeCatalogResponse:
        return NodeCatalogResponse(nodes=self.list())

    def import_manifest(self, manifest: NodeManifest) -> NodeManifest:
        self._assert_executor_known(manifest)
        if self.get(manifest.id, manifest.version) is not None:
            raise ValueError(f"Node manifest already exists for {manifest.id} v{manifest.version}")

        filename = f"{manifest.id.lower()}_v{manifest.version}.json"
        path = NODE_ROOT / filename
        path.write_text(json.dumps(manifest.model_dump(mode="json"), indent=2), encoding="utf-8")

        try:
            self.reload()
            created = self.get(manifest.id, manifest.version)
            if created is None:
                raise ValueError(f"Imported node manifest could not be reloaded: {manifest.id} v{manifest.version}")
            configuration_service.save_node_manifest(created)
        except Exception as exc:
            if path.exists():
                path.unlink()
            self.reload()
            raise ValueError(f"Failed to persist imported node manifest in database: {exc}") from exc

        return created

    def execute(self, executor_key: str, parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
        executor = EXECUTORS[executor_key]
        return executor(parameters, inputs)


node_registry = NodeRegistry()
