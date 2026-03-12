from __future__ import annotations

from typing import Any

import numpy as np
from pydantic import BaseModel, Field, field_validator, model_validator

from ParaGraph.server.services.workflow.node_handlers.base import NodeHandler
from ParaGraph.server.services.workflow.node_handlers.common import coerce_text, normalize_provider_name, parse_json_value
from ParaGraph.server.services.workflow.provider import provider_service
from ParaGraph.server.services.workflow.vectorstores import VectorStoreError, get_vector_store_adapter


class BatchEmbedderParameters(BaseModel):
    provider: str = "ollama"
    model_name: str = "nomic-embed-text"
    batch_size: int = Field(default=16, ge=1, le=128)
    dimensions: int | None = Field(default=None, ge=1)
    normalize: bool = True
    max_retries: int = Field(default=1, ge=0, le=5)

    @field_validator("dimensions", mode="before")
    @classmethod
    def normalize_dimensions(cls, value: Any) -> int | None:
        if value in {None, "", 0, "0"}:
            return None
        return value


class VectorWriterParameters(BaseModel):
    backend: str = "faiss"
    index_name: str
    storage_directory: str = ""
    metric: str = "cosine"
    index_type: str = "flat"
    write_mode: str = "overwrite"
    nlist: int = Field(default=64, ge=1, le=4096)
    hnsw_m: int = Field(default=32, ge=4, le=128)

    @model_validator(mode="after")
    def validate_options(self) -> "VectorWriterParameters":
        if self.backend.lower() != "faiss":
            raise ValueError("Phase 1 supports only the FAISS backend")
        if self.metric.lower() not in {"cosine", "l2", "ip"}:
            raise ValueError("metric must be one of: cosine, l2, ip")
        if self.index_type.lower() not in {"flat", "hnsw_flat", "ivf_flat"}:
            raise ValueError("index_type must be one of: flat, hnsw_flat, ivf_flat")
        if self.write_mode.lower() not in {"overwrite", "append"}:
            raise ValueError("write_mode must be one of: overwrite, append")
        return self


class SimilaritySearchParameters(BaseModel):
    top_k: int = Field(default=5, ge=1, le=100)
    score_threshold: float = Field(default=0.0, ge=0.0, le=1.0)
    filter: dict[str, Any] | None = None
    include_metadata: bool = True

    @field_validator("filter", mode="before")
    @classmethod
    def parse_filter(cls, value: Any) -> dict[str, Any] | None:
        if value is None or value == "" or value == {}:
            return None
        parsed = parse_json_value(value, "filter")
        if not isinstance(parsed, dict):
            raise ValueError("filter must be a JSON object")
        return parsed


class ContextInjectorParameters(BaseModel):
    max_context_items: int = Field(default=5, ge=1, le=50)
    include_citations: bool = True
    separator: str = "\n\n"


def _normalize_vector(vector: list[float]) -> list[float]:
    array = np.asarray(vector, dtype=np.float32)
    norm = float(np.linalg.norm(array))
    if norm == 0.0:
        return array.tolist()
    return (array / norm).tolist()


def _batch_embedder_executor(parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    chunks = inputs.get("chunks") or []
    provider = normalize_provider_name(parameters.get("provider"), default="ollama")
    model_name = coerce_text(parameters.get("model_name") or "nomic-embed-text").strip() or "nomic-embed-text"
    normalize = bool(parameters.get("normalize", True))
    dimensions = parameters.get("dimensions")
    max_retries = int(parameters.get("max_retries", 1))

    points: list[dict[str, Any]] = []
    for chunk in chunks:
        if not isinstance(chunk, dict):
            continue
        last_error: Exception | None = None
        vector: list[float] | None = None
        for _ in range(max_retries + 1):
            try:
                vector = provider_service.embed_text(
                    provider=provider,
                    model=model_name,
                    text=str(chunk.get("text", "")),
                    dimensions=dimensions,
                )
                break
            except Exception as exc:  # noqa: BLE001
                last_error = exc
        if vector is None:
            raise ValueError(str(last_error or "Embedding generation failed"))
        if normalize:
            vector = _normalize_vector(vector)
        points.append(
            {
                "id": str(chunk.get("id", "")),
                "chunk_id": str(chunk.get("id", "")),
                "document_id": str(chunk.get("document_id", "")),
                "text": str(chunk.get("text", "")),
                "source_uri": str(chunk.get("source_uri", "")),
                "vector": vector,
                "embedding_provider": provider,
                "embedding_model": model_name,
                "metadata": chunk.get("metadata", {}) if isinstance(chunk.get("metadata"), dict) else {},
            }
        )
    return {"points": points}


def _vector_db_writer_executor(parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    points = inputs.get("points") or []
    adapter = get_vector_store_adapter(coerce_text(parameters.get("backend") or "faiss"))
    handle = adapter.write_points(
        index_name=coerce_text(parameters.get("index_name")).strip(),
        storage_directory=coerce_text(parameters.get("storage_directory") or "").strip(),
        metric=coerce_text(parameters.get("metric") or "cosine"),
        index_type=coerce_text(parameters.get("index_type") or "flat"),
        write_mode=coerce_text(parameters.get("write_mode") or "overwrite"),
        points=points,
        nlist=int(parameters.get("nlist", 64)),
        hnsw_m=int(parameters.get("hnsw_m", 32)),
    )
    return {"store": handle.model_dump(mode="json")}


def _similarity_search_executor(parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    query = coerce_text(inputs.get("query") or "").strip()
    if not query:
        raise ValueError("SIMILARITY_SEARCH requires a query input")
    store = inputs.get("store") or {}
    if not isinstance(store, dict):
        raise ValueError("SIMILARITY_SEARCH requires a vector store handle")
    provider = normalize_provider_name(store.get("embedding_provider"), default="ollama")
    model = coerce_text(store.get("embedding_model") or "nomic-embed-text").strip() or "nomic-embed-text"
    vector = provider_service.embed_text(provider=provider, model=model, text=query, dimensions=store.get("dimension"))
    if str(store.get("metric", "cosine")).lower() == "cosine":
        vector = _normalize_vector(vector)

    adapter = get_vector_store_adapter(coerce_text(store.get("backend") or "faiss"))
    try:
        hits = adapter.search(
            store=store,
            query_vector=vector,
            top_k=int(parameters.get("top_k", 5)),
            score_threshold=float(parameters.get("score_threshold", 0.0)),
            filter_spec=parameters.get("filter"),
            include_metadata=bool(parameters.get("include_metadata", True)),
        )
    except VectorStoreError as exc:
        raise ValueError(str(exc)) from exc
    return {"results": {"query": query, "hits": [hit.model_dump(mode="json") for hit in hits]}}


def _context_injector_executor(parameters: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    results = inputs.get("results") or {}
    if not isinstance(results, dict):
        raise ValueError("CONTEXT_INJECTOR requires retrieval results")
    hits = results.get("hits", [])
    if not isinstance(hits, list):
        raise ValueError("retrieval results must contain a hits array")
    max_items = int(parameters.get("max_context_items", 5))
    include_citations = bool(parameters.get("include_citations", True))
    separator = coerce_text(parameters.get("separator") or "\n\n")

    sections: list[str] = []
    for index, hit in enumerate(hits[:max_items], start=1):
        if not isinstance(hit, dict):
            continue
        text = str(hit.get("text", "")).strip()
        if not text:
            continue
        if include_citations:
            source_uri = str(hit.get("source_uri", ""))
            sections.append(f"[{index}] {source_uri}\n{text}")
        else:
            sections.append(text)
    return {"text": separator.join(sections).strip()}


RAG_HANDLERS = {
    "batch_embedder": NodeHandler(executor=_batch_embedder_executor, parameter_model=BatchEmbedderParameters),
    "vector_db_writer": NodeHandler(executor=_vector_db_writer_executor, parameter_model=VectorWriterParameters),
    "similarity_search": NodeHandler(executor=_similarity_search_executor, parameter_model=SimilaritySearchParameters),
    "context_injector": NodeHandler(executor=_context_injector_executor, parameter_model=ContextInjectorParameters),
}
