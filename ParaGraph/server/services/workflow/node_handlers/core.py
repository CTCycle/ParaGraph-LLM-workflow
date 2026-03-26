from __future__ import annotations

import importlib
import json
import re
import shutil
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from ParaGraph.server.common.constants import RESOURCES_PATH
from ParaGraph.server.common.security import ensure_path_within_root, is_cloud_deployment
from ParaGraph.server.domain.node_handler_core import (
    ChatParameters,
    EmbeddingParameters,
    ImageInputParameters,
    ModelProviderParameters,
    PromptParameters,
    PromptTemplateParameters,
    RouterParameters,
    SaveAsFileParameters,
    SaveAsFolderParameters,
    StorageParameters,
    StructuredParameters,
    TextSplitParameters,
)
from ParaGraph.server.domain.nodecatalog import ProviderModelDefinition
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
from ParaGraph.server.services.workflow.node_handlers.ingestion import _load_file_text, _resolve_local_path


ARTIFACT_ROOT = Path(RESOURCES_PATH) / "artifacts"
_HF_MODEL_CACHE: dict[str, tuple[Any, Any]] = {}
SAVE_AS_FILE_CHUNK_SEPARATOR = "/n/n"
SAVE_AS_FOLDER_INDEX_WIDTH = 6

# -----------------------------------------------------------------------------
def _load_huggingface_modules() -> tuple[Any, Any, Any]:
    try:
        torch_module = importlib.import_module("torch")
        transformers_module = importlib.import_module("transformers")
    except ModuleNotFoundError as exc:
        raise ValueError("Hugging Face support requires installing torch and transformers") from exc

    auto_model_for_causal_lm = getattr(transformers_module, "AutoModelForCausalLM", None)
    auto_tokenizer = getattr(transformers_module, "AutoTokenizer", None)
    if auto_model_for_causal_lm is None or auto_tokenizer is None:
        raise ValueError("Hugging Face support requires transformers AutoModelForCausalLM and AutoTokenizer")

    return torch_module, auto_model_for_causal_lm, auto_tokenizer

# -----------------------------------------------------------------------------
def _resolve_storage_path(
    raw_path: Any,
    *,
    label: str,
    relative_to_artifacts_root: bool = False,
) -> Path:
    storage_path = coerce_text(raw_path).strip()
    if not storage_path:
        raise ValueError(f"{label} is required. Select a local path.")
    candidate = Path(storage_path).expanduser()
    artifact_root = ARTIFACT_ROOT.resolve()
    if candidate.is_absolute():
        resolved = candidate.resolve()
        if is_cloud_deployment():
            return ensure_path_within_root(resolved, artifact_root, label=label)
        return resolved

    if relative_to_artifacts_root:
        resolved = (ARTIFACT_ROOT / candidate).resolve()
        return ensure_path_within_root(resolved, artifact_root, label=label)

    resolved = candidate.resolve()
    if is_cloud_deployment():
        return ensure_path_within_root(resolved, artifact_root, label=label)
    return resolved

# -----------------------------------------------------------------------------
def _to_artifact_path(path: Path) -> str:
    artifact_root = ARTIFACT_ROOT.resolve()
    try:
        return str(path.resolve().relative_to(artifact_root))
    except ValueError:
        return str(path.resolve())

# -----------------------------------------------------------------------------
def _prompt_executor(parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    _ = inputs
    return {"text": coerce_text(parameters.get("prompt_text", "")).strip()}


def _extract_template_record_text(record: dict[str, Any]) -> str:
    candidate = coerce_text(record.get("text") or record.get("content") or record.get("chunk") or "")
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


_PROMPT_TEMPLATE_PATTERN = re.compile(r"\{\{\s*([^{}]+?)\s*\}\}")


def _apply_prompt_template_cleanup(text: str, mode: str) -> str:
    if mode == "none":
        return text
    if mode == "trim_lines":
        return "\n".join(line.strip() for line in text.splitlines())
    if mode == "drop_empty_lines":
        return "\n".join(line for line in (entry.strip() for entry in text.splitlines()) if line)
    if mode == "collapse_blank_lines":
        normalized = "\n".join(line.rstrip() for line in text.splitlines())
        return re.sub(r"\n{3,}", "\n\n", normalized)
    return text


def _prompt_template_executor(parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    parsed = PromptTemplateParameters.model_validate(parameters)
    value_map: dict[str, str] = {}
    for index in range(1, 9):
        key = f"var_{index}"
        if key in inputs and inputs.get(key) is not None:
            value_map[key] = _coerce_template_value(inputs.get(key))

    for index, alias in enumerate(parsed.variable_names, start=1):
        source_key = f"var_{index}"
        if source_key in value_map:
            value_map[alias] = value_map[source_key]

    missing_variables: set[str] = set()

    def replace_placeholder(match: re.Match[str]) -> str:
        variable_name = match.group(1).strip()
        if variable_name in value_map:
            return value_map[variable_name]
        missing_variables.add(variable_name)
        if parsed.missing_variable == "empty":
            return ""
        if parsed.missing_variable == "keep_placeholder":
            return match.group(0)
        return match.group(0)

    rendered = _PROMPT_TEMPLATE_PATTERN.sub(replace_placeholder, parsed.template)
    if missing_variables and parsed.missing_variable == "error":
        missing_list = ", ".join(sorted(missing_variables))
        raise ValueError(f"PROMPT_TEMPLATE missing variable values for: {missing_list}")

    return {"text": _apply_prompt_template_cleanup(rendered, parsed.cleanup)}

# -----------------------------------------------------------------------------
def _image_input_executor(parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    _ = inputs
    return {"image": {"path": coerce_text(parameters.get("file_path", "")).strip()}}

# -----------------------------------------------------------------------------
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

# -----------------------------------------------------------------------------
def _build_generation_options(parameters: dict[str, Any], *, include_context_window: bool) -> dict[str, Any]:
    max_tokens = max(1, coerce_int(parameters.get("max_tokens"), 512))
    options: dict[str, Any] = {"max_output_tokens": max_tokens}
    if include_context_window:
        context_window = max(0, coerce_int(parameters.get("context_window"), 0))
        if context_window > 0:
            options["num_ctx"] = context_window
    return options

# -----------------------------------------------------------------------------
def _resolve_model_selection(parameters: dict[str, Any], inputs: dict[str, Any]) -> ProviderModelDefinition:
    _ = parameters
    model_input = inputs.get("model")
    if model_input is None:
        raise ValueError("LLM nodes require a connected model provider controller")
    try:
        return ProviderModelDefinition.model_validate(model_input)
    except ValidationError as exc:
        raise ValueError("model controller must be a valid model handle") from exc

# -----------------------------------------------------------------------------
def _run_huggingface_chat(
    *,
    model_name: str,
    messages: list[dict[str, Any]],
    max_tokens: int,
    context_window: int,
    access_token: str,
) -> str:

    torch_module, auto_model_for_causal_lm, auto_tokenizer = _load_huggingface_modules()
    if model_name not in _HF_MODEL_CACHE:
        tokenizer = auto_tokenizer.from_pretrained(model_name, token=access_token)
        model = auto_model_for_causal_lm.from_pretrained(
            model_name,
            token=access_token,
            torch_dtype=torch_module.float16 if torch_module.cuda.is_available() else torch_module.float32,
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
        return decoded[len(prompt_text):].strip()
    return decoded.strip()

# -----------------------------------------------------------------------------
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


def _safe_file_stem(raw_name: str, fallback: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", raw_name).strip("._-")
    return cleaned or fallback


def _derive_item_name_from_source(source_uri: str, fallback: str) -> str:
    source = source_uri.strip()
    if not source:
        return fallback
    candidate = Path(source)
    if candidate.name:
        return candidate.stem or candidate.name
    return fallback


def _extract_text_from_payload(payload: dict[str, Any], candidate_keys: tuple[str, ...]) -> str:
    for key in candidate_keys:
        if key not in payload:
            continue
        raw_value = payload.get(key)
        if isinstance(raw_value, dict):
            nested = coerce_text(raw_value.get("text") or raw_value.get("content") or raw_value.get("chunk") or "")
            if nested.strip():
                return nested
            continue
        text_value = coerce_text(raw_value or "")
        if text_value.strip():
            return text_value
    return ""


def _collect_save_items(inputs: dict[str, Any]) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    text_payload = coerce_text(inputs.get("text") or "")
    if text_payload.strip():
        items.append({"name": "text_output", "text": text_payload})

    documents = inputs.get("documents") if isinstance(inputs.get("documents"), list) else []
    for index, document in enumerate(documents, start=1):
        if not isinstance(document, dict):
            continue
        metadata = document.get("metadata") if isinstance(document.get("metadata"), dict) else {}
        text_content = _extract_text_from_payload(document, ("text", "content", "chunk"))
        if not text_content.strip():
            path_candidate = coerce_text(metadata.get("file_path") or document.get("source_uri") or "").strip()
            if path_candidate:
                path = _resolve_local_path(path_candidate)
                if path.exists() and path.is_file():
                    text_content, _mime_type = _load_file_text(path)
        if not text_content.strip():
            continue
        file_name = coerce_text(metadata.get("file_name") or "")
        source_uri = coerce_text(document.get("source_uri") or "")
        derived = Path(file_name).stem if file_name else _derive_item_name_from_source(source_uri, f"document_{index}")
        items.append({"name": derived or f"document_{index}", "text": text_content})

    chunks = inputs.get("chunks") if isinstance(inputs.get("chunks"), list) else []
    for index, chunk in enumerate(chunks, start=1):
        if not isinstance(chunk, dict):
            continue
        text_content = _extract_text_from_payload(chunk, ("text", "content", "chunk"))
        if not text_content.strip():
            continue
        document_id = coerce_text(chunk.get("document_id") or "").strip()
        chunk_index = chunk.get("chunk_index")
        if isinstance(chunk_index, int) and chunk_index >= 0:
            derived = f"{document_id or 'chunk'}_{chunk_index}"
        else:
            derived = document_id or f"chunk_{index}"
        items.append({"name": derived, "text": text_content})

    return items

# -----------------------------------------------------------------------------
def _ensure_extension(path: Path, extension: str) -> Path:
    if path.suffix.lower() == extension:
        return path
    if path.suffix:
        return path.with_suffix(extension)
    return Path(f"{path.as_posix()}{extension}")

# -----------------------------------------------------------------------------
def _prepare_directory(path: Path) -> None:
    if path.exists() and path.is_file():
        path.unlink()
    path.mkdir(parents=True, exist_ok=True)

# -----------------------------------------------------------------------------
def _prepare_file_destination(path: Path) -> None:
    if path.exists() and path.is_dir():
        shutil.rmtree(path)
    path.parent.mkdir(parents=True, exist_ok=True)

# -----------------------------------------------------------------------------
def _build_client_side_save_as_file_artifact(
    parsed: SaveAsFileParameters,
    item_texts: list[str],
) -> dict[str, Any]:
    output_path = coerce_text(parsed.output_path).strip()
    if not output_path:
        raise ValueError("output_path is required. Select a local path.")

    destination = _ensure_extension(Path(output_path).expanduser(), parsed.extension)
    resolved_path = str(destination)
    return {
        "artifact": {
            "path": resolved_path,
            "files": [resolved_path],
            "count": 1,
            "extension": parsed.extension,
            "item_texts": item_texts,
        }
    }

# -----------------------------------------------------------------------------
def _save_as_file_executor(parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    parsed = SaveAsFileParameters.model_validate(parameters)
    items = _collect_save_items(inputs)
    if not items:
        raise ValueError("SAVE_AS_FILE requires at least one non-empty text, documents, or chunks input")

    item_texts = [item["text"] for item in items]

    if parsed.client_side_write and not is_cloud_deployment():
        return _build_client_side_save_as_file_artifact(
            parsed,
            item_texts,
        )

    target_root = _resolve_storage_path(parsed.output_path, label="output_path", relative_to_artifacts_root=True)
    destination = _ensure_extension(target_root, parsed.extension)
    _prepare_file_destination(destination)
    with destination.open("w", encoding="utf-8") as stream:
        for index, item_text in enumerate(item_texts):
            if index > 0:
                stream.write(SAVE_AS_FILE_CHUNK_SEPARATOR)
            stream.write(item_text)
    resolved_path = _to_artifact_path(destination)
    return {
        "artifact": {
            "path": resolved_path,
            "files": [resolved_path],
            "count": 1,
            "extension": parsed.extension,
        }
    }

# -----------------------------------------------------------------------------
def _build_client_side_save_as_folder_artifact(
    parsed: SaveAsFolderParameters,
    item_count: int,
    item_texts: list[str],
) -> dict[str, Any]:
    output_path = coerce_text(parsed.output_path).strip()
    if not output_path:
        raise ValueError("output_path is required. Select a local path.")

    destination_dir = Path(output_path).expanduser()
    base_stem = _safe_file_stem(destination_dir.name, "output")
    files = [
        str(destination_dir / f"{base_stem}_{index:0{SAVE_AS_FOLDER_INDEX_WIDTH}d}{parsed.extension}")
        for index in range(1, item_count + 1)
    ]
    return {
        "artifact": {
            "path": str(destination_dir),
            "files": files,
            "count": len(files),
            "extension": parsed.extension,
            "item_texts": item_texts,
        }
    }

# -----------------------------------------------------------------------------
def _save_as_folder_executor(parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    parsed = SaveAsFolderParameters.model_validate(parameters)
    items = _collect_save_items(inputs)
    if not items:
        raise ValueError("SAVE_AS_FOLDER requires at least one non-empty text, documents, or chunks input")

    item_texts = [item["text"] for item in items]
    if parsed.client_side_write and not is_cloud_deployment():
        return _build_client_side_save_as_folder_artifact(
            parsed,
            len(items),
            item_texts,
        )

    destination_dir = _resolve_storage_path(parsed.output_path, label="output_path", relative_to_artifacts_root=True)
    _prepare_directory(destination_dir)
    base_stem = _safe_file_stem(destination_dir.name, "output")
    written_files: list[str] = []
    for index, item in enumerate(items, start=1):
        candidate_name = f"{base_stem}_{index:0{SAVE_AS_FOLDER_INDEX_WIDTH}d}{parsed.extension}"
        destination = destination_dir / candidate_name
        destination.write_text(item["text"], encoding="utf-8")
        written_files.append(_to_artifact_path(destination))

    return {
        "artifact": {
            "path": _to_artifact_path(destination_dir),
            "files": written_files,
            "count": len(written_files),
            "extension": parsed.extension,
        }
    }

# -----------------------------------------------------------------------------
def _load_text_executor(parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    _ = inputs
    source = _resolve_storage_path(parameters.get("storage_path"), label="storage_path")
    if not source.exists():
        raise ValueError(f"Text file not found: {source}")
    if not source.is_file():
        raise ValueError(f"storage_path must point to a file: {source}")
    text_content, _mime_type = _load_file_text(source)
    return {"text": text_content}

# -----------------------------------------------------------------------------
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
    "prompt_template": NodeHandler(executor=_prompt_template_executor, parameter_model=PromptTemplateParameters),
    "user_prompt": NodeHandler(executor=_prompt_executor, parameter_model=PromptParameters),
    "system_prompt": NodeHandler(executor=_prompt_executor, parameter_model=PromptParameters),
    "image_input": NodeHandler(executor=_image_input_executor, parameter_model=ImageInputParameters),
    "model_provider": NodeHandler(executor=_model_provider_executor, parameter_model=ModelProviderParameters),
    "llm_chat": NodeHandler(executor=_llm_chat_executor, parameter_model=ChatParameters),
    "llm_structured": NodeHandler(executor=_llm_structured_executor, parameter_model=StructuredParameters),
    "embedding_model": NodeHandler(executor=_embedding_executor, parameter_model=EmbeddingParameters),
    "tokenize": NodeHandler(executor=_tokenize_executor),
    "text_split": NodeHandler(executor=_text_split_executor, parameter_model=TextSplitParameters),
    "save_as_file": NodeHandler(executor=_save_as_file_executor, parameter_model=SaveAsFileParameters),
    "save_as_folder": NodeHandler(executor=_save_as_folder_executor, parameter_model=SaveAsFolderParameters),
    "load_text": NodeHandler(executor=_load_text_executor, parameter_model=StorageParameters),
    "if": NodeHandler(executor=_if_executor),
    "router": NodeHandler(executor=_router_executor, parameter_model=RouterParameters),
}

