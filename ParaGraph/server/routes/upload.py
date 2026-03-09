from __future__ import annotations

import io
import os
from typing import Any

import pandas as pd
from fastapi import APIRouter, File, HTTPException, UploadFile, status

from ParaGraph.server.common.utils.logger import logger
from ParaGraph.server.entities.training import DatasetUploadResponse


###############################################################################
class UploadState:
    def __init__(self) -> None:
        self.storage: dict[str, Any] = {}

    # -------------------------------------------------------------------------
    def store(self, key: str, data: dict[str, Any]) -> None:
        self.storage[key] = data

    # -------------------------------------------------------------------------
    def get_latest(self) -> tuple[str, dict[str, Any]] | None:
        if not self.storage:
            return None
        latest_key = list(self.storage.keys())[-1]
        return latest_key, self.storage[latest_key]

    # -------------------------------------------------------------------------
    def is_empty(self) -> bool:
        return len(self.storage) == 0


upload_state = UploadState()


###############################################################################
class UploadEndpoint:
    def __init__(self, router: APIRouter, state: UploadState) -> None:
        self.router = router
        self.state = state

    # -------------------------------------------------------------------------
    async def upload_dataset(self, file: UploadFile = File(...)) -> DatasetUploadResponse:
        if not file.filename:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No file provided")
        filename = file.filename
        ext = os.path.splitext(filename)[1].lower()
        if ext not in {".csv", ".xlsx"}:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only CSV/XLSX files are supported")
        dataset_name = os.path.splitext(filename)[0]

        try:
            content = await file.read()
            if ext == ".csv":
                df = pd.read_csv(io.BytesIO(content), sep=None, engine="python")
            else:
                df = pd.read_excel(io.BytesIO(content))
            self.state.store(
                f"dataset_{filename}",
                {
                    "dataframe": df,
                    "filename": filename,
                    "dataset_name": dataset_name,
                },
            )
            logger.info("Uploaded dataset file %s with %s rows", filename, len(df))
            return DatasetUploadResponse(
                success=True,
                filename=filename,
                dataset_name=dataset_name,
                row_count=len(df),
                column_count=len(df.columns),
                columns=list(df.columns),
                message="Dataset parsed successfully",
            )
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Failed to parse upload: {exc}") from exc

    # -------------------------------------------------------------------------
    def add_routes(self) -> None:
        self.router.add_api_route(
            "/dataset",
            self.upload_dataset,
            methods=["POST"],
            response_model=DatasetUploadResponse,
            status_code=status.HTTP_200_OK,
        )


router = APIRouter(prefix="/upload", tags=["upload"])
endpoint = UploadEndpoint(router, upload_state)
endpoint.add_routes()

