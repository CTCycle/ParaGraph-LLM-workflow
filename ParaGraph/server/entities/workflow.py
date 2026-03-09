from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from ParaGraph.server.entities.jobs import JobStartResponse


NodeCategory = Literal["input", "process", "output"]
PortDirection = Literal["input", "output"]


###############################################################################
class NodePort(BaseModel):
    handle: str
    label: str
    direction: PortDirection
    data_type: str


###############################################################################
class NodeParameterSchema(BaseModel):
    key: str
    label: str
    field_type: str
    required: bool = False
    default: Any | None = None
    options: list[str] = Field(default_factory=list)
    description: str | None = None


###############################################################################
class WorkflowNodeDefinition(BaseModel):
    type: str
    label: str
    description: str
    category: NodeCategory
    ports: list[NodePort] = Field(default_factory=list)
    parameters: list[NodeParameterSchema] = Field(default_factory=list)


###############################################################################
class WorkflowPosition(BaseModel):
    x: float
    y: float


###############################################################################
class WorkflowNode(BaseModel):
    id: str
    type: str
    position: WorkflowPosition
    params: dict[str, Any] = Field(default_factory=dict)


###############################################################################
class WorkflowEdge(BaseModel):
    id: str
    source: str
    sourceHandle: str
    target: str
    targetHandle: str


###############################################################################
class WorkflowGraph(BaseModel):
    nodes: list[WorkflowNode] = Field(default_factory=list)
    edges: list[WorkflowEdge] = Field(default_factory=list)


###############################################################################
class CatalogResponse(BaseModel):
    nodes: list[WorkflowNodeDefinition]


###############################################################################
class ValidateWorkflowResponse(BaseModel):
    valid: bool
    errors: list[str] = Field(default_factory=list)


###############################################################################
class ExecuteWorkflowResponse(JobStartResponse):
    output_node_ids: list[str] = Field(default_factory=list)
