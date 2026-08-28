from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


NodeCategory = Literal[
    "input",
    "web",
    "prompt",
    "model",
    "memory",
    "processing",
    "retrieval",
    "embeddings",
    "text_segmentation",
    "output",
    "serialization",
    "vector_storage",
    "database",
    "control",
]
NodeDataType = Literal[
    "TEXT",
    "IMAGE",
    "VIDEO",
    "AUDIO",
    "DOCUMENT",
    "DOCUMENT_LIST",
    "DATABASE_CONNECTION",
    "CHUNK",
    "CHUNK_LIST",
    "EMBEDDING",
    "VECTOR_POINT_LIST",
    "VECTOR_STORE_HANDLE",
    "RETRIEVAL_RESULTS",
    "TOKENIZER_OUTPUT",
    "METADATA",
    "METADATA_LIST",
    "TOOL_DEFINITION",
    "TOOL_COLLECTION_HANDLE",
    "TOOL_CALL_RESULT",
    "SQL_OPERATION_RESULT",
    "JSON",
    "MODEL_HANDLE",
    "CHAT_HISTORY_HANDLE",
    "DATASET",
    "BOOLEAN",
    "ANY",
]
ModelVisibility = Literal["public", "private", "gated", "unknown"]
ModelVisibilityFilter = Literal["all", "public", "private", "gated"]
HuggingFaceSortBy = Literal["relevance", "downloads", "likes", "updated"]
HuggingFaceDownloadJobStatus = Literal[
    "pending", "running", "completed", "failed", "cancelled"
]
VectorMetric = Literal["cosine", "l2", "dot"]
VectorSearchMode = Literal["vector", "keyword", "hybrid"]
VectorSearchEngine = Literal["native", "faiss_augmented"]
VectorFilterOperator = Literal[
    "eq", "in", "exists", "contains", "gt", "gte", "lt", "lte"
]
VectorScoreSemantics = Literal["normalized_similarity", "native_similarity"]
VectorStoreOperation = Literal[
    "insert",
    "upsert",
    "update",
    "delete_ids",
    "delete_document",
    "delete_filter",
    "inspect",
    "delete_collection",
    "reload",
    "search",
    "close",
]

###############################################################################
class NodePortDefinition(BaseModel):
    name: str
    data_type: NodeDataType
    required: bool = True
    accepts_multiple: bool = False
    description: str | None = None


NodeControllerScope = Literal["source", "target", "both"]

###############################################################################
class NodeControllerDefinition(BaseModel):
    name: str
    data_type: NodeDataType
    required: bool = True
    accepts_multiple: bool = False
    scope: NodeControllerScope = "target"
    description: str | None = None

###############################################################################
class NodeParameterDefinition(BaseModel):
    name: str
    data_type: NodeDataType
    default: Any | None = None
    constraints: dict[str, Any] = Field(default_factory=dict)
    ui_control: str = "text"
    description: str | None = None

###############################################################################
class NodeUiDefinition(BaseModel):
    default_width: int = 280
    accent_color: str = "#4aa3ff"
    icon: str | None = None
    collapsed_by_default: bool = False

###############################################################################
class NodePluginRuntimeDefinition(BaseModel):
    script_path: str
    entrypoint: str = "execute"

###############################################################################
class NodeRuntimeDefinition(BaseModel):
    executor_key: str
    cacheable: bool = False
    deterministic: bool = True
    side_effecting: bool = False
    destructive: bool = False
    idempotent: bool = False
    plugin: NodePluginRuntimeDefinition | None = None

###############################################################################
class NodeManifest(BaseModel):
    id: str
    version: int = 1
    name: str
    category: NodeCategory
    description: str
    inputs: list[NodePortDefinition] = Field(default_factory=list)
    outputs: list[NodePortDefinition] = Field(default_factory=list)
    controllers: list[NodeControllerDefinition] = Field(default_factory=list)
    parameters: list[NodeParameterDefinition] = Field(default_factory=list)
    ui: NodeUiDefinition = Field(default_factory=NodeUiDefinition)
    runtime: NodeRuntimeDefinition

    # -------------------------------------------------------------------------
    @field_validator("category", mode="before")
    @classmethod
    def normalize_category(cls, value: str) -> str:
        return str(value or "").strip().lower()

    # -------------------------------------------------------------------------
    @model_validator(mode="after")
    def validate_unique_contract_names(self) -> NodeManifest:
        for label, definitions in (
            ("input", self.inputs),
            ("output", self.outputs),
            ("controller", self.controllers),
            ("parameter", self.parameters),
        ):
            names = [definition.name for definition in definitions]
            duplicates = sorted(
                name for name in set(names) if names.count(name) > 1
            )
            if duplicates:
                joined = ", ".join(duplicates)
                raise ValueError(
                    f"Node '{self.id}' has duplicate {label} names: {joined}"
                )
        return self

###############################################################################
class VectorStoreCapabilities(BaseModel):
    """Authoritative backend capability contract shared by catalog and runtime."""

    model_config = ConfigDict(extra="forbid")

    backend: str = Field(min_length=1)
    supported_metrics: list[VectorMetric] = Field(default_factory=list)
    supported_search_modes: list[VectorSearchMode] = Field(
        default_factory=lambda: ["vector"]
    )
    supported_search_engines: list[VectorSearchEngine] = Field(
        default_factory=lambda: ["native"]
    )
    supports_namespaces: bool = False
    supports_metadata_filtering: bool = True
    supported_filter_operators: list[VectorFilterOperator] = Field(
        default_factory=list
    )
    supports_filter_groups: bool = True
    supports_minimum_should_match: bool = False
    supports_keyword_index: bool = False
    supported_operations: list[VectorStoreOperation] = Field(default_factory=list)
    score_semantics_by_metric: dict[VectorMetric, VectorScoreSemantics] = Field(
        default_factory=dict
    )

    # -------------------------------------------------------------------------
    @model_validator(mode="after")
    def validate_contract(self) -> VectorStoreCapabilities:
        for field_name in (
            "supported_metrics",
            "supported_search_modes",
            "supported_search_engines",
            "supported_filter_operators",
            "supported_operations",
        ):
            values = getattr(self, field_name)
            if len(values) != len(set(values)):
                raise ValueError(f"{field_name} must not contain duplicates")
        supported_metrics = set(self.supported_metrics)
        missing_score_contracts = supported_metrics.difference(
            self.score_semantics_by_metric
        )
        if missing_score_contracts:
            raise ValueError(
                "score_semantics_by_metric must define every supported metric: "
                + ", ".join(sorted(missing_score_contracts))
            )
        if not self.supports_metadata_filtering and self.supported_filter_operators:
            raise ValueError(
                "unsupported metadata filtering cannot advertise filter operators"
            )
        if not self.supports_filter_groups and self.supports_minimum_should_match:
            raise ValueError(
                "minimum_should_match requires grouped filter support"
            )
        return self

###############################################################################
class NodeCatalogResponse(BaseModel):
    nodes: list[NodeManifest] = Field(default_factory=list)
    vector_store_capabilities: list[VectorStoreCapabilities] = Field(
        default_factory=list
    )

###############################################################################
class ProviderCapability(BaseModel):
    provider: str
    supports_chat: bool = True
    supports_embeddings: bool = False
    supports_structured_output: bool = False
    supports_streaming: bool = False
    supports_tool_calling: bool = False
    supports_tool_selection: bool = False
    supports_native_tool_protocol: bool = False

###############################################################################
class ProviderCatalogResponse(BaseModel):
    providers: list[ProviderCapability] = Field(default_factory=list)

###############################################################################
class ProviderModelDefinition(BaseModel):
    provider: str
    model: str
    label: str
    supports_image: bool = False
    supports_embeddings: bool = False
    supports_reasoning: bool = False
    supports_structured_output: bool = True
    timeout_s: float | None = Field(default=None, ge=1)

###############################################################################
class ProviderModelCatalogResponse(BaseModel):
    models: list[ProviderModelDefinition] = Field(default_factory=list)

###############################################################################
class OllamaLibraryModelDefinition(BaseModel):
    model: str
    description: str | None = None
    homepage: str
    pulled: bool = False

###############################################################################
class OllamaLibraryCatalogResponse(BaseModel):
    models: list[OllamaLibraryModelDefinition] = Field(default_factory=list)
    total_count: int = 0
    pulled_count: int = 0
    refreshed_at: str
    source: str = "https://ollama.com/library"

###############################################################################
class OllamaModelPullRequest(BaseModel):
    model: str = Field(min_length=1, max_length=255)

###############################################################################
class OllamaModelPullResponse(BaseModel):
    ok: bool
    model: str
    message: str

###############################################################################
class HuggingFaceModelDefinition(BaseModel):
    repo_id: str
    author: str | None = None
    task: str | None = None
    library: str | None = None
    likes: int | None = None
    downloads: int | None = None
    visibility: ModelVisibility = "unknown"
    private: bool | None = None
    gated: bool | None = None
    last_modified: str | None = None
    url: str
    downloaded: bool = False
    size_bytes: int | None = None

###############################################################################
class HuggingFaceModelCatalogResponse(BaseModel):
    models: list[HuggingFaceModelDefinition] = Field(default_factory=list)
    page: int
    page_size: int
    has_more: bool
    using_token: bool = False
    warning: str | None = None
    available_tasks: list[str] = Field(default_factory=list)
    available_libraries: list[str] = Field(default_factory=list)

###############################################################################
class HuggingFaceModelDownloadRequest(BaseModel):
    repo_id: str = Field(min_length=3, max_length=240)

###############################################################################
class HuggingFaceModelDownloadResponse(BaseModel):
    ok: bool
    repo_id: str
    message: str
    destination_path: str
    already_downloaded: bool = False
    job_id: str | None = None
    status: HuggingFaceDownloadJobStatus = "completed"
    progress: float = 100.0
    downloaded_bytes: int = 0
    total_bytes: int | None = None
    poll_interval: float = 1.0

###############################################################################
class HuggingFaceModelDownloadStatusResponse(BaseModel):
    job_id: str
    repo_id: str
    destination_path: str
    status: HuggingFaceDownloadJobStatus
    progress: float
    message: str | None = None
    downloaded_bytes: int = 0
    total_bytes: int | None = None
    error: str | None = None

###############################################################################
class HuggingFaceModelDownloadCancelResponse(BaseModel):
    ok: bool
    job_id: str
    repo_id: str
    message: str
