from __future__ import annotations

import time

from fastapi import APIRouter, HTTPException, status

from APP.server.entities.jobs import JobCancelResponse, JobStartResponse, JobStatusResponse
from APP.server.entities.validation import (
    CheckpointEvaluationReportResponse,
    StartCheckpointEvaluationRequest,
    StartValidationRequest,
    ValidationReportResponse,
)
from APP.server.services.jobs import job_manager


# -----------------------------------------------------------------------------
def run_validation_job(configuration: dict[str, object], job_id: str) -> dict[str, object]:
    _ = configuration
    for progress in (30, 70, 100):
        if job_manager.should_stop(job_id):
            return {}
        time.sleep(0.05)
        job_manager.update_progress(job_id, float(progress))
    return {"metrics": {"accuracy": 0.9, "loss": 0.1}}


###############################################################################
class ValidationEndpoint:
    JOB_TYPE = "validation"

    def __init__(self, router: APIRouter) -> None:
        self.router = router
        self.dataset_reports: dict[str, dict[str, object]] = {}
        self.checkpoint_reports: dict[str, dict[str, object]] = {}

    # -------------------------------------------------------------------------
    def run_validation(self, request: StartValidationRequest) -> JobStartResponse:
        job_id = job_manager.start_job(
            job_type=self.JOB_TYPE,
            runner=run_validation_job,
            kwargs={"configuration": request.model_dump()},
        )
        self.dataset_reports[request.dataset_name] = {"accuracy": 0.9, "loss": 0.1}
        return JobStartResponse(job_id=job_id, job_type=self.JOB_TYPE, status="running", message="Validation job started")

    # -------------------------------------------------------------------------
    def run_checkpoint_evaluation(self, request: StartCheckpointEvaluationRequest) -> JobStartResponse:
        job_id = job_manager.start_job(
            job_type=self.JOB_TYPE,
            runner=run_validation_job,
            kwargs={"configuration": request.model_dump()},
        )
        self.checkpoint_reports[request.checkpoint] = {"accuracy": 0.92, "loss": 0.08}
        return JobStartResponse(job_id=job_id, job_type=self.JOB_TYPE, status="running", message="Checkpoint evaluation started")

    # -------------------------------------------------------------------------
    def get_checkpoint_report(self, checkpoint: str) -> CheckpointEvaluationReportResponse:
        payload = self.checkpoint_reports.get(checkpoint)
        if payload is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Checkpoint report not found")
        return CheckpointEvaluationReportResponse(checkpoint=checkpoint, metrics=payload)

    # -------------------------------------------------------------------------
    def get_dataset_report(self, dataset_name: str) -> ValidationReportResponse:
        payload = self.dataset_reports.get(dataset_name)
        if payload is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Validation report not found")
        return ValidationReportResponse(dataset_name=dataset_name, metrics=payload)

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
        self.router.add_api_route("/run", self.run_validation, methods=["POST"], response_model=JobStartResponse, status_code=status.HTTP_202_ACCEPTED)
        self.router.add_api_route("/checkpoint", self.run_checkpoint_evaluation, methods=["POST"], response_model=JobStartResponse, status_code=status.HTTP_202_ACCEPTED)
        self.router.add_api_route("/checkpoint/reports/{checkpoint}", self.get_checkpoint_report, methods=["GET"], response_model=CheckpointEvaluationReportResponse)
        self.router.add_api_route("/reports/{dataset_name}", self.get_dataset_report, methods=["GET"], response_model=ValidationReportResponse)
        self.router.add_api_route("/jobs/{job_id}", self.get_job_status, methods=["GET"], response_model=JobStatusResponse)
        self.router.add_api_route("/jobs/{job_id}", self.cancel_job, methods=["DELETE"], response_model=JobCancelResponse)


router = APIRouter(prefix="/validation", tags=["validation"])
endpoint = ValidationEndpoint(router)
endpoint.add_routes()
