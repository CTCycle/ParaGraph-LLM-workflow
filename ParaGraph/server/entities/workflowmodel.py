from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field, model_validator

from ParaGraph.server.entities.execution import CompiledExecutionPlan


LEGACY_NODE_TYPE_MAP = {
    "Prompt": "PROMPT",
    "LLM": "LLM_GENERATE",
    "Output": "TEXT_OUTPUT",
    "Retrieval": "TEXT_SPLIT",
    "VectorDB": "LOAD_TEXT",
}


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
        if "parameters" in value:
            return value
        return {
            "node_id": value.get("node_id"),
            "node_type": LEGACY_NODE_TYPE_MAP.get(str(value.get("node_type")), str(value.get("node_type"))),
            "node_version": value.get("node_version", 1),
            "parameters": value.get("config", {}),
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
