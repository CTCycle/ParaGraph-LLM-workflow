from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from server.domain.execution import CompiledExecutionPlan

###############################################################################
class WorkflowNodeInstance(BaseModel):
    node_id: str
    node_type: str
    node_version: int
    parameters: dict[str, Any] = Field(default_factory=dict)
    timeout_ms: int | None = None
    retries: int = 0
    skipped: bool = False

###############################################################################
class WorkflowConnection(BaseModel):
    from_node: str
    to_node: str
    connection_type: Literal["data", "controller"] = "data"
    from_output: str | None = None
    to_input: str | None = None
    from_controller: str | None = None
    to_controller: str | None = None

    # -------------------------------------------------------------------------
    @model_validator(mode="after")
    def validate_connection_type_contract(self) -> WorkflowConnection:
        if self.connection_type == "controller":
            if not self.from_controller or not self.to_controller:
                raise ValueError(
                    "Controller connections require from_controller and to_controller"
                )
            self.from_output = None
            self.to_input = None
            return self

        if not self.from_output or not self.to_input:
            raise ValueError("Data connections require from_output and to_input")
        self.from_controller = None
        self.to_controller = None
        return self

###############################################################################
class WorkflowDefinition(BaseModel):
    schema_version: Literal[2]
    nodes: list[WorkflowNodeInstance] = Field(default_factory=list)
    connections: list[WorkflowConnection] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

###############################################################################
class VisualNodeState(BaseModel):
    node_id: str
    x: float
    y: float
    width: float = 280.0
    height: float = 180.0
    collapsed: bool = False
    items_expanded: bool = False
    pinged: bool = False
    skipped: bool = False
    is_global: bool = False

###############################################################################
class VisualGraph(BaseModel):
    schema_version: Literal[2]
    nodes: list[VisualNodeState] = Field(default_factory=list)
    groups: list[dict[str, Any]] = Field(default_factory=list)
    comments: list[dict[str, Any]] = Field(default_factory=list)

###############################################################################
class WorkflowDocument(BaseModel):
    workflow_id: str
    name: str
    definition: WorkflowDefinition
    visual_graph: VisualGraph
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

###############################################################################
class CompilerDiagnostic(BaseModel):
    code: str
    message: str
    level: Literal["error", "warning"] = "error"
    node_id: str | None = None
    connection: WorkflowConnection | None = None

###############################################################################
class CompileWorkflowRequest(BaseModel):
    definition: WorkflowDefinition

###############################################################################
class CompileWorkflowResponse(BaseModel):
    valid: bool
    diagnostics: list[CompilerDiagnostic] = Field(default_factory=list)
    plan: CompiledExecutionPlan | None = None

###############################################################################
class CreateWorkflowRequest(BaseModel):
    name: str
    definition: WorkflowDefinition
    visual_graph: VisualGraph = Field(default_factory=VisualGraph)

###############################################################################
class UpdateWorkflowRequest(BaseModel):
    name: str | None = None
    definition: WorkflowDefinition
    visual_graph: VisualGraph

###############################################################################
class WorkflowListItem(BaseModel):
    workflow_id: str
    name: str
    updated_at: datetime

###############################################################################
class WorkflowListResponse(BaseModel):
    workflows: list[WorkflowListItem] = Field(default_factory=list)
