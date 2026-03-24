from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from ParaGraph.server.domain.execution import CompiledExecutionPlan


LEGACY_NODE_TYPE_MAP = {
    "Prompt": "PROMPT",
    "PROMPT": "PROMPT",
    "USER_PROMPT": "PROMPT",
    "SYSTEM_PROMPT": "PROMPT",
    "Output": "TEXT_OUTPUT",
    "Retrieval": "TEXT_SPLIT",
    "VectorDB": "LOAD_TEXT",
}
LEGACY_LLM_NODE_TYPE_MAP: dict[str, tuple[str, str]] = {
    "OLLAMA_LLM_CHAT": ("LLM_CHAT", "ollama"),
    "CLOUD_LLM_CHAT": ("LLM_CHAT", "openai"),
    "HUGGINGFACE_LLM_CHAT": ("LLM_CHAT", "huggingface"),
    "OLLAMA_STRUCTURED_RESPONSE": ("LLM_STRUCTURED", "ollama"),
    "CLOUD_STRUCTURED_RESPONSE": ("LLM_STRUCTURED", "openai"),
    "HUGGINGFACE_STRUCTURED_RESPONSE": ("LLM_STRUCTURED", "huggingface"),
}
MODEL_NODE_TYPES = {"LLM_CHAT", "LLM_STRUCTURED"}


def _normalize_provider_name(provider: Any) -> str:
    normalized = str(provider or "ollama").strip().lower()
    if normalized == "anthropic":
        return "claude"
    return normalized


def _normalize_legacy_model_node(node_type: str, parameters: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    next_parameters = dict(parameters)
    if "provider" in next_parameters:
        next_parameters["provider"] = _normalize_provider_name(next_parameters.get("provider"))

    if node_type in LEGACY_LLM_NODE_TYPE_MAP:
        mapped_type, default_provider = LEGACY_LLM_NODE_TYPE_MAP[node_type]
        next_parameters.setdefault("provider", default_provider)
        return mapped_type, next_parameters

    if node_type != "LLM_GENERATE":
        mapped = LEGACY_NODE_TYPE_MAP.get(node_type, node_type)
        return mapped, next_parameters

    provider = _normalize_provider_name(next_parameters.get("provider", "ollama"))
    next_parameters["provider"] = provider
    return "LLM_CHAT", next_parameters


class WorkflowNodeInstance(BaseModel):
    node_id: str
    node_type: str
    node_version: int = 1
    parameters: dict[str, Any] = Field(default_factory=dict)
    skipped: bool = False

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
            "skipped": bool(value.get("skipped", value.get("disabled", False))),
        }


class WorkflowConnection(BaseModel):
    from_node: str
    to_node: str
    connection_type: Literal["data", "controller"] = "data"
    from_output: str | None = None
    to_input: str | None = None
    from_controller: str | None = None
    to_controller: str | None = None

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_connection(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        if "from_node" in value:
            migrated = dict(value)
            if "connection_type" not in migrated:
                if migrated.get("from_controller") or migrated.get("to_controller"):
                    migrated["connection_type"] = "controller"
                else:
                    migrated["connection_type"] = "data"
            return migrated
        return {
            "from_node": value.get("source", {}).get("node_id"),
            "from_output": value.get("source", {}).get("port"),
            "to_node": value.get("target", {}).get("node_id"),
            "to_input": value.get("target", {}).get("port"),
            "connection_type": "data",
        }

    @model_validator(mode="after")
    def validate_connection_type_contract(self) -> WorkflowConnection:
        if self.connection_type == "controller":
            if not self.from_controller or not self.to_controller:
                raise ValueError("Controller connections require from_controller and to_controller")
            self.from_output = None
            self.to_input = None
            return self

        if not self.from_output or not self.to_input:
            raise ValueError("Data connections require from_output and to_input")
        self.from_controller = None
        self.to_controller = None
        return self


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
            if connection.connection_type == "controller":
                normalized_connections.append(connection)
                continue

            to_input = connection.to_input or ""
            target_type = node_types.get(connection.to_node, "")
            if target_type in MODEL_NODE_TYPES and to_input == "prompt":
                to_input = "user_prompt"
            if target_type in MODEL_NODE_TYPES and to_input == "model":
                normalized_connections.append(
                    WorkflowConnection(
                        from_node=connection.from_node,
                        to_node=connection.to_node,
                        connection_type="controller",
                        from_controller=connection.from_output or "model",
                        to_controller="model",
                    )
                )
                continue
            normalized_connections.append(
                WorkflowConnection(
                    from_node=connection.from_node,
                    to_node=connection.to_node,
                    connection_type="data",
                    from_output=connection.from_output,
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
    pinged: bool = False
    skipped: bool = False


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

