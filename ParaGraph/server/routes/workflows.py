from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from ParaGraph.server.common.constants import RESOURCES_PATH
from ParaGraph.server.entities.workflowmodel import (
    CreateWorkflowRequest,
    UpdateWorkflowRequest,
    WorkflowDocument,
    WorkflowListResponse,
    WorkflowVersionListResponse,
)
from ParaGraph.server.services.workflow import workflow_service
from ParaGraph.server.services.workflow.path_picker import pick_open_file, pick_save_file


router = APIRouter(prefix="/workflows", tags=["workflows"])
WORKFLOW_JSON_DEFAULT_DIR = Path(RESOURCES_PATH) / "workflows"


class WorkflowDialogImportResponse(BaseModel):
    path: str | None = None
    json_payload: str | None = None


class WorkflowDialogExportRequest(BaseModel):
    json_payload: str = Field(min_length=2)
    suggested_filename: str = Field(default="paragraph-workflow.json", min_length=1, max_length=255)


class WorkflowDialogExportResponse(BaseModel):
    path: str | None = None


def _sanitize_filename(value: str) -> str:
    name = Path(value).name.strip() or "paragraph-workflow.json"
    if name.lower().endswith(".json"):
        return name
    return f"{name}.json"


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


@router.get("/dialog/import-json", response_model=WorkflowDialogImportResponse)
def import_workflow_json_dialog() -> WorkflowDialogImportResponse:
    try:
        selected_path = pick_open_file(
            title="Open ParaGraph workflow JSON",
            initial_directory=WORKFLOW_JSON_DEFAULT_DIR,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    if not selected_path:
        return WorkflowDialogImportResponse(path=None, json_payload=None)

    try:
        payload = Path(selected_path).read_text(encoding="utf-8")
    except OSError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unable to read workflow JSON file: {exc}",
        ) from exc

    return WorkflowDialogImportResponse(path=selected_path, json_payload=payload)


@router.post("/dialog/export-json", response_model=WorkflowDialogExportResponse)
def export_workflow_json_dialog(request: WorkflowDialogExportRequest) -> WorkflowDialogExportResponse:
    try:
        selected_path = pick_save_file(
            title="Save ParaGraph workflow JSON",
            initial_directory=WORKFLOW_JSON_DEFAULT_DIR,
            initial_file_name=_sanitize_filename(request.suggested_filename),
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    if not selected_path:
        return WorkflowDialogExportResponse(path=None)

    path = Path(selected_path)
    if path.suffix.lower() != ".json":
        path = path.with_suffix(".json")

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(request.json_payload, encoding="utf-8")
    except OSError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unable to save workflow JSON file: {exc}",
        ) from exc

    return WorkflowDialogExportResponse(path=str(path.resolve()))
