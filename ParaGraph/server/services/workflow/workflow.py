from __future__ import annotations

from ParaGraph.server.repositories.workflow import workflow_repository
from ParaGraph.server.domain.workflow_model import (
    CreateWorkflowRequest,
    UpdateWorkflowRequest,
    WorkflowDocument,
    WorkflowListResponse,
    WorkflowVersionListResponse,
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

    def get_workflow(
        self, workflow_id: str, version: int | None = None
    ) -> WorkflowDocument | None:
        if version is None:
            return workflow_repository.get_latest_workflow(workflow_id)
        return workflow_repository.get_workflow_version(workflow_id, version)

    def update_workflow(
        self, workflow_id: str, request: UpdateWorkflowRequest
    ) -> WorkflowDocument | None:
        return workflow_repository.update_workflow(
            workflow_id=workflow_id,
            name=request.name,
            definition=request.definition,
            visual_graph=request.visual_graph,
        )

    def list_versions(self, workflow_id: str) -> WorkflowVersionListResponse | None:
        latest = workflow_repository.get_latest_workflow(workflow_id)
        if latest is None:
            return None

        versions = workflow_repository.list_versions(workflow_id)
        return WorkflowVersionListResponse(workflow_id=workflow_id, versions=versions)


workflow_service = WorkflowService()
