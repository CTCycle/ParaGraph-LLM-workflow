from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


NodeCategory = Literal["input", "model", "processing", "fragmentation", "output", "serialization", "control"]
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
    "TOKEN_IDS",
    "JSON",
    "MODEL_HANDLE",
    "DATASET",
    "BOOLEAN",
    "ANY",
]
ModelVisibility = Literal["public", "private", "gated", "unknown"]
ModelVisibilityFilter = Literal["all", "public", "private", "gated"]
HuggingFaceSortBy = Literal["relevance", "downloads", "likes", "updated"]


class NodePortDefinition(BaseModel):
    name: str
    data_type: NodeDataType
    required: bool = True
    accepts_multiple: bool = False
    description: str | None = None


NodeControllerScope = Literal["source", "target", "both"]


class NodeControllerDefinition(BaseModel):
    name: str
    data_type: NodeDataType
    required: bool = True
    accepts_multiple: bool = False
    scope: NodeControllerScope = "target"
    description: str | None = None


class NodeParameterDefinition(BaseModel):
    name: str
    data_type: NodeDataType
    default: Any | None = None
    constraints: dict[str, Any] = Field(default_factory=dict)
    ui_control: str = "text"
    description: str | None = None


class NodeUiDefinition(BaseModel):
    default_width: int = 280
    accent_color: str = "#4aa3ff"
    icon: str | None = None
    collapsed_by_default: bool = False


class NodePluginRuntimeDefinition(BaseModel):
    script_path: str
    entrypoint: str = "execute"


class NodeRuntimeDefinition(BaseModel):
    executor_key: str
    cacheable: bool = False
    deterministic: bool = True
    side_effecting: bool = False
    plugin: NodePluginRuntimeDefinition | None = None


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


class NodeCatalogResponse(BaseModel):
    nodes: list[NodeManifest] = Field(default_factory=list)


class ProviderCapability(BaseModel):
    provider: str
    supports_chat: bool = True
    supports_embeddings: bool = False
    supports_structured_output: bool = False
    supports_streaming: bool = False
    supports_tool_calling: bool = False


class ProviderCatalogResponse(BaseModel):
    providers: list[ProviderCapability] = Field(default_factory=list)


class ProviderModelDefinition(BaseModel):
    provider: str
    model: str
    label: str
    supports_image: bool = False
    supports_reasoning: bool = False
    supports_structured_output: bool = True


class ProviderModelCatalogResponse(BaseModel):
    models: list[ProviderModelDefinition] = Field(default_factory=list)


class OllamaLibraryModelDefinition(BaseModel):
    model: str
    description: str | None = None
    homepage: str
    pulled: bool = False


class OllamaLibraryCatalogResponse(BaseModel):
    models: list[OllamaLibraryModelDefinition] = Field(default_factory=list)
    total_count: int = 0
    pulled_count: int = 0
    refreshed_at: str
    source: str = "https://ollama.com/library"


class OllamaModelPullRequest(BaseModel):
    model: str = Field(min_length=1, max_length=255)


class OllamaModelPullResponse(BaseModel):
    ok: bool
    model: str
    message: str


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


class HuggingFaceModelCatalogResponse(BaseModel):
    models: list[HuggingFaceModelDefinition] = Field(default_factory=list)
    page: int
    page_size: int
    has_more: bool
    using_token: bool = False
    warning: str | None = None
    available_tasks: list[str] = Field(default_factory=list)
    available_libraries: list[str] = Field(default_factory=list)
