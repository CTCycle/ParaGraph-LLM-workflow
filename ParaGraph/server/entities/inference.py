from __future__ import annotations

from pydantic import BaseModel, Field


###############################################################################
class StartInferenceRequest(BaseModel):
    checkpoint: str = Field(..., min_length=1)
    generation_mode: str = "greedy_search"
    request_id: str | None = None


###############################################################################
class InferenceReportItem(BaseModel):
    input_name: str
    output_text: str


###############################################################################
class InferenceResultResponse(BaseModel):
    reports: list[InferenceReportItem]
    count: int
