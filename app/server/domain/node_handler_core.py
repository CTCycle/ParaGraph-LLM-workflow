from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


###############################################################################
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


###############################################################################
def _validate_schema_keys(schema: dict[str, Any], path: str) -> None:
    allowed_keys = {
        "type",
        "properties",
        "required",
        "items",
        "additionalProperties",
        "enum",
    }
    unsupported = sorted(set(schema) - allowed_keys)
    if unsupported:
        raise ValueError(
            f"Unsupported JSON Schema keys at {path}: {', '.join(unsupported)}"
        )

###############################################################################
def _validate_schema_type(schema: dict[str, Any], path: str) -> None:
    schema_type = schema.get("type")
    if schema_type is not None and schema_type not in {
        "object",
        "array",
        "string",
        "number",
        "integer",
        "boolean",
        "null",
    }:
        raise ValueError(f"Unsupported JSON Schema type at {path}: {schema_type}")

###############################################################################
def _validate_schema_properties(schema: dict[str, Any], path: str) -> None:
    properties = schema.get("properties")
    if properties is None:
        return
    if not isinstance(properties, dict):
        raise ValueError(f"properties at {path} must be an object")
    for key, value in properties.items():
        _validate_schema_definition(value, f"{path}.properties.{key}")

###############################################################################
def _validate_schema_required(schema: dict[str, Any], path: str) -> None:
    required = schema.get("required")
    if required is not None and (
        not isinstance(required, list)
        or not all(isinstance(item, str) for item in required)
    ):
        raise ValueError(f"required at {path} must be an array of strings")

###############################################################################
def _validate_schema_items(schema: dict[str, Any], path: str) -> None:
    if "items" in schema:
        _validate_schema_definition(schema["items"], f"{path}.items")

###############################################################################
def _validate_schema_additional_properties(schema: dict[str, Any], path: str) -> None:
    additional_properties = schema.get("additionalProperties")
    if additional_properties is not None and not isinstance(
        additional_properties, bool
    ):
        raise ValueError(f"additionalProperties at {path} must be a boolean")

###############################################################################
def _validate_schema_enum(schema: dict[str, Any], path: str) -> None:
    enum = schema.get("enum")
    if enum is not None and not isinstance(enum, list):
        raise ValueError(f"enum at {path} must be an array")


###############################################################################
def _validate_schema_definition(schema: Any, path: str = "$") -> None:
    if not isinstance(schema, dict):
        raise ValueError("response_schema must be a JSON object")

    _validate_schema_keys(schema, path)
    _validate_schema_type(schema, path)
    _validate_schema_properties(schema, path)
    _validate_schema_required(schema, path)
    _validate_schema_items(schema, path)
    _validate_schema_additional_properties(schema, path)
    _validate_schema_enum(schema, path)

###############################################################################
class PromptParameters(BaseModel):
    prompt_text: str = ""

###############################################################################
class PromptTemplateParameters(BaseModel):
    template: str = ""

    @field_validator("template")
    @classmethod
    def validate_template(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("template is required")
        return value

###############################################################################
class ImageInputParameters(BaseModel):
    file_path: str = ""

###############################################################################
class ModelProviderParameters(BaseModel):
    provider: str = "ollama"
    model_name: str = ""
    timeout_seconds: float = Field(default=120, ge=1)

###############################################################################
class ChatParameters(BaseModel):
    provider: str | None = None
    model_name: str | None = None
    context_window: int = Field(default=0, ge=0)
    max_tokens: int = Field(default=512, ge=1)
    use_reasoning: bool = False

###############################################################################
class InMemoryChatHistoryParameters(BaseModel):
    max_messages: int = Field(default=20, ge=1)
    separator: str = "\n"
    keep_prompt_type: bool = True

###############################################################################
class PersistedChatHistoryParameters(InMemoryChatHistoryParameters):
    storage_backend: Literal["file", "database"] = "file"

###############################################################################
class StructuredParameters(ChatParameters):
    response_schema: dict[str, Any]

    @field_validator("response_schema", mode="before")
    @classmethod
    def validate_schema(cls, value: Any) -> dict[str, Any]:
        schema = _parse_json_value(value, "response_schema")
        _validate_schema_definition(schema)
        return schema

###############################################################################
class EmbeddingParameters(BaseModel):
    provider: str = "ollama"
    model_name: str = "nomic-embed-text"
    tokenizer_name: str = ""

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, value: str) -> str:
        normalized = str(value or "").strip().lower()
        allowed = {"openai", "gemini", "huggingface", "ollama"}
        if normalized not in allowed:
            raise ValueError(
                "provider must be one of: openai, gemini, huggingface, ollama"
            )
        return normalized

    @field_validator("model_name", "tokenizer_name")
    @classmethod
    def normalize_model_reference(cls, value: str) -> str:
        return str(value or "").strip()

###############################################################################
class SimilaritySearchParameters(BaseModel):
    similarity_strategy: str = "cosine"
    search_mode: str = "vector"
    search_engine: str = "native"
    metadata_filter: dict[str, Any] | None = None
    ann_search_depth: int = Field(default=100, ge=10, le=500)
    top_k: int = Field(default=5, ge=1, le=100)
    score_threshold: float = Field(default=0.0, ge=0.0, le=1.0)
    include_metadata: bool = True
    keyword_query: str = ""
    vector_weight: float = Field(default=0.5, ge=0.0, le=1.0)
    keyword_weight: float = Field(default=0.5, ge=0.0, le=1.0)

    @field_validator("similarity_strategy")
    @classmethod
    def validate_similarity_strategy(cls, value: str) -> str:
        normalized = str(value or "").strip().lower()
        if normalized not in {"cosine", "euclidean", "dot"}:
            raise ValueError(
                "similarity_strategy must be one of: cosine, euclidean, dot"
            )
        return normalized

    @field_validator("search_mode")
    @classmethod
    def validate_search_mode(cls, value: str) -> str:
        normalized = str(value or "").strip().lower()
        if normalized not in {"vector", "hybrid"}:
            raise ValueError("search_mode must be one of: vector, hybrid")
        return normalized

    @field_validator("search_engine")
    @classmethod
    def validate_search_engine(cls, value: str) -> str:
        normalized = str(value or "").strip().lower()
        if normalized not in {"native", "faiss_augmented"}:
            raise ValueError("search_engine must be one of: native, faiss_augmented")
        return normalized

    @field_validator("metadata_filter", mode="before")
    @classmethod
    def validate_metadata_filter(cls, value: Any) -> dict[str, Any] | None:
        if value is None:
            return None
        parsed = _parse_json_value(value, "metadata_filter")
        if not isinstance(parsed, dict):
            raise ValueError("metadata_filter must be a JSON object")
        return parsed

    @model_validator(mode="after")
    def validate_hybrid_weights(self) -> "SimilaritySearchParameters":
        if self.search_mode == "hybrid":
            total_weight = float(self.vector_weight) + float(self.keyword_weight)
            if total_weight <= 0:
                raise ValueError(
                    "Hybrid search requires vector_weight + keyword_weight > 0"
                )
        if self.search_engine == "faiss_augmented" and self.search_mode != "vector":
            raise ValueError(
                "faiss_augmented search_engine currently supports search_mode='vector' only"
            )
        return self

###############################################################################
class TextSplitParameters(BaseModel):
    delimiter: str = "\n"

###############################################################################
class VectorStoreParameters(BaseModel):
    provider: str = "lancedb"
    index_name: str = "documents"
    namespace: str = ""
    storage_path: str = ""
    endpoint_url: str = ""
    api_key: str = ""
    collection_name: str = ""
    database_name: str = ""
    provider_config: dict[str, Any] = Field(default_factory=dict)
    write_mode: str = "overwrite"
    distance_metric: str = "cosine"

    @field_validator("write_mode")
    @classmethod
    def validate_write_mode(cls, value: str) -> str:
        normalized = str(value or "").strip().lower()
        if normalized not in {"overwrite", "append"}:
            raise ValueError("write_mode must be 'overwrite' or 'append'")
        return normalized

    @field_validator("distance_metric")
    @classmethod
    def validate_distance_metric(cls, value: str) -> str:
        normalized = str(value or "").strip().lower()
        if normalized not in {"l2", "cosine", "dot"}:
            raise ValueError("distance_metric must be one of: l2, cosine, dot")
        return normalized

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, value: str) -> str:
        normalized = str(value or "").strip().lower()
        allowed = {
            "lancedb",
            "qdrant",
            "pinecone",
            "weaviate",
            "milvus",
            "chroma",
            "faiss",
        }
        if normalized not in allowed:
            raise ValueError(
                "provider must be one of: lancedb, qdrant, pinecone, weaviate, milvus, chroma, faiss"
            )
        return normalized

    @field_validator("index_name")
    @classmethod
    def validate_index_name(cls, value: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError("index_name is required")
        return normalized

    @field_validator("provider_config", mode="before")
    @classmethod
    def validate_provider_config(cls, value: Any) -> dict[str, Any]:
        if value is None:
            return {}
        parsed = _parse_json_value(value, "provider_config")
        if not isinstance(parsed, dict):
            raise ValueError("provider_config must be a JSON object")
        return parsed

    @model_validator(mode="after")
    def validate_provider_requirements(self) -> "VectorStoreParameters":
        local_storage_providers = {"lancedb", "chroma", "faiss"}
        remote_endpoint_providers = {"qdrant", "pinecone", "weaviate", "milvus"}

        storage_path = str(self.storage_path or "").strip()
        endpoint_url = str(self.endpoint_url or "").strip()

        if self.provider in local_storage_providers and not storage_path:
            raise ValueError(f"storage_path is required for provider '{self.provider}'")
        if self.provider in remote_endpoint_providers and not endpoint_url:
            raise ValueError(f"endpoint_url is required for provider '{self.provider}'")
        return self

###############################################################################
class RerankParameters(BaseModel):
    strategy: str = "original_score"
    score_mode: str = "replace"
    metadata_field: str = ""
    metadata_value: str = ""
    original_score_weight: float = 1.0
    term_overlap_weight: float = 1.0
    phrase_boost: float = 1.0
    metadata_boost: float = 1.0
    top_k: int = Field(default=0, ge=0)

    @field_validator("strategy")
    @classmethod
    def validate_strategy(cls, value: str) -> str:
        normalized = str(value or "").strip().lower()
        allowed = {
            "original_score",
            "term_overlap",
            "exact_phrase",
            "metadata_match",
            "weighted_composite",
        }
        if normalized not in allowed:
            raise ValueError(
                "strategy must be one of: original_score, term_overlap, exact_phrase, metadata_match, weighted_composite"
            )
        return normalized

    @field_validator("score_mode")
    @classmethod
    def validate_score_mode(cls, value: str) -> str:
        normalized = str(value or "").strip().lower()
        if normalized not in {"replace", "boost"}:
            raise ValueError("score_mode must be one of: replace, boost")
        return normalized

###############################################################################
class _SaveNodeParameters(BaseModel):
    output_path: str = ""
    extension: str = ".txt"
    client_side_write: bool = False

    @field_validator("extension")
    @classmethod
    def validate_extension(cls, value: str) -> str:
        normalized = str(value or "").strip().lower()
        if normalized not in {".txt", ".md", ".doc", ".pdf"}:
            raise ValueError("extension must be one of: .txt, .md, .doc, .pdf")
        return normalized

###############################################################################
class SaveAsFileParameters(_SaveNodeParameters):
    pass

###############################################################################
class SaveAsFolderParameters(_SaveNodeParameters):
    pass

###############################################################################
class StorageParameters(BaseModel):
    storage_path: str = ""

    @field_validator("storage_path")
    @classmethod
    def validate_storage_path(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("storage_path is required. Select a local path.")
        return normalized

###############################################################################
class RouterParameters(BaseModel):
    expected_value: str = ""
