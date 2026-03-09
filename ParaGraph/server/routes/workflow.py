from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from ParaGraph.server.configurations.server import server_settings
from ParaGraph.server.entities.jobs import JobCancelResponse, JobStatusResponse
from ParaGraph.server.entities.workflow import (
    CatalogResponse,
    ExecuteWorkflowResponse,
    ValidateWorkflowResponse,
    WorkflowGraph,
)
from ParaGraph.server.services.jobs import job_manager
from ParaGraph.server.services.workflow.executor import (
    execute_workflow_graph,
    get_catalog_response,
    validate_workflow_graph,
)


###############################################################################
class WorkflowEndpoint:
    JOB_TYPE = "workflow"

    def __init__(self, router: APIRouter) -> None:
        self.router = router

    # -------------------------------------------------------------------------
    def get_catalog(self) -> CatalogResponse:
        return get_catalog_response()

    # -------------------------------------------------------------------------
    def validate_workflow(self, graph: WorkflowGraph) -> ValidateWorkflowResponse:
        return validate_workflow_graph(graph)

    # -------------------------------------------------------------------------
    def execute_workflow(self, graph: WorkflowGraph) -> ExecuteWorkflowResponse:
        validation = validate_workflow_graph(graph)
        if not validation.valid:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=validation.errors)

        output_node_ids = [node.id for node in graph.nodes if node.type == "Output"]
        job_id = job_manager.start_job(
            job_type=self.JOB_TYPE,
            runner=execute_workflow_graph,
            kwargs={"graph": graph},
        )

        return ExecuteWorkflowResponse(
            job_id=job_id,
            job_type=self.JOB_TYPE,
            status="running",
            message="Workflow execution started",
            poll_interval=server_settings.jobs.polling_interval,
            output_node_ids=output_node_ids,
        )

    # -------------------------------------------------------------------------
    def get_job_status(self, job_id: str) -> JobStatusResponse:
        payload = job_manager.get_job_status(job_id)
        if payload is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Job not found: {job_id}")
        return JobStatusResponse(**payload)

    # -------------------------------------------------------------------------
    def cancel_job(self, job_id: str) -> JobCancelResponse:
        success = job_manager.cancel_job(job_id)
        return JobCancelResponse(
            job_id=job_id,
            success=success,
            message="Cancellation requested" if success else "Job cannot be cancelled",
        )

    # -------------------------------------------------------------------------
    def add_routes(self) -> None:
        self.router.add_api_route(
            "/catalog",
            self.get_catalog,
            methods=["GET"],
            response_model=CatalogResponse,
        )
        self.router.add_api_route(
            "/validate",
            self.validate_workflow,
            methods=["POST"],
            response_model=ValidateWorkflowResponse,
        )
        self.router.add_api_route(
            "/execute",
            self.execute_workflow,
            methods=["POST"],
            response_model=ExecuteWorkflowResponse,
            status_code=status.HTTP_202_ACCEPTED,
        )
        self.router.add_api_route(
            "/jobs/{job_id}",
            self.get_job_status,
            methods=["GET"],
            response_model=JobStatusResponse,
        )
        self.router.add_api_route(
            "/jobs/{job_id}",
            self.cancel_job,
            methods=["DELETE"],
            response_model=JobCancelResponse,
        )


router = APIRouter(prefix="/workflow", tags=["workflow"])
endpoint = WorkflowEndpoint(router)
endpoint.add_routes()
