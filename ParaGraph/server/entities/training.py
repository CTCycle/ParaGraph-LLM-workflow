from __future__ import annotations

from pydantic import BaseModel, Field


###############################################################################
class DatasetUploadResponse(BaseModel):
    success: bool
    filename: str
    dataset_name: str
    row_count: int
    column_count: int
    columns: list[str]
    message: str


###############################################################################
class ImagePathRequest(BaseModel):
    folder_path: str = Field(..., description="Server-side folder containing assets")


###############################################################################
class ImagePathResponse(BaseModel):
    valid: bool
    folder_path: str
    image_count: int
    message: str


###############################################################################
class LoadDatasetRequest(BaseModel):
    image_folder_path: str
    sample_size: float = Field(1.0, ge=0.01, le=1.0)


###############################################################################
class LoadDatasetResponse(BaseModel):
    success: bool
    total_images: int
    matched_records: int
    unmatched_records: int
    message: str


###############################################################################
class ProcessDatasetRequest(BaseModel):
    dataset_name: str
    custom_name: str | None = None
    sample_size: float = Field(1.0, ge=0.01, le=1.0)
    validation_size: float = Field(0.2, ge=0.05, le=0.5)
    tokenizer: str = "generic-tokenizer"
    max_report_size: int = Field(200, ge=50, le=1000)


###############################################################################
class ProcessDatasetResponse(BaseModel):
    success: bool
    total_samples: int
    train_samples: int
    validation_samples: int
    vocabulary_size: int
    message: str


###############################################################################
class DatasetStatusResponse(BaseModel):
    has_data: bool
    row_count: int
    message: str


###############################################################################
class DatasetInfo(BaseModel):
    name: str
    folder_path: str
    row_count: int
    has_validation_report: bool = False


###############################################################################
class DatasetNamesResponse(BaseModel):
    datasets: list[DatasetInfo]
    count: int


###############################################################################
class ProcessingMetadataResponse(BaseModel):
    dataset_name: str
    metadata: dict[str, object]


###############################################################################
class DirectoryItem(BaseModel):
    name: str
    path: str
    is_dir: bool
    image_count: int = 0


###############################################################################
class BrowseResponse(BaseModel):
    current_path: str
    parent_path: str | None = None
    items: list[DirectoryItem]
    drives: list[str] = []


###############################################################################
class ImageCountResponse(BaseModel):
    dataset_name: str
    count: int


###############################################################################
class ImageMetadataResponse(BaseModel):
    dataset_name: str
    index: int
    image_name: str
    caption: str
    valid_path: bool
    path: str


###############################################################################
class StartTrainingRequest(BaseModel):
    dataset_name: str | None = None
    epochs: int = Field(10, ge=1, le=1000)
    batch_size: int = Field(32, ge=1, le=256)


###############################################################################
class ResumeTrainingRequest(BaseModel):
    checkpoint: str
    additional_epochs: int = Field(10, ge=1, le=1000)


###############################################################################
class CheckpointInfo(BaseModel):
    name: str
    epochs: int = 0
    loss: float = 0.0
    val_loss: float = 0.0


###############################################################################
class CheckpointsResponse(BaseModel):
    checkpoints: list[CheckpointInfo]


###############################################################################
class CheckpointMetadataResponse(BaseModel):
    checkpoint: str
    configuration: dict[str, object]
    metadata: dict[str, object]
    session: dict[str, object]


###############################################################################
class TrainingStatusResponse(BaseModel):
    job_id: str | None = None
    is_training: bool
    current_epoch: int = 0
    total_epochs: int = 0
    loss: float = 0.0
    val_loss: float = 0.0
    accuracy: float = 0.0
    val_accuracy: float = 0.0
    progress_percent: int = 0
    elapsed_seconds: int = 0
    poll_interval: float = 1.0


###############################################################################
class DeleteResponse(BaseModel):
    success: bool
    message: str
