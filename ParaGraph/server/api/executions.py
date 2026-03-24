from __future__ import annotations

from fastapi import APIRouter, HTTPException, Path, status

from ParaGraph.server.configurations.server import server_settings
from ParaGraph.server.domain.execution import EventHistoryResponse, ExecutionRunState, StartExecutionRequest, StartExecutionResponse
from ParaGraph.server.domain.workflowmodel import CompileWorkflowRequest, CompileWorkflowResponse
from ParaGraph.server.services.runtime.events import execution_event_service
from ParaGraph.server.services.workflow import compiler_service, execution_service


router = APIRouter(prefix="/executions", tags=["executions"])
RUN_ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$"


@router.post("/compile", response_model=CompileWorkflowResponse)
def compile_workflow(request: CompileWorkflowRequest) -> CompileWorkflowResponse:
    return compiler_service.compile(request.definition)


@router.post("", response_model=StartExecutionResponse, status_code=status.HTTP_202_ACCEPTED)
def start_execution(request: StartExecutionRequest) -> StartExecutionResponse:
    run_id = execution_service.start_execution(request.plan, workflow_id=request.workflow_id)
    return StartExecutionResponse(run_id=run_id, status="running", poll_interval=server_settings.jobs.polling_interval)


@router.get("/{run_id}", response_model=ExecutionRunState)
def get_execution(run_id: str = Path(..., min_length=1, max_length=128, pattern=RUN_ID_PATTERN)) -> ExecutionRunState:
    run = execution_service.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Run not found: {run_id}")
    return run


@router.get("/{run_id}/events", response_model=EventHistoryResponse)
def get_execution_events(run_id: str = Path(..., min_length=1, max_length=128, pattern=RUN_ID_PATTERN)) -> EventHistoryResponse:
    return execution_event_service.get_history(run_id)
