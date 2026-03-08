from __future__ import annotations

import os
import time
from typing import Any

from fastapi import APIRouter, HTTPException, status

from APP.server.common.constants import CHECKPOINT_PATH
from APP.server.configurations.server import server_settings
from APP.server.entities.jobs import JobCancelResponse, JobStartResponse, JobStatusResponse
from APP.server.entities.training import (
    CheckpointInfo,
    CheckpointMetadataResponse,
    CheckpointsResponse,
    DeleteResponse,
    ResumeTrainingRequest,
    StartTrainingRequest,
    TrainingStatusResponse,
)
from APP.server.repositories.serialization.model import ModelSerializer
from APP.server.services.jobs import job_manager


###############################################################################
class TrainingState:
    def __init__(self) -> None:
        self.state = self.build_state(is_training=False, total_epochs=0)
        self.current_job_id: str | None = None

    # -------------------------------------------------------------------------
    def build_state(self, is_training: bool, total_epochs: int) -> dict[str, Any]:
        return {
            "is_training": is_training,
            "current_epoch": 0,
            "total_epochs": total_epochs,
            "loss": 0.0,
            "val_loss": 0.0,
            "accuracy": 0.0,
            "val_accuracy": 0.0,
            "progress_percent": 0,
            "elapsed_seconds": 0,
        }

    # -------------------------------------------------------------------------
    def reset_for_new_session(self, total_epochs: int, job_id: str) -> None:
        self.state = self.build_state(is_training=True, total_epochs=total_epochs)
        self.current_job_id = job_id

    # -------------------------------------------------------------------------
    def finish_session(self) -> None:
        self.state["is_training"] = False
        self.current_job_id = None


training_state = TrainingState()


# -----------------------------------------------------------------------------
def run_training_job(configuration: dict[str, Any], job_id: str) -> dict[str, Any]:
    epochs = int(configuration.get("epochs", 10))
    start = time.monotonic()
    for epoch in range(1, epochs + 1):
        if job_manager.should_stop(job_id):
            return {}
        time.sleep(0.05)
        progress = (epoch / epochs) * 100
        training_state.state.update(
            {
                "current_epoch": epoch,
                "total_epochs": epochs,
                "loss": max(0.01, 1.0 / epoch),
                "val_loss": max(0.02, 1.2 / epoch),
                "accuracy": min(0.99, epoch / epochs),
                "val_accuracy": min(0.95, epoch / epochs),
                "progress_percent": int(progress),
                "elapsed_seconds": int(time.monotonic() - start),
            }
        )
        job_manager.update_progress(job_id, progress)
        job_manager.update_result(job_id, dict(training_state.state))
    training_state.finish_session()
    return dict(training_state.state)


###############################################################################
class TrainingEndpoint:
    JOB_TYPE = "training"

    def __init__(self, router: APIRouter) -> None:
        self.router = router

    # -------------------------------------------------------------------------
    def get_checkpoints(self) -> CheckpointsResponse:
        serializer = ModelSerializer()
        checkpoints = [CheckpointInfo(name=name, epochs=0, loss=0.0, val_loss=0.0) for name in serializer.scan_checkpoints_folder()]
        return CheckpointsResponse(checkpoints=checkpoints)

    # -------------------------------------------------------------------------
    def get_checkpoint_metadata(self, checkpoint: str) -> CheckpointMetadataResponse:
        checkpoint_path = os.path.join(CHECKPOINT_PATH, checkpoint)
        if not os.path.isdir(checkpoint_path):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Checkpoint not found: {checkpoint}")
        configuration, metadata, session = ModelSerializer().load_training_configuration(checkpoint_path)
        return CheckpointMetadataResponse(
            checkpoint=checkpoint,
            configuration=configuration,
            metadata=metadata,
            session=session,
        )

    # -------------------------------------------------------------------------
    def delete_checkpoint(self, checkpoint: str) -> DeleteResponse:
        checkpoint_path = os.path.join(CHECKPOINT_PATH, checkpoint)
        if not os.path.isdir(checkpoint_path):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Checkpoint not found: {checkpoint}")
        return DeleteResponse(success=True, message=f"Deletion placeholder for checkpoint {checkpoint}")

    # -------------------------------------------------------------------------
    def get_training_status(self) -> TrainingStatusResponse:
        return TrainingStatusResponse(
            job_id=training_state.current_job_id,
            is_training=training_state.state["is_training"],
            current_epoch=training_state.state["current_epoch"],
            total_epochs=training_state.state["total_epochs"],
            loss=training_state.state["loss"],
            val_loss=training_state.state["val_loss"],
            accuracy=training_state.state["accuracy"],
            val_accuracy=training_state.state["val_accuracy"],
            progress_percent=training_state.state["progress_percent"],
            elapsed_seconds=training_state.state["elapsed_seconds"],
            poll_interval=server_settings.jobs.polling_interval,
        )

    # -------------------------------------------------------------------------
    def start_training(self, request: StartTrainingRequest) -> JobStartResponse:
        if job_manager.is_job_running(self.JOB_TYPE):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Training is already in progress")

        configuration = request.model_dump()
        job_id = job_manager.start_job(job_type=self.JOB_TYPE, runner=run_training_job, kwargs={"configuration": configuration})
        training_state.reset_for_new_session(total_epochs=configuration.get("epochs", 10), job_id=job_id)

        return JobStartResponse(
            job_id=job_id,
            job_type=self.JOB_TYPE,
            status="running",
            message="Training job started",
            poll_interval=server_settings.jobs.polling_interval,
        )

    # -------------------------------------------------------------------------
    def resume_training(self, request: ResumeTrainingRequest) -> JobStartResponse:
        return self.start_training(StartTrainingRequest(dataset_name=None, epochs=request.additional_epochs, batch_size=32))

    # -------------------------------------------------------------------------
    def get_training_job_status(self, job_id: str) -> JobStatusResponse:
        payload = job_manager.get_job_status(job_id)
        if payload is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Job not found: {job_id}")
        return JobStatusResponse(**payload)

    # -------------------------------------------------------------------------
    def cancel_training_job(self, job_id: str) -> JobCancelResponse:
        success = job_manager.cancel_job(job_id)
        if success:
            training_state.finish_session()
        return JobCancelResponse(
            job_id=job_id,
            success=success,
            message="Cancellation requested" if success else "Job cannot be cancelled",
        )

    # -------------------------------------------------------------------------
    def stop_training(self) -> TrainingStatusResponse:
        if training_state.current_job_id:
            job_manager.cancel_job(training_state.current_job_id)
        training_state.finish_session()
        return self.get_training_status()

    # -------------------------------------------------------------------------
    def add_routes(self) -> None:
        self.router.add_api_route("/checkpoints", self.get_checkpoints, methods=["GET"], response_model=CheckpointsResponse)
        self.router.add_api_route("/checkpoints/{checkpoint}/metadata", self.get_checkpoint_metadata, methods=["GET"], response_model=CheckpointMetadataResponse)
        self.router.add_api_route("/checkpoints/{checkpoint}", self.delete_checkpoint, methods=["DELETE"], response_model=DeleteResponse)
        self.router.add_api_route("/status", self.get_training_status, methods=["GET"], response_model=TrainingStatusResponse)
        self.router.add_api_route("/start", self.start_training, methods=["POST"], response_model=JobStartResponse, status_code=status.HTTP_202_ACCEPTED)
        self.router.add_api_route("/resume", self.resume_training, methods=["POST"], response_model=JobStartResponse, status_code=status.HTTP_202_ACCEPTED)
        self.router.add_api_route("/jobs/{job_id}", self.get_training_job_status, methods=["GET"], response_model=JobStatusResponse)
        self.router.add_api_route("/jobs/{job_id}", self.cancel_training_job, methods=["DELETE"], response_model=JobCancelResponse)
        self.router.add_api_route("/stop", self.stop_training, methods=["POST"], response_model=TrainingStatusResponse)


router = APIRouter(prefix="/training", tags=["training"])
endpoint = TrainingEndpoint(router)
endpoint.add_routes()
