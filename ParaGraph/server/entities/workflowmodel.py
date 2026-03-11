from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field, model_validator

from ParaGraph.server.entities.execution import CompiledExecutionPlan


LEGACY_NODE_TYPE_MAP = {
    "Prompt": "USER_PROMPT",
    "PROMPT": "USER_PROMPT",
    "Output": "TEXT_OUTPUT",
    "Retrieval": "TEXT_SPLIT",
    "VectorDB": "LOAD_TEXT",
}

MODEL_NODE_TYPES = {
    "OLLAMA_LLM_CHAT",
    "CLOUD_LLM_CHAT",
    "HUGGINGFACE_LLM_CHAT",
    "OLLAMA_STRUCTURED_RESPONSE",
    "CLOUD_STRUCTURED_RESPONSE",
    "HUGGINGFACE_STRUCTURED_RESPONSE",
}


def _normalize_provider_name(provider: Any) -> str:
    normalized = str(provider or "ollama").strip().lower()
    if normalized == "anthropic":
        return "claude"
    return normalized


def _normalize_legacy_model_node(node_type: str, parameters: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    next_parameters = dict(parameters)
    if "provider" in next_parameters:
        next_parameters["provider"] = _normalize_provider_name(next_parameters.get("provider"))

    if node_type != "LLM_GENERATE":
        mapped = LEGACY_NODE_TYPE_MAP.get(node_type, node_type)
        return mapped, next_parameters

    provider = _normalize_provider_name(next_parameters.get("provider", "ollama"))
    if provider == "huggingface":
        return "HUGGINGFACE_LLM_CHAT", next_parameters
    if provider in {"openai", "gemini", "claude"}:
        return "CLOUD_LLM_CHAT", next_parameters
    next_parameters["provider"] = "ollama"
    return "OLLAMA_LLM_CHAT", next_parameters


class WorkflowNodeInstance(BaseModel):
    node_id: str
    node_type: str
    node_version: int = 1
    parameters: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_node(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value

        parameters = value.get("parameters")
        if parameters is None:
            parameters = value.get("config", {})
        if not isinstance(parameters, dict):
            parameters = {}

        node_type, normalized_parameters = _normalize_legacy_model_node(str(value.get("node_type")), parameters)
        return {
            "node_id": value.get("node_id"),
            "node_type": node_type,
            "node_version": value.get("node_version", 1),
            "parameters": normalized_parameters,
        }


class WorkflowConnection(BaseModel):
    from_node: str
    from_output: str
    to_node: str
    to_input: str

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_connection(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        if "from_node" in value:
            return value
        return {
            "from_node": value.get("source", {}).get("node_id"),
            "from_output": value.get("source", {}).get("port"),
            "to_node": value.get("target", {}).get("node_id"),
            "to_input": value.get("target", {}).get("port"),
        }


class WorkflowDefinition(BaseModel):
    schema_version: int = 2
    nodes: list[WorkflowNodeInstance] = Field(default_factory=list)
    connections: list[WorkflowConnection] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_definition(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        if "connections" in value:
            return value
        edges = value.get("edges", [])
        return {
            "schema_version": 2,
            "nodes": value.get("nodes", []),
            "connections": [
                {
                    "from_node": edge.get("source", {}).get("node_id"),
                    "from_output": edge.get("source", {}).get("port"),
                    "to_node": edge.get("target", {}).get("node_id"),
                    "to_input": edge.get("target", {}).get("port"),
                }
                for edge in edges
            ],
            "metadata": value.get("metadata", {}),
        }

    @model_validator(mode="after")
    def normalize_legacy_contracts(self) -> WorkflowDefinition:
        node_types = {node.node_id: node.node_type for node in self.nodes}
        for node in self.nodes:
            node.node_type, node.parameters = _normalize_legacy_model_node(node.node_type, node.parameters)
            node_types[node.node_id] = node.node_type

        normalized_connections: list[WorkflowConnection] = []
        for connection in self.connections:
            to_input = connection.to_input
            target_type = node_types.get(connection.to_node, "")
            if target_type in MODEL_NODE_TYPES and to_input == "prompt":
                to_input = "user_prompt"
            normalized_connections.append(
                WorkflowConnection(
                    from_node=connection.from_node,
                    from_output=connection.from_output,
                    to_node=connection.to_node,
                    to_input=to_input,
                )
            )
        self.connections = normalized_connections
        return self


class VisualNodeState(BaseModel):
    node_id: str
    x: float
    y: float
    width: float = 280.0
    height: float = 180.0
    collapsed: bool = False


class VisualGraph(BaseModel):
    schema_version: int = 2
    nodes: list[VisualNodeState] = Field(default_factory=list)
    groups: list[dict[str, Any]] = Field(default_factory=list)
    comments: list[dict[str, Any]] = Field(default_factory=list)


class WorkflowDocument(BaseModel):
    workflow_id: str
    name: str
    latest_version: int
    definition: WorkflowDefinition
    visual_graph: VisualGraph
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CompilerDiagnostic(BaseModel):
    code: str
    message: str
    level: str = "error"
    node_id: str | None = None
    connection: WorkflowConnection | None = None


class CompileWorkflowRequest(BaseModel):
    definition: WorkflowDefinition


class CompileWorkflowResponse(BaseModel):
    valid: bool
    diagnostics: list[CompilerDiagnostic] = Field(default_factory=list)
    plan: CompiledExecutionPlan | None = None


class CreateWorkflowRequest(BaseModel):
    name: str
    definition: WorkflowDefinition
    visual_graph: VisualGraph = Field(default_factory=VisualGraph)


class UpdateWorkflowRequest(BaseModel):
    name: str | None = None
    definition: WorkflowDefinition
    visual_graph: VisualGraph


class WorkflowListItem(BaseModel):
    workflow_id: str
    name: str
    latest_version: int
    updated_at: datetime


class WorkflowListResponse(BaseModel):
    workflows: list[WorkflowListItem] = Field(default_factory=list)


class WorkflowVersionListResponse(BaseModel):
    workflow_id: str
    versions: list[int] = Field(default_factory=list)
