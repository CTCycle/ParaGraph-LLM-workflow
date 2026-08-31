from __future__ import annotations

from fastapi import APIRouter, HTTPException

from server.contracts.workflow_templates import WorkflowTemplateListResponse
from server.services.workflow import workflow_template_service


router = APIRouter(prefix="/workflow-templates", tags=["workflow-templates"])


###############################################################################
@router.get("", response_model=WorkflowTemplateListResponse)
def list_workflow_templates() -> WorkflowTemplateListResponse:
    try:
        return workflow_template_service.list_templates()
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
