from __future__ import annotations

import json
import re
from typing import Any
from uuid import NAMESPACE_URL, uuid5

import httpx

from pydantic import ValidationError

from server.domain.chat_history import ChatHistoryHandle
from server.domain.node_handler_core import (
    ChatParameters,
    EmbeddingParameters,
    ImageInputParameters,
    InMemoryChatHistoryParameters,
    ModelProviderParameters,
    PersistedChatHistoryParameters,
    PromptParameters,
    PromptTemplateParameters,
    RerankParameters,
    RouterParameters,
    SaveAsFileParameters,
    SaveAsFolderParameters,
    SimilaritySearchParameters,
    StorageParameters,
    StructuredParameters,
    TextSplitParameters,
    VectorStoreParameters,
)
from server.domain.node_catalog import ProviderModelDefinition
from server.domain.workflow_payloads import (
    RetrievalResults,
    VectorPoint,
    VectorStoreHandle,
)
from server.services.configuration import configuration_service
from server.services.workflow.node_handlers.base import NodeHandler
from server.services.workflow.node_handlers.core.chat_history import (
    execute_chat_history_memory,
    execute_chat_history_persisted,
)
from server.services.workflow.node_handlers.core.huggingface_runtime import (
    load_huggingface_embedding_modules,
    load_huggingface_modules,
)
from server.services.workflow.node_handlers.core.routing import (
    _if_executor,
    _router_executor,
    _text_split_executor,
    _tokenize_executor,
)
from server.services.workflow.node_handlers.core.storage import (
    _extract_text_from_payload,
    _load_text_executor as _load_text_executor_impl,
    _save_as_file_executor,
    _save_as_folder_executor,
)
from server.services.workflow.node_handlers.common import (
    coerce_bool,
    coerce_int,
    coerce_text,
    normalize_provider_name,
    parse_json_value,
    validate_json_against_schema,
)
from server.services.workflow.provider import provider_service
from server.services.workflow.chat_history import chat_history_service
from server.services.workflow.node_handlers.ingestion import (
    load_file_text,
    resolve_local_path,
)
from server.services.workflow.vector_stores import get_vector_store_adapter


_HF_MODEL_CACHE: dict[str, tuple[Any, Any]] = {}
_HF_EMBEDDING_CACHE: dict[str, tuple[Any, Any, Any]] = {}


# -----------------------------------------------------------------------------
def _load_huggingface_modules() -> tuple[Any, Any, Any]:
    return load_huggingface_modules()


def _load_huggingface_embedding_modules() -> tuple[Any, Any, Any]:
    return load_huggingface_embedding_modules()


def _normalize_embedding_vector(vector: list[float]) -> list[float]:
    magnitude = sum(item * item for item in vector) ** 0.5
    if magnitude <= 0:
        return vector
    return [float(item / magnitude) for item in vector]


# -----------------------------------------------------------------------------
def _load_text_executor(
    parameters: dict[str, Any], inputs: dict[str, Any]
) -> dict[str, Any]:
    return _load_text_executor_impl(
        parameters,
        inputs,
        text_loader=load_file_text,
    )


# -----------------------------------------------------------------------------


# -----------------------------------------------------------------------------


# -----------------------------------------------------------------------------
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


# -----------------------------------------------------------------------------
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


# -----------------------------------------------------------------------------
def _build_generation_options(
    parameters: dict[str, Any], *, include_context_window: bool
) -> dict[str, Any]:
    max_tokens = max(1, coerce_int(parameters.get("max_tokens"), 512))
    options: dict[str, Any] = {"max_output_tokens": max_tokens}
    if include_context_window:
        context_window = max(0, coerce_int(parameters.get("context_window"), 0))
        if context_window > 0:
            options["num_ctx"] = context_window
    return options


# -----------------------------------------------------------------------------
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


# -----------------------------------------------------------------------------
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
            raise ValueError("history controller must be a valid chat history handle") from exc

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
    include_context_window = provider in {"ollama", "huggingface"}
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
        if not isinstance(schema, dict):
            raise ValueError("Structured response schema is required")
        validate_json_against_schema(parsed, schema)
        if history_handle is not None:
            chat_history_service.append_exchange(
                history_handle,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                assistant_output=chat_history_service.serialize_structured_output(parsed),
            )
        return {"result": parsed}
    if history_handle is not None:
        chat_history_service.append_exchange(
            history_handle,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            assistant_output=text,
        )
    return {"response": text}


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
    if not model_name:
        raise ValueError("MODEL_PROVIDER requires a model_name")
    return {
        "model": provider_service.build_model_definition(
            provider,
            model_name,
            timeout_s=timeout_seconds,
        ).model_dump(mode="json")
    }


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


def _load_document_text_content(
    document: dict[str, Any], *, fallback_index: int
) -> tuple[str, str, dict[str, Any]]:
    metadata = (
        document.get("metadata") if isinstance(document.get("metadata"), dict) else {}
    )
    text_content = _extract_text_from_payload(document, ("text", "content", "chunk"))
    source_uri = coerce_text(
        document.get("source_uri")
        or metadata.get("file_path")
        or f"document:{fallback_index}"
    ).strip()
    if not text_content.strip():
        path_candidate = coerce_text(metadata.get("file_path") or source_uri).strip()
        if path_candidate:
            path = resolve_local_path(path_candidate)
            if path.exists() and path.is_file():
                text_content, _mime_type = load_file_text(path)
    return text_content.strip(), source_uri, metadata


def _embed_text_with_gemini(*, model_name: str, text: str) -> list[float]:
    config = configuration_service.load_configuration()
    access_key = next(
        (
            item
            for item in config.access_keys
            if normalize_provider_name(item.provider, default="") == "gemini"
        ),
        None,
    )
    api_key = access_key.api_key if access_key else None
    base_url = (
        access_key.base_url
        if access_key and access_key.base_url
        else "https://generativelanguage.googleapis.com/v1beta"
    ).rstrip("/")
    if not api_key:
        raise ValueError("Provider 'gemini' requires an access key in Configurations")

    response = httpx.post(
        f"{base_url}/models/{model_name}:embedContent",
        json={
            "model": f"models/{model_name}",
            "content": {"parts": [{"text": text}]},
        },
        timeout=30.0,
        headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
    )
    response.raise_for_status()
    payload = response.json()
    embedding = payload.get("embedding") if isinstance(payload, dict) else None
    values = embedding.get("values") if isinstance(embedding, dict) else None
    if not isinstance(values, list):
        raise ValueError("Invalid Gemini embeddings response")
    return [float(item) for item in values]


def _embed_text_with_huggingface(
    *, model_name: str, text: str, tokenizer_name: str = ""
) -> list[float]:
    torch_module, auto_model, auto_tokenizer = _load_huggingface_embedding_modules()
    config = configuration_service.load_configuration()
    access_key = next(
        (
            item
            for item in config.access_keys
            if normalize_provider_name(item.provider, default="") == "huggingface"
        ),
        None,
    )
    access_token = access_key.api_key if access_key and access_key.api_key else None

    tokenizer_model_name = tokenizer_name.strip() or model_name
    cache_key = f"{model_name}\u0000{tokenizer_model_name}"

    if cache_key not in _HF_EMBEDDING_CACHE:
        tokenizer = auto_tokenizer.from_pretrained(tokenizer_model_name, token=access_token)
        if getattr(tokenizer, "pad_token", None) is None:
            tokenizer.pad_token = tokenizer.eos_token
        model = auto_model.from_pretrained(model_name, token=access_token)
        _HF_EMBEDDING_CACHE[cache_key] = (torch_module, tokenizer, model)

    cached_torch, tokenizer, model = _HF_EMBEDDING_CACHE[cache_key]
    encoded = tokenizer([text], padding=True, truncation=True, return_tensors="pt")
    target_device = getattr(model, "device", None)
    if target_device is not None:
        encoded = {key: value.to(target_device) for key, value in encoded.items()}

    with cached_torch.no_grad():
        outputs = model(**encoded)
        last_hidden_state = getattr(outputs, "last_hidden_state", None)
        if last_hidden_state is None:
            raise ValueError(
                "Hugging Face embedding model did not return a hidden state"
            )
        attention_mask = (
            encoded["attention_mask"]
            .unsqueeze(-1)
            .expand(last_hidden_state.size())
            .float()
        )
        pooled = (last_hidden_state * attention_mask).sum(dim=1) / attention_mask.sum(
            dim=1
        ).clamp(min=1.0)
        vector = pooled[0].detach().cpu().tolist()
    return _normalize_embedding_vector([float(item) for item in vector])


def _embed_text_for_text_embedding_node(
    *, provider: str, model_name: str, text: str, tokenizer_name: str = ""
) -> list[float]:
    if provider in {"openai", "ollama"}:
        return provider_service.embed_text(
            provider=provider, model=model_name, text=text
        )
    if provider == "gemini":
        return _embed_text_with_gemini(model_name=model_name, text=text)
    if provider == "huggingface":
        return _embed_text_with_huggingface(
            model_name=model_name, text=text, tokenizer_name=tokenizer_name
        )
    raise ValueError(f"Unsupported embedding provider: {provider}")


def _collect_embedding_points(
    *,
    inputs: dict[str, Any],
    provider: str,
    model_name: str,
    tokenizer_name: str = "",
) -> list[dict[str, Any]]:
    points: list[dict[str, Any]] = []
    text_payload = coerce_text(inputs.get("text") or "").strip()
    if text_payload:
        document_id = str(uuid5(NAMESPACE_URL, f"text:{text_payload}"))
        points.append(
            {
                "id": str(uuid5(NAMESPACE_URL, f"point:{document_id}")),
                "chunk_id": "",
                "document_id": document_id,
                "text": text_payload,
                "source_uri": "inline:text",
                "vector": _embed_text_for_text_embedding_node(
                    provider=provider,
                    model_name=model_name,
                    tokenizer_name=tokenizer_name,
                    text=text_payload,
                ),
                "embedding_provider": provider,
                "embedding_model": model_name,
                "metadata": {"origin": "text"},
            }
        )

    documents = (
        inputs.get("documents") if isinstance(inputs.get("documents"), list) else []
    )
    for index, document in enumerate(documents, start=1):
        if not isinstance(document, dict):
            continue
        text_content, source_uri, metadata = _load_document_text_content(
            document, fallback_index=index
        )
        if not text_content:
            continue
        document_id = coerce_text(document.get("id") or "").strip() or str(
            uuid5(NAMESPACE_URL, source_uri)
        )
        points.append(
            {
                "id": str(uuid5(NAMESPACE_URL, f"point:{document_id}")),
                "chunk_id": "",
                "document_id": document_id,
                "text": text_content,
                "source_uri": source_uri,
                "vector": _embed_text_for_text_embedding_node(
                    provider=provider,
                    model_name=model_name,
                    tokenizer_name=tokenizer_name,
                    text=text_content,
                ),
                "embedding_provider": provider,
                "embedding_model": model_name,
                "metadata": {**metadata, "origin": "document"},
            }
        )

    chunks = inputs.get("chunks") if isinstance(inputs.get("chunks"), list) else []
    for index, chunk in enumerate(chunks, start=1):
        if not isinstance(chunk, dict):
            continue
        text_content = _extract_text_from_payload(
            chunk, ("text", "content", "chunk")
        ).strip()
        if not text_content:
            continue
        chunk_id = coerce_text(chunk.get("id") or "").strip() or str(
            uuid5(NAMESPACE_URL, f"chunk:{index}:{text_content}")
        )
        document_id = coerce_text(chunk.get("document_id") or "").strip() or str(
            uuid5(NAMESPACE_URL, chunk_id)
        )
        source_uri = coerce_text(chunk.get("source_uri") or f"chunk:{chunk_id}").strip()
        metadata = (
            chunk.get("metadata") if isinstance(chunk.get("metadata"), dict) else {}
        )
        points.append(
            {
                "id": chunk_id,
                "chunk_id": chunk_id,
                "document_id": document_id,
                "text": text_content,
                "source_uri": source_uri,
                "vector": _embed_text_for_text_embedding_node(
                    provider=provider,
                    model_name=model_name,
                    tokenizer_name=tokenizer_name,
                    text=text_content,
                ),
                "embedding_provider": provider,
                "embedding_model": model_name,
                "metadata": {**metadata, "origin": "chunk"},
            }
        )

    return points


def _embedding_executor(
    parameters: dict[str, Any], inputs: dict[str, Any]
) -> dict[str, Any]:
    parsed = EmbeddingParameters.model_validate(parameters)
    model_name = coerce_text(parsed.model_name).strip()
    if not model_name:
        raise ValueError("TEXT_EMBEDDING requires a model_name")
    provider = normalize_provider_name(parsed.provider, default="ollama")
    tokenizer_name = coerce_text(parsed.tokenizer_name).strip()
    points = _collect_embedding_points(
        inputs=inputs,
        provider=provider,
        model_name=model_name,
        tokenizer_name=tokenizer_name,
    )
    if not points:
        raise ValueError(
            "TEXT_EMBEDDING requires at least one non-empty text, document, or chunk"
        )
    vectors = [
        VectorPoint.model_validate(point).model_dump(mode="json") for point in points
    ]
    return {
        "vectors": vectors,
        "embedding": {
            "provider": provider,
            "model": model_name,
            "tokenizer_model": tokenizer_name or model_name,
            "vectors": vectors,
        },
    }


def _flatten_vector_point_inputs(raw_points: Any) -> list[dict[str, Any]]:
    if isinstance(raw_points, list):
        flattened: list[dict[str, Any]] = []
        for item in raw_points:
            if isinstance(item, list):
                flattened.extend(_flatten_vector_point_inputs(item))
            elif isinstance(item, dict):
                flattened.append(item)
        return flattened
    if isinstance(raw_points, dict):
        return [raw_points]
    return []


def _flatten_embedding_controller_inputs(
    raw_embedding_payload: Any,
) -> list[dict[str, Any]]:
    values = (
        raw_embedding_payload
        if isinstance(raw_embedding_payload, list)
        else [raw_embedding_payload]
    )
    points: list[dict[str, Any]] = []
    for value in values:
        if not isinstance(value, dict):
            continue
        vectors = value.get("vectors")
        points.extend(_flatten_vector_point_inputs(vectors))
    return points


def _extract_embedding_source(payload: Any) -> tuple[str, str, str]:
    if not isinstance(payload, dict):
        raise ValueError("SIMILARITY_SEARCH requires an embedding controller payload")
    provider = coerce_text(payload.get("provider") or "").strip().lower()
    model_name = coerce_text(payload.get("model") or "").strip()
    if not provider or not model_name:
        raise ValueError("Embedding controller payload must include provider and model")
    tokenizer_name = coerce_text(payload.get("tokenizer_model") or "").strip()
    return provider, model_name, tokenizer_name


def _canonical_similarity_metric(value: str) -> str:
    normalized = value.strip().lower()
    if normalized == "euclidean":
        return "l2"
    if normalized == "dot":
        return "dot"
    return normalized


def _vector_store_executor(
    parameters: dict[str, Any], inputs: dict[str, Any]
) -> dict[str, Any]:
    parsed = VectorStoreParameters.model_validate(parameters)
    points = [
        *_flatten_vector_point_inputs(inputs.get("vectors")),
        *_flatten_embedding_controller_inputs(inputs.get("embedding")),
    ]
    if not points:
        raise ValueError("VECTOR_STORE requires at least one vectors input")
    adapter = get_vector_store_adapter(parsed.provider)
    store = adapter.write_points(
        index_name=parsed.index_name,
        storage_directory=parsed.storage_path,
        metric=parsed.distance_metric,
        write_mode=parsed.write_mode,
        namespace=parsed.namespace,
        endpoint_url=parsed.endpoint_url,
        api_key=parsed.api_key,
        collection_name=parsed.collection_name,
        database_name=parsed.database_name,
        provider_config=parsed.provider_config,
        points=points,
    )
    store_payload = store.model_dump(mode="json")
    return {"store": store_payload}


def _similarity_search_executor(
    parameters: dict[str, Any], inputs: dict[str, Any]
) -> dict[str, Any]:
    parsed = SimilaritySearchParameters.model_validate(parameters)
    query = coerce_text(inputs.get("query") or "").strip()
    if not query:
        raise ValueError("SIMILARITY_SEARCH requires a query input")

    embedding_payload = inputs.get("embedding")
    provider, model_name, tokenizer_name = _extract_embedding_source(embedding_payload)
    query_vector = _embed_text_for_text_embedding_node(
        provider=provider, model_name=model_name, tokenizer_name=tokenizer_name, text=query
    )

    raw_store_payload = inputs.get("store")
    if not isinstance(raw_store_payload, dict):
        raise ValueError("SIMILARITY_SEARCH requires a vector store controller input")
    try:
        store_payload = VectorStoreHandle.model_validate(raw_store_payload).model_dump(
            mode="json"
        )
    except ValidationError as exc:
        raise ValueError(
            "SIMILARITY_SEARCH received an invalid vector store controller payload"
        ) from exc

    requested_metric = _canonical_similarity_metric(parsed.similarity_strategy)
    store_metric = _canonical_similarity_metric(
        coerce_text(store_payload.get("metric") or "cosine")
    )
    if requested_metric != store_metric:
        raise ValueError(
            "SIMILARITY_SEARCH similarity_strategy must match the connected vector store metric "
            f"({store_metric})."
        )

    backend = coerce_text(store_payload.get("backend") or "lancedb").strip().lower()
    adapter = get_vector_store_adapter(backend)
    capabilities = adapter.describe_capabilities()
    if parsed.search_mode == "hybrid" and not bool(
        capabilities.get("supports_hybrid_search")
    ):
        raise ValueError(
            f"SIMILARITY_SEARCH backend '{backend}' does not support hybrid mode"
        )
    if parsed.search_engine == "faiss_augmented" and not bool(
        capabilities.get("supports_faiss_augmentation")
    ):
        raise ValueError(
            f"SIMILARITY_SEARCH backend '{backend}' does not support faiss_augmented engine"
        )

    raw_filter_spec = (
        parsed.metadata_filter if isinstance(parsed.metadata_filter, dict) else None
    )
    if raw_filter_spec and not bool(
        capabilities.get("supports_metadata_filtering", True)
    ):
        raise ValueError(
            f"SIMILARITY_SEARCH backend '{backend}' does not support metadata filtering"
        )

    effective_search_engine = parsed.search_engine
    if effective_search_engine == "faiss_augmented":
        # The runtime currently reuses backend-native search while preserving
        # explicit compatibility validation for optional faiss augmentation mode.
        effective_search_engine = "native"

    hits = adapter.search(
        store=store_payload,
        query_vector=query_vector,
        top_k=parsed.top_k,
        score_threshold=float(parsed.score_threshold),
        filter_spec=raw_filter_spec,
        include_metadata=bool(parsed.include_metadata),
        ann_search_depth=parsed.ann_search_depth,
        search_mode=parsed.search_mode,
        keyword_query=coerce_text(parsed.keyword_query).strip() or None,
        vector_weight=float(parsed.vector_weight),
        keyword_weight=float(parsed.keyword_weight),
        search_engine=effective_search_engine,
    )

    return {
        "results": RetrievalResults(query=query, hits=hits).model_dump(mode="json"),
    }


def _normalize_rerank_tokens(value: str) -> list[str]:
    return [token for token in re.split(r"[^a-z0-9]+", value.lower()) if token]


def _normalize_rerank_text(value: str) -> str:
    return " ".join(_normalize_rerank_tokens(value))


def _term_overlap_score(query_tokens: set[str], text_tokens: set[str]) -> float:
    if not query_tokens:
        return 0.0
    return float(len(query_tokens.intersection(text_tokens)) / len(query_tokens))


def _metadata_match_score(
    *,
    metadata: dict[str, Any],
    metadata_field: str,
    metadata_value: str,
) -> float:
    field_name = metadata_field.strip()
    if not field_name:
        return 0.0
    if field_name not in metadata:
        return 0.0
    actual = str(metadata.get(field_name, "")).strip().lower()
    expected = metadata_value.strip().lower()
    return 1.0 if actual == expected else 0.0


def _rerank_results_executor(
    parameters: dict[str, Any], inputs: dict[str, Any]
) -> dict[str, Any]:
    parsed = RerankParameters.model_validate(parameters)
    raw_results = inputs.get("results")
    if not isinstance(raw_results, dict):
        raise ValueError("RERANK_RESULTS requires a RETRIEVAL_RESULTS input")

    retrieval_results = RetrievalResults.model_validate(raw_results)
    query_input = coerce_text(inputs.get("query") or "").strip()
    effective_query = query_input or retrieval_results.query
    normalized_query = _normalize_rerank_text(effective_query)
    query_tokens = set(_normalize_rerank_tokens(effective_query))

    scored_hits: list[tuple[float, dict[str, Any]]] = []
    for hit in retrieval_results.hits:
        hit_payload = hit.model_dump(mode="json")
        original_score = float(hit.score)
        text_tokens = set(_normalize_rerank_tokens(hit.text))
        normalized_text = _normalize_rerank_text(hit.text)
        metadata = hit.metadata if isinstance(hit.metadata, dict) else {}

        term_overlap = _term_overlap_score(query_tokens, text_tokens)
        exact_phrase = (
            1.0 if normalized_query and normalized_query in normalized_text else 0.0
        )
        metadata_match = _metadata_match_score(
            metadata=metadata,
            metadata_field=parsed.metadata_field,
            metadata_value=parsed.metadata_value,
        )

        if parsed.strategy == "original_score":
            rerank_score = original_score
        elif parsed.strategy == "term_overlap":
            rerank_score = term_overlap
        elif parsed.strategy == "exact_phrase":
            rerank_score = exact_phrase
        elif parsed.strategy == "metadata_match":
            rerank_score = metadata_match
        else:
            rerank_score = (
                (float(parsed.original_score_weight) * original_score)
                + (float(parsed.term_overlap_weight) * term_overlap)
                + (float(parsed.phrase_boost) * exact_phrase)
                + (float(parsed.metadata_boost) * metadata_match)
            )

        if parsed.score_mode == "boost":
            final_score = original_score + rerank_score
        else:
            final_score = rerank_score

        hit_payload["score"] = float(final_score)
        scored_hits.append((float(final_score), hit_payload))

    reranked_hits = [
        payload
        for _, payload in sorted(scored_hits, key=lambda item: item[0], reverse=True)
    ]
    if parsed.top_k > 0:
        reranked_hits = reranked_hits[: parsed.top_k]

    return {
        "results": RetrievalResults(
            query=retrieval_results.query, hits=reranked_hits
        ).model_dump(mode="json"),
    }


CORE_HANDLERS = {
    "prompt": NodeHandler(executor=_prompt_executor, parameter_model=PromptParameters),
    "prompt_template": NodeHandler(
        executor=_prompt_template_executor, parameter_model=PromptTemplateParameters
    ),
    "image_input": NodeHandler(
        executor=_image_input_executor, parameter_model=ImageInputParameters
    ),
    "model_provider": NodeHandler(
        executor=_model_provider_executor, parameter_model=ModelProviderParameters
    ),
    "llm_chat": NodeHandler(
        executor=_llm_chat_executor, parameter_model=ChatParameters
    ),
    "llm_structured": NodeHandler(
        executor=_llm_structured_executor, parameter_model=StructuredParameters
    ),
    "text_embedding": NodeHandler(
        executor=_embedding_executor, parameter_model=EmbeddingParameters
    ),
    "vector_store": NodeHandler(
        executor=_vector_store_executor, parameter_model=VectorStoreParameters
    ),
    "similarity_search": NodeHandler(
        executor=_similarity_search_executor, parameter_model=SimilaritySearchParameters
    ),
    "rerank_results": NodeHandler(
        executor=_rerank_results_executor, parameter_model=RerankParameters
    ),
    "tokenize": NodeHandler(executor=_tokenize_executor),
    "text_split": NodeHandler(
        executor=_text_split_executor, parameter_model=TextSplitParameters
    ),
    "save_as_file": NodeHandler(
        executor=_save_as_file_executor, parameter_model=SaveAsFileParameters
    ),
    "save_as_folder": NodeHandler(
        executor=_save_as_folder_executor, parameter_model=SaveAsFolderParameters
    ),
    "load_text": NodeHandler(
        executor=_load_text_executor, parameter_model=StorageParameters
    ),
    "if": NodeHandler(executor=_if_executor),
    "router": NodeHandler(executor=_router_executor, parameter_model=RouterParameters),
    "chat_history_memory": NodeHandler(
        executor=execute_chat_history_memory,
        parameter_model=InMemoryChatHistoryParameters,
    ),
    "chat_history_persisted": NodeHandler(
        executor=execute_chat_history_persisted,
        parameter_model=PersistedChatHistoryParameters,
    ),
}

