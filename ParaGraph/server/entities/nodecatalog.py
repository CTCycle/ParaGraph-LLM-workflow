from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from ParaGraph.server.entities.workflowmodel import NodeCategory, PortDirection


class PortSchema(BaseModel):
    handle: str
    label: str
    direction: PortDirection
    data_type: str


class ConfigFieldSchema(BaseModel):
    key: str
    label: str
    field_type: str
    required: bool = False
    default: Any | None = None
    options: list[str] = Field(default_factory=list)
    description: str | None = None


class NodeExecutionSemantics(BaseModel):
    purity: Literal["pure", "side_effecting"] = "pure"
    scheduling: Literal["sync", "async"] = "sync"
    determinism: Literal["deterministic", "provider_dependent"] = "provider_dependent"
    cacheable: bool = False
    streamable: bool = False
    retryable: bool = True
    emits_artifacts: bool = False
    requires_secrets: bool = False


class NodeDefinition(BaseModel):
    type: str
    version: int = 1
    label: str
    description: str
    category: NodeCategory
    ports: list[PortSchema] = Field(default_factory=list)
    config_schema: list[ConfigFieldSchema] = Field(default_factory=list)
    semantics: NodeExecutionSemantics = Field(default_factory=NodeExecutionSemantics)


class NodeCatalogResponse(BaseModel):
    nodes: list[NodeDefinition] = Field(default_factory=list)


class ProviderCapability(BaseModel):
    provider: str
    supports_chat: bool = True
    supports_embeddings: bool = False
    supports_structured_output: bool = False
    supports_streaming: bool = False
    supports_tool_calling: bool = False


class ProviderCatalogResponse(BaseModel):
    providers: list[ProviderCapability] = Field(default_factory=list)