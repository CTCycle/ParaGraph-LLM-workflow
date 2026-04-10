from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from ParaGraph.server.domain.node_catalog import NodeManifest
from ParaGraph.server.domain.workflow_model import VisualGraph, WorkflowDefinition


class WorkflowTemplateManifest(BaseModel):
    id: str
    name: str
    description: str
    tags: list[str] = Field(default_factory=list)
    definition: WorkflowDefinition
    visual_graph: VisualGraph = Field(default_factory=VisualGraph)
    required_nodes: list[NodeManifest] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorkflowTemplateListResponse(BaseModel):
    templates: list[WorkflowTemplateManifest] = Field(default_factory=list)
