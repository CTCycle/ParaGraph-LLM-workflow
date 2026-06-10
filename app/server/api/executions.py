from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Request, status

from server.domain.execution import (
    EventHistoryResponse,
    ExecutionRunState,
    RUN_ID_PATTERN,
    StartExecutionRequest,
    StartExecutionResponse,
)
from server.domain.workflow_model import (
    CompileWorkflowRequest,
    CompileWorkflowResponse,
)
from server.services.runtime.events import execution_event_service
from server.services.workflow import compiler_service, execution_service


router = APIRouter(prefix="/executions", tags=["executions"])
logger = logging.getLogger(__name__)
RunIdPath = Annotated[str, Path(min_length=1, max_length=128, pattern=RUN_ID_PATTERN)]

###############################################################################
@router.post("/compile", response_model=CompileWorkflowResponse)
def compile_workflow(request: CompileWorkflowRequest) -> CompileWorkflowResponse:
    return compiler_service.compile(request.definition)

###############################################################################
@router.post(
    "",
    response_model=StartExecutionResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def start_execution(
    payload: StartExecutionRequest, request: Request
) -> StartExecutionResponse:
    request_id = getattr(request.state, "request_id", None)
    logger.info(
        "Starting execution request_id=%s workflow_id=%s session_id=%s plan_id=%s",
        request_id,
        payload.workflow_id,
        payload.execution_session_id,
        payload.plan.plan_id,
    )
    return execution_service.start_execution_response(
        payload.plan,
        workflow_id=payload.workflow_id,
        execution_session_id=payload.execution_session_id,
        request_id=request_id,
    )

###############################################################################
@router.get("/{run_id}", response_model=ExecutionRunState)
def get_execution(run_id: RunIdPath) -> ExecutionRunState:
    run = execution_service.get_run(run_id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Run not found: {run_id}"
        )
    return run

###############################################################################
@router.get("/{run_id}/events", response_model=EventHistoryResponse)
def get_execution_events(run_id: RunIdPath) -> EventHistoryResponse:
    return execution_event_service.get_history(run_id)
