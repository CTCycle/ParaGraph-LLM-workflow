from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from ParaGraph.server.entities.workflowmodel import (
    CreateWorkflowRequest,
    UpdateWorkflowRequest,
    WorkflowDocument,
    WorkflowListResponse,
    WorkflowVersionListResponse,
)
from ParaGraph.server.services.workflow import workflow_service


router = APIRouter(prefix="/workflows", tags=["workflows"])


@router.get("", response_model=WorkflowListResponse)
def list_workflows() -> WorkflowListResponse:
    return workflow_service.list_workflows()


@router.post("", response_model=WorkflowDocument, status_code=status.HTTP_201_CREATED)
def create_workflow(request: CreateWorkflowRequest) -> WorkflowDocument:
    return workflow_service.create_workflow(request)


@router.get("/{workflow_id}", response_model=WorkflowDocument)
def get_workflow(workflow_id: str, version: int | None = None) -> WorkflowDocument:
    payload = workflow_service.get_workflow(workflow_id, version=version)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Workflow not found: {workflow_id}")
    return payload


@router.put("/{workflow_id}", response_model=WorkflowDocument)
def update_workflow(workflow_id: str, request: UpdateWorkflowRequest) -> WorkflowDocument:
    payload = workflow_service.update_workflow(workflow_id, request)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Workflow not found: {workflow_id}")
    return payload


@router.get("/{workflow_id}/versions", response_model=WorkflowVersionListResponse)
def list_workflow_versions(workflow_id: str) -> WorkflowVersionListResponse:
    return workflow_service.list_versions(workflow_id)