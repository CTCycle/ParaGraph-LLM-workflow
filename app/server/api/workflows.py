from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from server.contracts.workflow_model import (
    CreateWorkflowRequest,
    UpdateWorkflowRequest,
    WorkflowDocument,
    WorkflowListResponse,
)
from server.contracts.workflow_templates import WorkflowTemplateListResponse
from server.services.workflow import (
    workflow_service,
    workflow_template_service,
)
from server.services.workflow.workflow import WorkflowCompilationError


router = APIRouter(prefix="/workflows", tags=["workflows"])


###############################################################################
@router.get("", response_model=WorkflowListResponse)
def list_workflows() -> WorkflowListResponse:
    return workflow_service.list_workflows()


###############################################################################
@router.post("", response_model=WorkflowDocument, status_code=status.HTTP_201_CREATED)
def create_workflow(request: CreateWorkflowRequest) -> WorkflowDocument:
    try:
        return workflow_service.create_workflow(request)
    except WorkflowCompilationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "message": str(exc),
                "diagnostics": [
                    item.model_dump(mode="json") for item in exc.diagnostics
                ],
            },
        ) from exc


###############################################################################
@router.get("/templates", response_model=WorkflowTemplateListResponse)
def list_workflow_templates() -> WorkflowTemplateListResponse:
    try:
        return workflow_template_service.list_templates()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)
        ) from exc


###############################################################################
@router.get("/{workflow_id}", response_model=WorkflowDocument)
def get_workflow(workflow_id: str) -> WorkflowDocument:
    payload = workflow_service.get_workflow(workflow_id)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow not found: {workflow_id}",
        )
    return payload


###############################################################################
@router.put("/{workflow_id}", response_model=WorkflowDocument)
def update_workflow(
    workflow_id: str, request: UpdateWorkflowRequest
) -> WorkflowDocument:
    try:
        payload = workflow_service.update_workflow(workflow_id, request)
    except WorkflowCompilationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "message": str(exc),
                "diagnostics": [
                    item.model_dump(mode="json") for item in exc.diagnostics
                ],
            },
        ) from exc
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow not found: {workflow_id}",
        )
    return payload
