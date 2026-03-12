from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


NodeCategory = Literal["input", "model", "processing", "output", "serialization", "control"]
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


class NodePortDefinition(BaseModel):
    name: str
    data_type: NodeDataType
    required: bool = True
    accepts_multiple: bool = False
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


class NodeRuntimeDefinition(BaseModel):
    executor_key: str
    cacheable: bool = False
    deterministic: bool = True
    side_effecting: bool = False


class NodeManifest(BaseModel):
    id: str
    version: int = 1
    name: str
    category: NodeCategory
    description: str
    inputs: list[NodePortDefinition] = Field(default_factory=list)
    outputs: list[NodePortDefinition] = Field(default_factory=list)
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
