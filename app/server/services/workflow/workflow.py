from __future__ import annotations

from datetime import datetime, timezone

from server.repositories.workflow import workflow_repository
from server.domain.workflow_model import (
    CompilerDiagnostic,
    CreateWorkflowRequest,
    UpdateWorkflowRequest,
    WorkflowDocument,
    WorkflowListResponse,
)
from server.services.workflow.compiler.service import compiler_service

###############################################################################
class WorkflowCompilationError(ValueError):

    # -------------------------------------------------------------------------
    def __init__(self, diagnostics: list[CompilerDiagnostic]) -> None:
        self.diagnostics = diagnostics
        message = "; ".join(item.message for item in diagnostics)
        super().__init__(message or "Workflow definition failed compilation")

###############################################################################
class WorkflowService:

    # -------------------------------------------------------------------------
    @staticmethod
    def _validate_definition(request_definition) -> None:
        compiled = compiler_service.compile(request_definition)
        if not compiled.valid:
            raise WorkflowCompilationError(compiled.diagnostics)

    # -------------------------------------------------------------------------
    def list_workflows(self) -> WorkflowListResponse:
        return WorkflowListResponse(workflows=workflow_repository.list_workflows())

    # -------------------------------------------------------------------------
    def create_workflow(self, request: CreateWorkflowRequest) -> WorkflowDocument:
        self._validate_definition(request.definition)
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

    # -------------------------------------------------------------------------
    def get_workflow(self, workflow_id: str) -> WorkflowDocument | None:
        return workflow_repository.get_workflow(workflow_id)

    # -------------------------------------------------------------------------
    def update_workflow(
        self, workflow_id: str, request: UpdateWorkflowRequest
    ) -> WorkflowDocument | None:
        current = workflow_repository.get_workflow(workflow_id)
        if current is None:
            return None

        self._validate_definition(request.definition)

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
