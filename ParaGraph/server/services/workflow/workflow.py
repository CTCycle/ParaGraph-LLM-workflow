from __future__ import annotations

from ParaGraph.server.repositories.workflow import workflow_repository
from ParaGraph.server.domain.workflow_model import (
    CreateWorkflowRequest,
    UpdateWorkflowRequest,
    WorkflowDocument,
    WorkflowListResponse,
)


class WorkflowService:
    def list_workflows(self) -> WorkflowListResponse:
        return WorkflowListResponse(workflows=workflow_repository.list_workflows())

    def create_workflow(self, request: CreateWorkflowRequest) -> WorkflowDocument:
        return workflow_repository.create_workflow(
            name=request.name,
            definition=request.definition,
            visual_graph=request.visual_graph,
        )

    def get_workflow(self, workflow_id: str) -> WorkflowDocument | None:
        return workflow_repository.get_workflow(workflow_id)

    def update_workflow(
        self, workflow_id: str, request: UpdateWorkflowRequest
    ) -> WorkflowDocument | None:
        return workflow_repository.update_workflow(
            workflow_id=workflow_id,
            name=request.name,
            definition=request.definition,
            visual_graph=request.visual_graph,
        )

workflow_service = WorkflowService()
