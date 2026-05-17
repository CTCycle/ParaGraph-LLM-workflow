from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator

from server.domain.chat_history import ChatHistoryHandle
from server.domain.node_catalog import NodeDataType, ProviderModelDefinition

###############################################################################
class ImagePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str

###############################################################################
class DocumentRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    text: str
    source_uri: str
    mime_type: str
    metadata: dict[str, Any] = Field(default_factory=dict)

###############################################################################
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

###############################################################################
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

###############################################################################
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

###############################################################################
class VectorStoreHandle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    backend: str
    index_name: str
    artifact_path: str
    metric: str
    dimension: int
    embedding_provider: str
    embedding_model: str
    collection_name: str = ""
    indexed_metadata_fields: list[str] = Field(default_factory=list)
    keyword_index_status: str = "unsupported"
    vector_index_status: str = "unknown"
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("dimension")
    @classmethod
    def validate_dimension(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("vector store dimensions must be greater than zero")
        return value

###############################################################################
class RetrievalHit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    chunk_id: str
    document_id: str
    text: str
    source_uri: str
    score: float
    metadata: dict[str, Any] = Field(default_factory=dict)

###############################################################################
class RetrievalResults(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str
    hits: list[RetrievalHit] = Field(default_factory=list)

###############################################################################
class TokenizerOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tokenizer_name: str
    revision: str = ""
    records: list[dict[str, Any]] = Field(default_factory=list)

###############################################################################
class MetadataRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metadata: dict[str, Any] = Field(default_factory=dict)

###############################################################################
class ToolDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    description: str = ""
    parameters_schema: dict[str, Any]
    source_type: str
    source_ref: str = ""
    entrypoint: str = ""
    callable_name: str = ""

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError("tool name is required")
        return normalized

###############################################################################
class ToolCollectionHandle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tools: list[ToolDefinition]
    metadata: dict[str, Any] = Field(default_factory=dict)

###############################################################################
class ToolCallRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    instruction: str
    context: dict[str, Any] = Field(default_factory=dict)

###############################################################################
class ToolCallSelection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    raw_model_response: Any = None

###############################################################################
class ToolCallResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    result: Any = None
    raw_model_response: Any = None
    metadata: dict[str, Any] = Field(default_factory=dict)

###############################################################################
class SqlOperationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    affected_rows: int = 0
    rows: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


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
    "TOKENIZER_OUTPUT": TypeAdapter(TokenizerOutput),
    "METADATA": TypeAdapter(MetadataRecord),
    "METADATA_LIST": TypeAdapter(list[MetadataRecord]),
    "TOOL_DEFINITION": TypeAdapter(ToolDefinition),
    "TOOL_COLLECTION_HANDLE": TypeAdapter(ToolCollectionHandle),
    "TOOL_CALL_RESULT": TypeAdapter(ToolCallResult),
    "SQL_OPERATION_RESULT": TypeAdapter(SqlOperationResult),
    "JSON": TypeAdapter(dict[str, Any] | list[Any] | str | int | float | bool | None),
    "MODEL_HANDLE": TypeAdapter(ProviderModelDefinition),
    "CHAT_HISTORY_HANDLE": TypeAdapter(ChatHistoryHandle),
    "DATASET": TypeAdapter(dict[str, Any]),
    "BOOLEAN": TypeAdapter(bool),
    "ANY": TypeAdapter(Any),
}

###############################################################################
def _normalize_validated_value(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, list):
        return [_normalize_validated_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _normalize_validated_value(item) for key, item in value.items()}
    return value

###############################################################################
def validate_data_type(data_type: NodeDataType, value: Any) -> Any:
    return _normalize_validated_value(
        DATA_TYPE_ADAPTERS[data_type].validate_python(value)
    )

