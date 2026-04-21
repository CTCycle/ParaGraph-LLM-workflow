from __future__ import annotations

from datetime import datetime, timezone

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
        now = datetime.now(timezone.utc)
        document = WorkflowDocument(
            workflow_id=workflow_repository.new_workflow_id(),
            name=request.name,
            definition=request.definition,
            visual_graph=request.visual_graph,
            created_at=now,
            updated_at=now,
        )
        workflow_repository.save_workflow(document)
        return document

    def get_workflow(self, workflow_id: str) -> WorkflowDocument | None:
        return workflow_repository.get_workflow(workflow_id)

    def update_workflow(
        self, workflow_id: str, request: UpdateWorkflowRequest
    ) -> WorkflowDocument | None:
        current = workflow_repository.get_workflow(workflow_id)
        if current is None:
            return None

        updated_document = WorkflowDocument(
            workflow_id=workflow_id,
            name=request.name or current.name,
            definition=request.definition,
            visual_graph=request.visual_graph,
            created_at=current.created_at,
            updated_at=datetime.now(timezone.utc),
        )
        workflow_repository.save_workflow(updated_document)
        return updated_document

workflow_service = WorkflowService()
