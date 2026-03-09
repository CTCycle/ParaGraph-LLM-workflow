from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


NodeCategory = Literal["input", "process", "output"]
PortDirection = Literal["input", "output"]


class LegacyWorkflowPosition(BaseModel):
    x: float
    y: float


class LegacyWorkflowNode(BaseModel):
    id: str
    type: str
    position: LegacyWorkflowPosition
    params: dict[str, Any] = Field(default_factory=dict)


class LegacyWorkflowEdge(BaseModel):
    id: str
    source: str
    sourceHandle: str
    target: str
    targetHandle: str


class LegacyWorkflowGraph(BaseModel):
    nodes: list[LegacyWorkflowNode] = Field(default_factory=list)
    edges: list[LegacyWorkflowEdge] = Field(default_factory=list)


class WorkflowPortReference(BaseModel):
    node_id: str
    port: str


class WorkflowNodeSpec(BaseModel):
    node_id: str
    node_type: str
    config: dict[str, Any] = Field(default_factory=dict)


class WorkflowEdgeSpec(BaseModel):
    edge_id: str
    source: WorkflowPortReference
    target: WorkflowPortReference


class WorkflowDefinition(BaseModel):
    schema_version: int = 1
    nodes: list[WorkflowNodeSpec] = Field(default_factory=list)
    edges: list[WorkflowEdgeSpec] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class VisualNodeState(BaseModel):
    node_id: str
    x: float
    y: float
    width: float = 280.0
    height: float = 180.0
    collapsed: bool = False


class VisualGraph(BaseModel):
    schema_version: int = 1
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


class WorkflowVersionRecord(BaseModel):
    workflow_id: str
    version: int
    document: WorkflowDocument
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CompilerDiagnostic(BaseModel):
    code: str
    message: str
    level: Literal["error", "warning"] = "error"
    node_id: str | None = None
    edge_id: str | None = None


class CompileWorkflowRequest(BaseModel):
    definition: WorkflowDefinition


class CompileWorkflowResponse(BaseModel):
    valid: bool
    diagnostics: list[CompilerDiagnostic] = Field(default_factory=list)


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