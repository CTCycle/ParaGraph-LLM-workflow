from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


ExecutionStatus = Literal[
    "queued", "running", "completed", "failed", "cancelled", "paused"
]
ExecutionStepStatus = Literal["queued", "running", "completed", "failed", "skipped"]
RUN_ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$"
ExecutionEventType = Literal[
    "execution.queued",
    "execution.started",
    "execution.step.started",
    "execution.step.progress",
    "execution.step.completed",
    "execution.step.failed",
    "execution.cancellation.requested",
    "execution.cancelled",
    "execution.step.retry.started",
    "execution.step.retry.failed",
    "execution.step.timeout",
    "execution.paused",
    "execution.resumed",
    "execution.recovered",
    "execution.completed",
    "execution.failed",
]

###############################################################################
class ExecutionBinding(BaseModel):
    binding_type: Literal["input", "controller"] = "input"
    input_name: str
    source_node_id: str
    source_output: str

###############################################################################
class ExecutionStepPlan(BaseModel):
    step_id: str
    node_id: str
    node_type: str
    node_version: int
    category: str
    executor_key: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    bindings: list[ExecutionBinding] = Field(default_factory=list)
    timeout_ms: int | None = None
    retries: int = 0
    cacheable: bool = False

###############################################################################
class CompiledExecutionPlan(BaseModel):
    plan_id: str
    schema_version: int = 2
    step_order: list[str] = Field(default_factory=list)
    steps: list[ExecutionStepPlan] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

###############################################################################
class ExecutionStepState(BaseModel):
    step_id: str
    node_id: str
    node_type: str
    status: ExecutionStepStatus = "queued"
    started_at: datetime | None = None
    completed_at: datetime | None = None
    output: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    pause_payload: dict[str, Any] | None = None
    resume_token: str | None = None
    position: int = 0
    attempt_count: int = 0
    blocked_reason: str | None = None

###############################################################################
class ExecutionRunState(BaseModel):
    run_id: str
    request_id: str | None = None
    workflow_id: str | None = None
    execution_session_id: str | None = None
    plan_id: str
    status: ExecutionStatus = "queued"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    progress: float = 0.0
    steps: list[ExecutionStepState] = Field(default_factory=list)
    outputs: dict[str, dict[str, Any]] = Field(default_factory=dict)
    error: str | None = None
    pause_payload: dict[str, Any] | None = None
    resume_token: str | None = None
    plan: CompiledExecutionPlan | None = None
    cancellation_requested: bool = False

###############################################################################
class ExecutionEventEnvelope(BaseModel):
    event_type: ExecutionEventType
    run_id: str
    request_id: str | None = None
    step_id: str | None = None
    sequence: int
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    payload: dict[str, Any] = Field(default_factory=dict)

###############################################################################
class StartExecutionRequest(BaseModel):
    workflow_id: str | None = None
    execution_session_id: str | None = None
    plan: CompiledExecutionPlan

###############################################################################
class StartExecutionResponse(BaseModel):
    run_id: str
    request_id: str | None = None
    status: ExecutionStatus
    execution_session_id: str | None = None
    poll_interval: float = 1.0

###############################################################################
class EventHistoryResponse(BaseModel):
    run_id: str
    request_id: str | None = None
    events: list[ExecutionEventEnvelope] = Field(default_factory=list)

###############################################################################
class ResumeExecutionRequest(BaseModel):
    resume_token: str
    reviewed_payload: dict[str, Any] | None = None

###############################################################################
class ExecutionActionResponse(BaseModel):
    run_id: str
    status: ExecutionStatus
    message: str
