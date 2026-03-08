from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import declarative_base

from APP.server.repositories.schemas.types import JSONSequence

Base = declarative_base()


###############################################################################
class Dataset(Base):
    __tablename__ = "datasets"
    dataset_id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    __table_args__ = (UniqueConstraint("name", name="uq_datasets_name"),)


###############################################################################
class DatasetRecord(Base):
    __tablename__ = "dataset_records"
    record_id = Column(Integer, primary_key=True, autoincrement=True)
    dataset_id = Column(Integer, ForeignKey("datasets.dataset_id", ondelete="CASCADE"), nullable=False)
    asset_name = Column(String, nullable=False)
    asset_path = Column(String, nullable=False)
    content = Column(String, nullable=False)
    row_order = Column(Integer, nullable=False)


###############################################################################
class ProcessingRun(Base):
    __tablename__ = "processing_runs"
    processing_run_id = Column(Integer, primary_key=True, autoincrement=True)
    dataset_id = Column(Integer, ForeignKey("datasets.dataset_id", ondelete="CASCADE"), nullable=False)
    config_hash = Column(String, nullable=False)
    executed_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


###############################################################################
class TrainingSample(Base):
    __tablename__ = "training_samples"
    training_sample_id = Column(Integer, primary_key=True, autoincrement=True)
    processing_run_id = Column(Integer, ForeignKey("processing_runs.processing_run_id", ondelete="CASCADE"), nullable=False)
    record_id = Column(Integer, ForeignKey("dataset_records.record_id", ondelete="CASCADE"), nullable=False)
    split = Column(String, nullable=False)
    features_json = Column(JSONSequence, nullable=False)


###############################################################################
class ValidationRun(Base):
    __tablename__ = "validation_runs"
    validation_run_id = Column(Integer, primary_key=True, autoincrement=True)
    dataset_id = Column(Integer, ForeignKey("datasets.dataset_id", ondelete="CASCADE"), nullable=False)
    executed_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    sample_size = Column(Float, nullable=False)
    metrics_json = Column(JSONSequence, nullable=False)


###############################################################################
class Checkpoint(Base):
    __tablename__ = "checkpoints"
    checkpoint_id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    path = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    __table_args__ = (
        UniqueConstraint("name", name="uq_checkpoints_name"),
        UniqueConstraint("path", name="uq_checkpoints_path"),
    )


###############################################################################
class InferenceRun(Base):
    __tablename__ = "inference_runs"
    inference_run_id = Column(Integer, primary_key=True, autoincrement=True)
    checkpoint_id = Column(Integer, ForeignKey("checkpoints.checkpoint_id", ondelete="CASCADE"), nullable=False)
    request_id = Column(String)
    executed_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    __table_args__ = (UniqueConstraint("request_id", name="uq_inference_runs_request_id"),)


###############################################################################
class InferenceReport(Base):
    __tablename__ = "inference_reports"
    inference_report_id = Column(Integer, primary_key=True, autoincrement=True)
    inference_run_id = Column(Integer, ForeignKey("inference_runs.inference_run_id", ondelete="CASCADE"), nullable=False)
    input_name = Column(String, nullable=False)
    output_text = Column(String, nullable=False)
