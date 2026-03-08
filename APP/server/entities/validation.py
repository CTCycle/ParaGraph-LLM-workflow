from __future__ import annotations

from typing import Any

from pydantic import BaseModel


###############################################################################
class StartValidationRequest(BaseModel):
    dataset_name: str
    sample_size: float = 0.1
    include_text_stats: bool = True
    include_asset_stats: bool = False


###############################################################################
class StartCheckpointEvaluationRequest(BaseModel):
    checkpoint: str
    metric_names: list[str] = ["loss", "accuracy"]


###############################################################################
class ValidationReportResponse(BaseModel):
    dataset_name: str
    metrics: dict[str, Any]


###############################################################################
class CheckpointEvaluationReportResponse(BaseModel):
    checkpoint: str
    metrics: dict[str, Any]
