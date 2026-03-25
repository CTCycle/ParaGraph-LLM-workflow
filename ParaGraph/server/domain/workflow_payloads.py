from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator

from ParaGraph.server.domain.nodecatalog import NodeDataType, ProviderModelDefinition


class ImagePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str


class DocumentRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    text: str
    source_uri: str
    mime_type: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class DatabaseConnectionHandle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    engine: str
    database_name: str | None = None
    host: str | None = None
    port: int | None = None
    username: str | None = None
    password: str | None = None
    file_path: str | None = None
    read_only: bool = True
    options: dict[str, Any] = Field(default_factory=dict)


class ChunkRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    document_id: str
    text: str
    source_uri: str
    chunk_index: int
    token_count: int
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("chunk_index", "token_count")
    @classmethod
    def validate_non_negative(cls, value: int) -> int:
        if value < 0:
            raise ValueError("chunk metadata values must be non-negative")
        return value


class VectorPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    chunk_id: str
    document_id: str
    text: str
    source_uri: str
    vector: list[float]
    embedding_provider: str
    embedding_model: str
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("vector")
    @classmethod
    def validate_vector(cls, value: list[float]) -> list[float]:
        if not value:
            raise ValueError("vector points must include at least one dimension")
        return value


class VectorStoreHandle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    backend: str
    index_name: str
    artifact_path: str
    metric: str
    dimension: int
    embedding_provider: str
    embedding_model: str
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("dimension")
    @classmethod
    def validate_dimension(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("vector store dimensions must be greater than zero")
        return value


class RetrievalHit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    chunk_id: str
    document_id: str
    text: str
    source_uri: str
    score: float
    metadata: dict[str, Any] = Field(default_factory=dict)


class RetrievalResults(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str
    hits: list[RetrievalHit] = Field(default_factory=list)


DATA_TYPE_ADAPTERS: dict[NodeDataType, TypeAdapter[Any]] = {
    "TEXT": TypeAdapter(str),
    "IMAGE": TypeAdapter(ImagePayload),
    "VIDEO": TypeAdapter(dict[str, Any]),
    "AUDIO": TypeAdapter(dict[str, Any]),
    "DOCUMENT": TypeAdapter(DocumentRecord),
    "DOCUMENT_LIST": TypeAdapter(list[DocumentRecord]),
    "DATABASE_CONNECTION": TypeAdapter(DatabaseConnectionHandle),
    "CHUNK": TypeAdapter(ChunkRecord),
    "CHUNK_LIST": TypeAdapter(list[ChunkRecord]),
    "EMBEDDING": TypeAdapter(list[float]),
    "VECTOR_POINT_LIST": TypeAdapter(list[VectorPoint]),
    "VECTOR_STORE_HANDLE": TypeAdapter(VectorStoreHandle),
    "RETRIEVAL_RESULTS": TypeAdapter(RetrievalResults),
    "TOKEN_IDS": TypeAdapter(list[int]),
    "JSON": TypeAdapter(dict[str, Any] | list[Any] | str | int | float | bool | None),
    "MODEL_HANDLE": TypeAdapter(ProviderModelDefinition),
    "DATASET": TypeAdapter(dict[str, Any]),
    "BOOLEAN": TypeAdapter(bool),
    "ANY": TypeAdapter(Any),
}


def _normalize_validated_value(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, list):
        return [_normalize_validated_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _normalize_validated_value(item) for key, item in value.items()}
    return value


def validate_data_type(data_type: NodeDataType, value: Any) -> Any:
    return _normalize_validated_value(DATA_TYPE_ADAPTERS[data_type].validate_python(value))
