from __future__ import annotations

import time

from fastapi import APIRouter, HTTPException, status

from APP.server.entities.inference import InferenceResultResponse, StartInferenceRequest
from APP.server.entities.jobs import JobCancelResponse, JobStartResponse, JobStatusResponse
from APP.server.entities.training import CheckpointInfo, CheckpointsResponse
from APP.server.repositories.serialization.model import ModelSerializer
from APP.server.services.jobs import job_manager


# -----------------------------------------------------------------------------
def run_inference_job(configuration: dict[str, object], job_id: str) -> dict[str, object]:
    _ = configuration
    for progress in (25, 60, 100):
        if job_manager.should_stop(job_id):
            return {}
        time.sleep(0.05)
        job_manager.update_progress(job_id, float(progress))
    return {
        "reports": [{"input_name": "sample_asset.png", "output_text": "Template output text"}],
        "count": 1,
    }


###############################################################################
class InferenceEndpoint:
    JOB_TYPE = "inference"

    def __init__(self, router: APIRouter) -> None:
        self.router = router

    # -------------------------------------------------------------------------
    def get_checkpoints(self) -> CheckpointsResponse:
        names = ModelSerializer().scan_checkpoints_folder()
        return CheckpointsResponse(
            checkpoints=[CheckpointInfo(name=name, epochs=0, loss=0.0, val_loss=0.0) for name in names]
        )

    # -------------------------------------------------------------------------
    def generate(self, request: StartInferenceRequest) -> JobStartResponse:
        if job_manager.is_job_running(self.JOB_TYPE):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Inference already in progress")
        job_id = job_manager.start_job(
            job_type=self.JOB_TYPE,
            runner=run_inference_job,
            kwargs={"configuration": request.model_dump()},
        )
        return JobStartResponse(
            job_id=job_id,
            job_type=self.JOB_TYPE,
            status="running",
            message="Inference job started",
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
    def result_schema(self) -> InferenceResultResponse:
        return InferenceResultResponse(reports=[], count=0)

    # -------------------------------------------------------------------------
    def add_routes(self) -> None:
        self.router.add_api_route("/checkpoints", self.get_checkpoints, methods=["GET"], response_model=CheckpointsResponse)
        self.router.add_api_route("/generate", self.generate, methods=["POST"], response_model=JobStartResponse, status_code=status.HTTP_202_ACCEPTED)
        self.router.add_api_route("/jobs/{job_id}", self.get_job_status, methods=["GET"], response_model=JobStatusResponse)
        self.router.add_api_route("/jobs/{job_id}", self.cancel_job, methods=["DELETE"], response_model=JobCancelResponse)


router = APIRouter(prefix="/inference", tags=["inference"])
endpoint = InferenceEndpoint(router)
endpoint.add_routes()
