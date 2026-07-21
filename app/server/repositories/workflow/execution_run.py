from __future__ import annotations

from datetime import datetime, timedelta, timezone
import threading
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from server.configurations.startup import get_server_settings
from server.domain.execution import (
    CompiledExecutionPlan,
    ExecutionEventEnvelope,
    ExecutionRunState,
    ExecutionStepState,
)
from server.repositories.database.factory import DatabaseRepositoryFactory
from server.repositories.schemas import (
    Base,
    ExecutionEventRecord,
    ExecutionRunRecord,
    ExecutionStepRecord,
)

###############################################################################
class ExecutionRunRepository:
    """Durable execution state backed by the application database."""

    # -------------------------------------------------------------------------
    def __init__(
        self, database_factory: DatabaseRepositoryFactory | None = None
    ) -> None:
        self._database_factory = database_factory or DatabaseRepositoryFactory()
        self._cached_engine = None
        self._engine_lock = threading.Lock()

    # -------------------------------------------------------------------------
    def _engine(self):
        with self._engine_lock:
            if self._cached_engine is None:
                self._cached_engine = self._database_factory.build(
                    get_server_settings().database
                ).engine
                Base.metadata.create_all(self._cached_engine)
            return self._cached_engine

    # -------------------------------------------------------------------------
    @staticmethod
    def _aware(value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

    # -------------------------------------------------------------------------
    def create_run(self, run: ExecutionRunState) -> None:
        if run.plan is None:
            raise ValueError("Execution run requires its serialized plan")
        with Session(self._engine()) as session, session.begin():
            session.add(
                ExecutionRunRecord(
                    run_id=run.run_id,
                    request_id=run.request_id,
                    workflow_id=run.workflow_id,
                    execution_session_id=run.execution_session_id,
                    plan_id=run.plan_id,
                    plan_json=run.plan.model_dump(mode="json"),
                    status=run.status,
                    progress=run.progress,
                    outputs_json=run.outputs,
                    error=run.error,
                    pause_payload_json=run.pause_payload,
                    resume_token=run.resume_token,
                    cancellation_requested=run.cancellation_requested,
                    created_at=run.created_at,
                    updated_at=run.updated_at,
                )
            )
            for position, step in enumerate(run.steps):
                session.add(self._step_record(run.run_id, step, position))

    # -------------------------------------------------------------------------
    @staticmethod
    def _step_record(
        run_id: str, step: ExecutionStepState, position: int
    ) -> ExecutionStepRecord:
        return ExecutionStepRecord(
            run_id=run_id,
            step_id=step.step_id,
            node_id=step.node_id,
            node_type=step.node_type,
            position=step.position or position,
            status=step.status,
            attempt_count=step.attempt_count,
            started_at=step.started_at,
            completed_at=step.completed_at,
            output_json=step.output,
            error=step.error,
            blocked_reason=step.blocked_reason,
            pause_payload_json=step.pause_payload,
            resume_token=step.resume_token,
        )

    # -------------------------------------------------------------------------
    def get_run(self, run_id: str) -> ExecutionRunState | None:
        with Session(self._engine()) as session:
            row = session.get(ExecutionRunRecord, run_id)
            if row is None:
                return None
            steps = list(
                session.execute(
                    select(ExecutionStepRecord)
                    .where(ExecutionStepRecord.run_id == run_id)
                    .order_by(ExecutionStepRecord.position)
                ).scalars()
            )
            return ExecutionRunState(
                run_id=row.run_id,
                request_id=row.request_id,
                workflow_id=row.workflow_id,
                execution_session_id=row.execution_session_id,
                plan_id=row.plan_id,
                plan=CompiledExecutionPlan.model_validate(row.plan_json),
                status=row.status,
                created_at=self._aware(row.created_at),
                updated_at=self._aware(row.updated_at),
                progress=row.progress,
                outputs=row.outputs_json or {},
                error=row.error,
                pause_payload=row.pause_payload_json,
                resume_token=row.resume_token,
                cancellation_requested=row.cancellation_requested,
                steps=[
                    ExecutionStepState(
                        step_id=item.step_id,
                        node_id=item.node_id,
                        node_type=item.node_type,
                        position=item.position,
                        status=item.status,
                        attempt_count=item.attempt_count,
                        started_at=self._aware(item.started_at),
                        completed_at=self._aware(item.completed_at),
                        output=item.output_json or {},
                        error=item.error,
                        blocked_reason=item.blocked_reason,
                        pause_payload=item.pause_payload_json,
                        resume_token=item.resume_token,
                    )
                    for item in steps
                ],
            )

    # -------------------------------------------------------------------------
    def update_run(self, run_id: str, **kwargs: Any) -> ExecutionRunState | None:
        aliases = {"outputs": "outputs_json", "pause_payload": "pause_payload_json"}
        with Session(self._engine()) as session, session.begin():
            row = session.get(ExecutionRunRecord, run_id)
            if row is None:
                return None
            for key, value in kwargs.items():
                column = aliases.get(key, key)
                if not hasattr(row, column):
                    raise ValueError(f"Unsupported run field: {key}")
                setattr(row, column, value)
            row.updated_at = datetime.now(timezone.utc)
        return self.get_run(run_id)

    # -------------------------------------------------------------------------
    def update_step(
        self, run_id: str, step_id: str, **updates: Any
    ) -> ExecutionRunState | None:
        aliases = {"output": "output_json", "pause_payload": "pause_payload_json"}
        with Session(self._engine()) as session, session.begin():
            row = session.execute(
                select(ExecutionStepRecord).where(
                    ExecutionStepRecord.run_id == run_id,
                    ExecutionStepRecord.step_id == step_id,
                )
            ).scalar_one_or_none()
            if row is None:
                return None
            for key, value in updates.items():
                column = aliases.get(key, key)
                if not hasattr(row, column):
                    raise ValueError(f"Unsupported step field: {key}")
                setattr(row, column, value)
            run = session.get(ExecutionRunRecord, run_id)
            if run is not None:
                run.updated_at = datetime.now(timezone.utc)
        return self.get_run(run_id)

    # -------------------------------------------------------------------------
    def set_steps(
        self, run_id: str, steps: list[ExecutionStepState]
    ) -> ExecutionRunState | None:
        with Session(self._engine()) as session, session.begin():
            if session.get(ExecutionRunRecord, run_id) is None:
                return None
            session.execute(
                delete(ExecutionStepRecord).where(ExecutionStepRecord.run_id == run_id)
            )
            session.add_all(
                [
                    self._step_record(run_id, step, index)
                    for index, step in enumerate(steps)
                ]
            )
        return self.get_run(run_id)

    # -------------------------------------------------------------------------
    def append_event(
        self,
        *,
        run_id: str,
        event_type: str,
        payload: dict[str, Any],
        step_id: str | None = None,
        request_id: str | None = None,
    ) -> ExecutionEventEnvelope:
        with Session(self._engine()) as session, session.begin():
            sequence = (
                session.execute(
                    select(func.max(ExecutionEventRecord.sequence)).where(
                        ExecutionEventRecord.run_id == run_id
                    )
                ).scalar_one_or_none()
                or 0
            ) + 1
            row = ExecutionEventRecord(
                run_id=run_id,
                sequence=sequence,
                event_type=event_type,
                payload_json=payload,
                step_id=step_id,
                request_id=request_id,
            )
            session.add(row)
            session.flush()
            timestamp = row.timestamp
        return ExecutionEventEnvelope(
            event_type=event_type,
            run_id=run_id,
            request_id=request_id,
            step_id=step_id,
            sequence=sequence,
            timestamp=self._aware(timestamp),
            payload=payload,
        )

    # -------------------------------------------------------------------------
    def get_events(self, run_id: str) -> list[ExecutionEventEnvelope]:
        with Session(self._engine()) as session:
            rows = list(
                session.execute(
                    select(ExecutionEventRecord)
                    .where(ExecutionEventRecord.run_id == run_id)
                    .order_by(ExecutionEventRecord.sequence)
                ).scalars()
            )
            return [
                ExecutionEventEnvelope(
                    event_type=row.event_type,
                    run_id=row.run_id,
                    request_id=row.request_id,
                    step_id=row.step_id,
                    sequence=row.sequence,
                    timestamp=self._aware(row.timestamp),
                    payload=row.payload_json or {},
                )
                for row in rows
            ]

    # -------------------------------------------------------------------------
    def list_recoverable(self) -> list[ExecutionRunState]:
        with Session(self._engine()) as session:
            ids = list(
                session.execute(
                    select(ExecutionRunRecord.run_id).where(
                        ExecutionRunRecord.status.in_(("queued", "running"))
                    )
                ).scalars()
            )
        return [run for run_id in ids if (run := self.get_run(run_id)) is not None]

    # -------------------------------------------------------------------------
    def cleanup_completed_before(self, cutoff: datetime) -> int:
        with Session(self._engine()) as session, session.begin():
            result = session.execute(
                delete(ExecutionRunRecord).where(
                    ExecutionRunRecord.status.in_(("completed", "failed", "cancelled")),
                    ExecutionRunRecord.updated_at < cutoff,
                )
            )
            return int(result.rowcount or 0)

    # -------------------------------------------------------------------------
    def cleanup_retention(self, retention_days: int) -> int:
        if retention_days < 1:
            raise ValueError("retention_days must be at least one")
        return self.cleanup_completed_before(
            datetime.now(timezone.utc) - timedelta(days=retention_days)
        )

    # -------------------------------------------------------------------------
    def reset_for_tests(self) -> None:
        with Session(self._engine()) as session, session.begin():
            session.execute(delete(ExecutionEventRecord))
            session.execute(delete(ExecutionStepRecord))
            session.execute(delete(ExecutionRunRecord))


execution_run_repository = ExecutionRunRepository()
