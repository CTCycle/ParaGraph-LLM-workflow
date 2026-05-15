from __future__ import annotations

import re
from typing import Any
from uuid import NAMESPACE_URL, uuid5

import httpx
from pydantic import ValidationError

from server.domain.node_handler_core import (
    EmbeddingParameters,
    RerankParameters,
    SimilaritySearchParameters,
    VectorStoreParameters,
)
from server.domain.workflow_payloads import (
    RetrievalResults,
    VectorPoint,
    VectorStoreHandle,
)
from server.services.configuration import configuration_service
from server.services.workflow.node_handlers.common import (
    coerce_text,
    normalize_provider_name,
)
from server.services.workflow.node_handlers.core.huggingface_runtime import (
    load_huggingface_embedding_modules as _default_load_huggingface_embedding_modules,
)
from server.services.workflow.node_handlers.core.resolvers import resolve_core_override
from server.services.workflow.node_handlers.core.storage import (
    _extract_text_from_payload,
)
from server.services.workflow.node_handlers.ingestion import (
    load_file_text,
    resolve_local_path,
)
from server.services.workflow.provider import provider_service
from server.services.workflow.vector_stores import get_vector_store_adapter


_HF_EMBEDDING_CACHE: dict[str, tuple[Any, Any, Any]] = {}

###############################################################################
def _resolve_vector_store_adapter(backend: str):
    override = resolve_core_override("get_vector_store_adapter", get_vector_store_adapter)
    return override(backend)

###############################################################################
def _resolve_embedding_function():
    return resolve_core_override(
        "_embed_text_for_text_embedding_node",
        _embed_text_for_text_embedding_node,
    )

###############################################################################
def _resolve_huggingface_embedding_modules():
    override = resolve_core_override(
        "_load_huggingface_embedding_modules",
        _default_load_huggingface_embedding_modules,
    )
    return override()

###############################################################################
def _normalize_embedding_vector(vector: list[float]) -> list[float]:
    magnitude = sum(item * item for item in vector) ** 0.5
    if magnitude <= 0:
        return vector
    return [float(item / magnitude) for item in vector]

###############################################################################
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

###############################################################################
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

###############################################################################
def _embed_text_with_huggingface(
    *, model_name: str, text: str, tokenizer_name: str = ""
) -> list[float]:
    torch_module, auto_model, auto_tokenizer = _resolve_huggingface_embedding_modules()
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

###############################################################################
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

###############################################################################
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

###############################################################################
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

###############################################################################
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

###############################################################################
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

###############################################################################
def _extract_embedding_source(payload: Any) -> tuple[str, str, str]:
    if not isinstance(payload, dict):
        raise ValueError("SIMILARITY_SEARCH requires an embedding controller payload")
    provider = coerce_text(payload.get("provider") or "").strip().lower()
    model_name = coerce_text(payload.get("model") or "").strip()
    if not provider or not model_name:
        raise ValueError("Embedding controller payload must include provider and model")
    tokenizer_name = coerce_text(payload.get("tokenizer_model") or "").strip()
    return provider, model_name, tokenizer_name

###############################################################################
def _canonical_similarity_metric(value: str) -> str:
    normalized = value.strip().lower()
    if normalized == "euclidean":
        return "l2"
    if normalized == "dot":
        return "dot"
    return normalized

###############################################################################
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
    adapter = _resolve_vector_store_adapter(parsed.provider)
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
        index_type=parsed.index_type,
        create_vector_index=parsed.create_vector_index,
        create_keyword_index=parsed.create_keyword_index,
        metadata_index_fields=parsed.metadata_index_fields,
        metadata_schema=parsed.metadata_schema,
        id_conflict_policy=parsed.id_conflict_policy,
        points=points,
    )
    store_payload = store.model_dump(mode="json")
    return {"store": store_payload}

###############################################################################
def _similarity_search_executor(
    parameters: dict[str, Any], inputs: dict[str, Any]
) -> dict[str, Any]:
    parsed = SimilaritySearchParameters.model_validate(parameters)
    query = coerce_text(inputs.get("query") or "").strip()
    if not query:
        raise ValueError("SIMILARITY_SEARCH requires a query input")

    embedding_payload = inputs.get("embedding")
    provider, model_name, tokenizer_name = _extract_embedding_source(embedding_payload)
    query_vector = _resolve_embedding_function()(
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
    adapter = _resolve_vector_store_adapter(backend)
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

###############################################################################
def _normalize_rerank_tokens(value: str) -> list[str]:
    return [token for token in re.split(r"[^a-z0-9]+", value.lower()) if token]

###############################################################################
def _normalize_rerank_text(value: str) -> str:
    return " ".join(_normalize_rerank_tokens(value))


def _term_overlap_score(query_tokens: set[str], text_tokens: set[str]) -> float:
    if not query_tokens:
        return 0.0
    return float(len(query_tokens.intersection(text_tokens)) / len(query_tokens))

###############################################################################
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

###############################################################################
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


__all__ = [
    "_embedding_executor",
    "_rerank_results_executor",
    "_similarity_search_executor",
    "_vector_store_executor",
]
