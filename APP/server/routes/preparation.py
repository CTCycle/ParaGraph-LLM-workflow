from __future__ import annotations

import os
import string
import time
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status

from APP.server.entities.jobs import JobCancelResponse, JobStartResponse, JobStatusResponse
from APP.server.entities.training import (
    BrowseResponse,
    DatasetInfo,
    DatasetNamesResponse,
    DatasetStatusResponse,
    DeleteResponse,
    DirectoryItem,
    ImageCountResponse,
    ImageMetadataResponse,
    ImagePathRequest,
    ImagePathResponse,
    LoadDatasetRequest,
    LoadDatasetResponse,
    ProcessDatasetRequest,
    ProcessingMetadataResponse,
)
from APP.server.routes.upload import upload_state
from APP.server.services.jobs import job_manager


# -----------------------------------------------------------------------------
def run_preparation_job(configuration: dict[str, Any], job_id: str) -> dict[str, Any]:
    _ = configuration
    for step, progress in enumerate((20, 45, 75, 100), start=1):
        if job_manager.should_stop(job_id):
            return {}
        time.sleep(0.05)
        job_manager.update_progress(job_id, float(progress))
        job_manager.update_result(job_id, {"stage": f"step_{step}"})
    return {
        "success": True,
        "total_samples": 100,
        "train_samples": 80,
        "validation_samples": 20,
        "vocabulary_size": 5000,
    }


# -----------------------------------------------------------------------------
def list_windows_drives() -> list[str]:
    drives: list[str] = []
    for letter in string.ascii_uppercase:
        drive = f"{letter}:\\"
        if os.path.isdir(drive):
            drives.append(drive)
    return drives


###############################################################################
class PreparationEndpoint:
    JOB_TYPE = "preparation"

    def __init__(self, router: APIRouter) -> None:
        self.router = router
        self.processed_datasets: dict[str, dict[str, Any]] = {}

    # -------------------------------------------------------------------------
    def get_dataset_status(self) -> DatasetStatusResponse:
        latest = upload_state.get_latest()
        if latest is None:
            return DatasetStatusResponse(has_data=False, row_count=0, message="No dataset uploaded yet")
        _, payload = latest
        df = payload.get("dataframe")
        row_count = len(df) if hasattr(df, "__len__") else 0
        return DatasetStatusResponse(has_data=row_count > 0, row_count=row_count, message="Dataset available")

    # -------------------------------------------------------------------------
    def get_dataset_names(self) -> DatasetNamesResponse:
        latest = upload_state.get_latest()
        datasets: list[DatasetInfo] = []
        if latest is not None:
            _, payload = latest
            dataset_name = str(payload.get("dataset_name", "default"))
            row_count = len(payload.get("dataframe", []))
            datasets.append(
                DatasetInfo(
                    name=dataset_name,
                    folder_path="(uploaded)",
                    row_count=row_count,
                    has_validation_report=False,
                )
            )
        return DatasetNamesResponse(datasets=datasets, count=len(datasets))

    # -------------------------------------------------------------------------
    def get_processed_dataset_names(self) -> DatasetNamesResponse:
        datasets = [
            DatasetInfo(
                name=name,
                folder_path=str(meta.get("folder_path", "")),
                row_count=int(meta.get("row_count", 0)),
                has_validation_report=bool(meta.get("has_validation_report", False)),
            )
            for name, meta in self.processed_datasets.items()
        ]
        return DatasetNamesResponse(datasets=datasets, count=len(datasets))

    # -------------------------------------------------------------------------
    def get_processing_metadata(self, dataset_name: str) -> ProcessingMetadataResponse:
        metadata = self.processed_datasets.get(dataset_name)
        if metadata is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Dataset not found: {dataset_name}")
        return ProcessingMetadataResponse(dataset_name=dataset_name, metadata=metadata)

    # -------------------------------------------------------------------------
    def delete_dataset(self, dataset_name: str) -> DeleteResponse:
        if dataset_name in self.processed_datasets:
            del self.processed_datasets[dataset_name]
            return DeleteResponse(success=True, message=f"Deleted dataset {dataset_name}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Dataset not found: {dataset_name}")

    # -------------------------------------------------------------------------
    def validate_image_path(self, request: ImagePathRequest) -> ImagePathResponse:
        folder_path = request.folder_path.strip()
        valid = os.path.isdir(folder_path)
        count = 0
        if valid:
            try:
                count = sum(1 for name in os.listdir(folder_path) if os.path.isfile(os.path.join(folder_path, name)))
            except OSError:
                count = 0
        return ImagePathResponse(
            valid=valid,
            folder_path=folder_path,
            image_count=count,
            message="Path is valid" if valid else "Path not found",
        )

    # -------------------------------------------------------------------------
    def load_dataset(self, request: LoadDatasetRequest) -> LoadDatasetResponse:
        latest = upload_state.get_latest()
        if latest is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Upload a dataset first")

        _, payload = latest
        df = payload.get("dataframe")
        row_count = len(df) if hasattr(df, "__len__") else 0
        dataset_name = str(payload.get("dataset_name", "default"))
        self.processed_datasets[dataset_name] = {
            "folder_path": request.image_folder_path,
            "row_count": row_count,
            "sample_size": request.sample_size,
        }
        return LoadDatasetResponse(
            success=True,
            total_images=row_count,
            matched_records=row_count,
            unmatched_records=0,
            message="Dataset linked to assets folder",
        )

    # -------------------------------------------------------------------------
    def process_dataset(self, request: ProcessDatasetRequest) -> JobStartResponse:
        if job_manager.is_job_running(self.JOB_TYPE):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Preparation already in progress")

        job_id = job_manager.start_job(
            job_type=self.JOB_TYPE,
            runner=run_preparation_job,
            kwargs={"configuration": request.model_dump()},
        )
        return JobStartResponse(
            job_id=job_id,
            job_type=self.JOB_TYPE,
            status="running",
            message="Preparation job started",
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
    def browse(self, path: str = Query(default="")) -> BrowseResponse:
        drives = list_windows_drives()
        current_path = path or (drives[0] if drives else os.getcwd())
        items: list[DirectoryItem] = []
        try:
            for name in sorted(os.listdir(current_path)):
                full_path = os.path.join(current_path, name)
                items.append(
                    DirectoryItem(
                        name=name,
                        path=full_path,
                        is_dir=os.path.isdir(full_path),
                        image_count=0,
                    )
                )
        except OSError:
            items = []
        parent_path = os.path.dirname(current_path) if os.path.dirname(current_path) != current_path else None
        return BrowseResponse(current_path=current_path, parent_path=parent_path, items=items, drives=drives)

    # -------------------------------------------------------------------------
    def get_dataset_image_count(self, dataset_name: str) -> ImageCountResponse:
        if dataset_name not in self.processed_datasets:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")
        row_count = int(self.processed_datasets[dataset_name].get("row_count", 0))
        return ImageCountResponse(dataset_name=dataset_name, count=row_count)

    # -------------------------------------------------------------------------
    def get_dataset_image_metadata(self, dataset_name: str, index: int) -> ImageMetadataResponse:
        if dataset_name not in self.processed_datasets:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")
        return ImageMetadataResponse(
            dataset_name=dataset_name,
            index=index,
            image_name=f"asset_{index}.png",
            caption="Placeholder caption",
            valid_path=True,
            path=os.path.join(self.processed_datasets[dataset_name]["folder_path"], f"asset_{index}.png"),
        )

    # -------------------------------------------------------------------------
    def add_routes(self) -> None:
        self.router.add_api_route("/dataset/status", self.get_dataset_status, methods=["GET"], response_model=DatasetStatusResponse)
        self.router.add_api_route("/dataset/names", self.get_dataset_names, methods=["GET"], response_model=DatasetNamesResponse)
        self.router.add_api_route("/dataset/processed/names", self.get_processed_dataset_names, methods=["GET"], response_model=DatasetNamesResponse)
        self.router.add_api_route("/dataset/metadata/{dataset_name}", self.get_processing_metadata, methods=["GET"], response_model=ProcessingMetadataResponse)
        self.router.add_api_route("/dataset/{dataset_name}", self.delete_dataset, methods=["DELETE"], response_model=DeleteResponse)
        self.router.add_api_route("/images/validate", self.validate_image_path, methods=["POST"], response_model=ImagePathResponse)
        self.router.add_api_route("/dataset/load", self.load_dataset, methods=["POST"], response_model=LoadDatasetResponse)
        self.router.add_api_route("/dataset/process", self.process_dataset, methods=["POST"], response_model=JobStartResponse, status_code=status.HTTP_202_ACCEPTED)
        self.router.add_api_route("/jobs/{job_id}", self.get_job_status, methods=["GET"], response_model=JobStatusResponse)
        self.router.add_api_route("/jobs/{job_id}", self.cancel_job, methods=["DELETE"], response_model=JobCancelResponse)
        self.router.add_api_route("/browse", self.browse, methods=["GET"], response_model=BrowseResponse)
        self.router.add_api_route("/dataset/{dataset_name}/images/count", self.get_dataset_image_count, methods=["GET"], response_model=ImageCountResponse)
        self.router.add_api_route("/dataset/{dataset_name}/images/{index}", self.get_dataset_image_metadata, methods=["GET"], response_model=ImageMetadataResponse)


router = APIRouter(prefix="/preparation", tags=["preparation"])
endpoint = PreparationEndpoint(router)
endpoint.add_routes()
