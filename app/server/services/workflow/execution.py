from __future__ import annotations

import hashlib
import json
import secrets
import uuid
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from datetime import datetime, timezone
from typing import Any

from server.common.security import redact_sensitive_payload
from server.configurations.startup import get_server_settings
from server.contracts.chat_history import ChatHistoryHandle
from server.contracts.execution import (
    CompiledExecutionPlan,
    ExecutionRunState,
    ExecutionStepState,
    PauseCheckpoint,
    StartExecutionResponse,
)
from server.repositories.workflow import execution_run_repository
from server.services.jobs import job_manager
from server.services.runtime.events import execution_event_service
from server.services.workflow.nodes import node_registry
from server.services.workflow.node_handlers.core.tools import (
    release_run_tool_resources,
)
from server.common.utils.values import (
    extract_top_level_json_fields,
    validate_json_against_schema,
)

###############################################################################
class ExecutionService:
    SKIP_SENTINEL = "__paragraph_skip__"

    # -------------------------------------------------------------------------
    def start_execution(
        self,
        plan: CompiledExecutionPlan,
        workflow_id: str | None = None,
        execution_session_id: str | None = None,
        request_id: str | None = None,
    ) -> str:
        run_id = str(uuid.uuid4())[:8]
        self._initialize_run(
            plan, workflow_id, execution_session_id, run_id, request_id=request_id
        )
        return job_manager.start_job(
            job_type="workflow",
            runner=self.execute_plan_job,
            kwargs={
                "plan": plan,
                "workflow_id": workflow_id,
                "execution_session_id": execution_session_id,
                "request_id": request_id,
            },
            job_id=run_id,
        )

    # -------------------------------------------------------------------------
    def start_execution_response(
        self,
        plan: CompiledExecutionPlan,
        workflow_id: str | None = None,
        execution_session_id: str | None = None,
        request_id: str | None = None,
    ) -> StartExecutionResponse:
        run_id = self.start_execution(
            plan,
            workflow_id=workflow_id,
            execution_session_id=execution_session_id,
            request_id=request_id,
        )
        return StartExecutionResponse(
            run_id=run_id,
            request_id=request_id,
            status="queued",
            execution_session_id=execution_session_id,
            poll_interval=get_server_settings().jobs.polling_interval,
        )

    # -------------------------------------------------------------------------
    def get_run(self, run_id: str) -> ExecutionRunState | None:
        return execution_run_repository.get_run(run_id)

    # -------------------------------------------------------------------------
    def execute_plan_job(
        self,
        plan: CompiledExecutionPlan,
        workflow_id: str | None,
        job_id: str,
        execution_session_id: str | None = None,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        if execution_run_repository.get_run(job_id) is None:
            self._initialize_run(
                plan, workflow_id, execution_session_id, job_id, request_id=request_id
            )
        else:
            execution_run_repository.update_run(job_id, status="running")
            execution_event_service.publish(
                run_id=job_id,
                event_type="execution.started",
                request_id=request_id,
                payload={"plan_id": plan.plan_id},
            )
        persisted = execution_run_repository.get_run(job_id)
        outputs_by_step = {
            step.step_id: dict(step.output.get("ports", {}))
            for step in (persisted.steps if persisted else [])
            if step.status == "completed"
        }
        output_payload = dict(persisted.outputs if persisted else {})
        cache: dict[str, dict[str, Any]] = {}
        step_lookup = {step.step_id: step for step in plan.steps}
        total_steps = len(plan.step_order) or 1

        for index, step_id in enumerate(plan.step_order, start=1):
            if self._cancelled(job_id):
                return {}

            step = step_lookup[step_id]
            current = execution_run_repository.get_run(job_id)
            current_step = (
                next((item for item in current.steps if item.step_id == step_id), None)
                if current
                else None
            )
            if current_step is not None and current_step.status == "completed":
                continue
            try:
                if self._should_skip_step(step, outputs_by_step):
                    self._skip_step(job_id, step_id)
                    continue
                output_state_public = self._execute_step_with_policy(
                    job_id=job_id,
                    workflow_id=workflow_id,
                    execution_session_id=execution_session_id,
                    step=step,
                    outputs_by_step=outputs_by_step,
                    output_payload=output_payload,
                    cache=cache,
                    step_lookup=step_lookup,
                )
                if self._is_pause_output(outputs_by_step.get(step.step_id, {})):
                    self._pause_run(
                        job_id,
                        step,
                        outputs_by_step[step.step_id],
                        output_state_public,
                    )
                    return {"outputs": output_payload}
                computed_progress = (index / total_steps) * 100.0
                progress = computed_progress if index < total_steps else 99.0
                self._complete_step(job_id, step_id, output_state_public, progress)
            except Exception as exc:  # noqa: BLE001
                self._fail_step(job_id, step_id, str(exc))
                raise

        if self._cancelled(job_id):
            return {}
        try:
            self._persist_chat_history(
                plan,
                outputs_by_step=outputs_by_step,
                output_payload=output_payload,
            )
        except Exception as exc:  # noqa: BLE001
            message = f"CHAT_HISTORY_PERSISTENCE_FAILED: {exc}"
            execution_run_repository.update_run(job_id, status="failed", error=message)
            release_run_tool_resources(job_id)
            execution_event_service.publish(
                run_id=job_id,
                event_type="execution.failed",
                request_id=self._request_id_for_run(job_id),
                payload={"error": message},
            )
            raise RuntimeError(message) from exc
        execution_run_repository.update_run(
            job_id, status="completed", outputs=output_payload, progress=100.0
        )
        release_run_tool_resources(job_id)
        execution_event_service.publish(
            run_id=job_id,
            event_type="execution.completed",
            request_id=request_id,
            payload={"outputs": output_payload},
        )
        return {"outputs": output_payload}

    # -------------------------------------------------------------------------
    def _persist_chat_history(
        self,
        plan: CompiledExecutionPlan,
        *,
        outputs_by_step: dict[str, dict[str, Any]],
        output_payload: dict[str, dict[str, Any]],
    ) -> None:
        raw_mapping = plan.metadata.get("chat_terminal_outputs")
        if not isinstance(raw_mapping, dict):
            return

        from server.services.workflow.chat_history import chat_history_service

        steps_by_node_id = {step.node_id: step for step in plan.steps}
        for raw_chat_node_id, raw_terminal_node_id in raw_mapping.items():
            chat_node_id = str(raw_chat_node_id)
            terminal_node_id = str(raw_terminal_node_id)
            chat_step = steps_by_node_id.get(chat_node_id)
            if chat_step is None or chat_step.node_type != "CHAT_INPUT":
                continue

            raw_handle = outputs_by_step.get(chat_step.step_id, {}).get("history")
            if raw_handle is None:
                raise ValueError(
                    f"Chat node '{chat_node_id}' did not produce a history handle"
                )
            handle = ChatHistoryHandle.model_validate(raw_handle)
            terminal_output = output_payload.get(terminal_node_id)
            assistant_output = self._format_chat_terminal_output(terminal_output)
            chat_history_service.append_chat_result(
                handle,
                user_message=str(chat_step.parameters.get("message") or ""),
                assistant_output=assistant_output,
            )

    # -------------------------------------------------------------------------
    @staticmethod
    def _format_chat_terminal_output(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        if isinstance(value, dict):
            if isinstance(value.get("text"), str):
                return value["text"]
            if "json" in value:
                from server.services.workflow.chat_history import chat_history_service

                return chat_history_service.serialize_structured_output(value["json"])
        from server.services.workflow.chat_history import chat_history_service

        return chat_history_service.serialize_structured_output(value)

    # -------------------------------------------------------------------------
    def _initialize_run(
        self,
        plan: CompiledExecutionPlan,
        workflow_id: str | None,
        execution_session_id: str | None,
        job_id: str,
        *,
        request_id: str | None,
    ) -> None:
        steps_state = [
            ExecutionStepState(
                step_id=step.step_id,
                node_id=step.node_id,
                node_type=step.node_type,
                position=index,
            )
            for index, step in enumerate(plan.steps)
        ]
        run = ExecutionRunState(
            run_id=job_id,
            request_id=request_id,
            workflow_id=workflow_id,
            execution_session_id=execution_session_id,
            plan_id=plan.plan_id,
            plan=plan,
            status="queued",
            steps=steps_state,
        )
        execution_run_repository.create_run(run)
        execution_event_service.publish(
            run_id=job_id,
            event_type="execution.queued",
            request_id=request_id,
            payload={"plan_id": plan.plan_id},
        )
        execution_run_repository.update_run(job_id, status="running", progress=0.0)
        execution_event_service.publish(
            run_id=job_id,
            event_type="execution.started",
            request_id=request_id,
            payload={"plan_id": plan.plan_id},
        )

    # -------------------------------------------------------------------------
    def _cancelled(self, job_id: str) -> bool:
        run = execution_run_repository.get_run(job_id)
        requested = bool(run and run.cancellation_requested)
        if not requested and not job_manager.should_stop(job_id):
            return False
        if run and run.status not in ("completed", "failed", "cancelled"):
            execution_run_repository.update_run(job_id, status="cancelled")
            release_run_tool_resources(job_id)
            execution_event_service.publish(
                run_id=job_id,
                event_type="execution.cancelled",
                request_id=run.request_id,
                payload={"message": "Execution cancelled"},
            )
        return True

    # -------------------------------------------------------------------------
    def cancel(self, run_id: str) -> ExecutionRunState | None:
        run = execution_run_repository.get_run(run_id)
        if run is None or run.status in ("completed", "failed", "cancelled"):
            return run
        execution_run_repository.update_run(run_id, cancellation_requested=True)
        execution_event_service.publish(
            run_id=run_id,
            event_type="execution.cancellation.requested",
            request_id=run.request_id,
            payload={"status": run.status},
        )
        manager_accepted = job_manager.cancel_job(run_id)
        if run.status in ("queued", "paused") or not manager_accepted:
            self._cancelled(run_id)
        return execution_run_repository.get_run(run_id)

    # -------------------------------------------------------------------------
    @staticmethod
    def _validate_reviewed_payload(
        payload: dict[str, Any], checkpoint: PauseCheckpoint
    ) -> None:
        try:
            validate_json_against_schema(
                payload, checkpoint.expected_reviewed_payload_schema
            )
        except ValueError as exc:
            raise ValueError(f"Invalid reviewed payload: {exc}") from exc

    # -------------------------------------------------------------------------
    @staticmethod
    def _build_resumed_output(
        run: ExecutionRunState,
        checkpoint: PauseCheckpoint,
        reviewed_payload: dict[str, Any],
    ) -> dict[str, Any]:
        step = next(
            (
                item
                for item in run.steps
                if item.step_id == checkpoint.step_id
                and item.node_id == checkpoint.node_id
            ),
            None,
        )
        if step is None:
            raise ValueError("legacy_pause_state_not_resumable")

        output = dict(step.output or {})
        ports = dict(output.get("ports") or {})
        ports.pop("paused", None)
        ports.pop("pause_payload", None)
        ports["result"] = reviewed_payload
        output["ports"] = ports
        return output

    # -------------------------------------------------------------------------
    def resume(
        self,
        run_id: str,
        resume_token: str,
        reviewed_payload: dict[str, Any] | None = None,
    ) -> ExecutionRunState | None:
        run = execution_run_repository.get_run(run_id)
        if run is None:
            return None
        if run.plan is None:
            raise ValueError("Persisted execution plan is unavailable")
        if run.status != "paused" or run.resume_token != resume_token:
            raise ValueError("Run is not paused or resume token is invalid")
        checkpoint = run.pause_checkpoint
        if checkpoint is None:
            raise ValueError("legacy_pause_state_not_resumable")

        payload = reviewed_payload or {}
        self._validate_reviewed_payload(payload, checkpoint)
        resumed_output = self._build_resumed_output(run, checkpoint, payload)
        resumed = execution_run_repository.consume_pause_checkpoint(
            run_id, resume_token, resumed_output
        )
        if resumed is None:
            return None
        execution_event_service.publish(
            run_id=run_id,
            event_type="execution.resumed",
            request_id=run.request_id,
            payload={
                "reviewed_payload": reviewed_payload or {},
                "node_id": (
                    run.pause_checkpoint.node_id
                    if run.pause_checkpoint is not None
                    else None
                ),
            },
        )
        job_manager.start_job(
            job_type="workflow",
            runner=self.execute_plan_job,
            kwargs={
                "plan": run.plan,
                "workflow_id": run.workflow_id,
                "execution_session_id": run.execution_session_id,
                "request_id": run.request_id,
            },
            job_id=run_id,
        )
        return execution_run_repository.get_run(run_id)

    # -------------------------------------------------------------------------
    def recover_interrupted(self) -> int:
        recovered = 0
        for run in execution_run_repository.list_recoverable():
            if run.plan is None:
                execution_run_repository.update_run(
                    run.run_id,
                    status="failed",
                    error="RECOVERY_UNAVAILABLE: persisted plan is missing",
                )
                continue
            if any(step.status == "running" for step in run.steps):
                message = (
                    "RECOVERY_UNAVAILABLE: an interrupted running step may have "
                    "produced side effects"
                )
                execution_run_repository.update_run(
                    run.run_id, status="failed", error=message
                )
                execution_event_service.publish(
                    run_id=run.run_id,
                    event_type="execution.recovered",
                    request_id=run.request_id,
                    payload={"policy": "marked_unrecoverable", "error": message},
                )
                continue
            execution_run_repository.update_run(run.run_id, status="queued")
            execution_event_service.publish(
                run_id=run.run_id,
                event_type="execution.recovered",
                request_id=run.request_id,
                payload={"policy": "resume_after_completed_steps"},
            )
            job_manager.start_job(
                job_type="workflow",
                runner=self.execute_plan_job,
                kwargs={
                    "plan": run.plan,
                    "workflow_id": run.workflow_id,
                    "execution_session_id": run.execution_session_id,
                    "request_id": run.request_id,
                },
                job_id=run.run_id,
            )
            recovered += 1
        return recovered

    # -------------------------------------------------------------------------
    def _execute_step_with_policy(self, **kwargs: Any) -> dict[str, Any]:
        step = kwargs["step"]
        job_id = kwargs["job_id"]
        if (
            step.retries > 0
            and getattr(step, "side_effecting", False)
            and not getattr(step, "idempotent", False)
        ):
            raise ValueError(
                f"Step '{step.step_id}' is side-effecting and has no idempotency contract"
            )
        attempts = step.retries + 1
        for attempt in range(1, attempts + 1):
            self._start_step(job_id, step, attempt)
            local_kwargs = dict(kwargs)
            local_kwargs["outputs_by_step"] = dict(kwargs["outputs_by_step"])
            local_kwargs["output_payload"] = dict(kwargs["output_payload"])
            local_kwargs["cache"] = dict(kwargs["cache"])
            executor = ThreadPoolExecutor(
                max_workers=1, thread_name_prefix=f"step-{step.step_id}"
            )
            future = executor.submit(self._execute_step, **local_kwargs)
            try:
                result = future.result(
                    timeout=(step.timeout_ms / 1000) if step.timeout_ms else None
                )
                kwargs["outputs_by_step"].clear()
                kwargs["outputs_by_step"].update(local_kwargs["outputs_by_step"])
                kwargs["output_payload"].clear()
                kwargs["output_payload"].update(local_kwargs["output_payload"])
                kwargs["cache"].clear()
                kwargs["cache"].update(local_kwargs["cache"])
                executor.shutdown(wait=False)
                return result
            except FutureTimeoutError as exc:
                future.cancel()
                executor.shutdown(wait=False, cancel_futures=True)
                message = f"STEP_TIMEOUT: step exceeded {step.timeout_ms} ms"
                execution_event_service.publish(
                    run_id=job_id,
                    event_type="execution.step.timeout",
                    step_id=step.step_id,
                    request_id=self._request_id_for_run(job_id),
                    payload={
                        "attempt": attempt,
                        "timeout_ms": step.timeout_ms,
                        "error": message,
                    },
                )
                raise TimeoutError(message) from exc
            except Exception as exc:  # noqa: BLE001
                executor.shutdown(wait=False, cancel_futures=True)
                if attempt >= attempts:
                    raise
                execution_event_service.publish(
                    run_id=job_id,
                    event_type="execution.step.retry.failed",
                    step_id=step.step_id,
                    request_id=self._request_id_for_run(job_id),
                    payload={"attempt": attempt, "error": str(exc)},
                )
                execution_event_service.publish(
                    run_id=job_id,
                    event_type="execution.step.retry.started",
                    step_id=step.step_id,
                    request_id=self._request_id_for_run(job_id),
                    payload={"attempt": attempt + 1, "max_attempts": attempts},
                )
        raise RuntimeError("Unreachable retry state")

    # -------------------------------------------------------------------------
    def _start_step(self, job_id: str, step: Any, attempt: int = 1) -> None:
        self._set_step_state(
            job_id,
            step.step_id,
            status="running",
            started_at=datetime.now(timezone.utc),
            attempt_count=attempt,
            error=None,
        )
        execution_event_service.publish(
            run_id=job_id,
            event_type="execution.step.started",
            step_id=step.step_id,
            request_id=self._request_id_for_run(job_id),
            payload={
                "node_type": step.node_type,
                "node_id": step.node_id,
                "attempt": attempt,
            },
        )

    # -------------------------------------------------------------------------
    def _execute_step(
        self,
        *,
        job_id: str,
        workflow_id: str | None,
        execution_session_id: str | None,
        step: Any,
        outputs_by_step: dict[str, dict[str, Any]],
        output_payload: dict[str, dict[str, Any]],
        cache: dict[str, dict[str, Any]],
        step_lookup: dict[str, Any],
    ) -> dict[str, Any]:
        resolved_inputs, resolved_controllers = self._resolve_inputs(
            step, outputs_by_step, step_lookup
        )
        port_outputs = self._resolve_port_outputs(
            step,
            resolved_inputs,
            resolved_controllers,
            cache,
            job_id=job_id,
            workflow_id=workflow_id,
            execution_session_id=execution_session_id,
        )
        outputs_by_step[step.step_id] = port_outputs
        result = self._extract_terminal_output(
            step.node_type, resolved_inputs, port_outputs
        )
        if result is not None:
            output_payload[step.node_id] = result
            job_manager.update_result(job_id, {"outputs": dict(output_payload)})
        return self._redact_output_state(
            {
                "inputs": self._json_safe(resolved_inputs),
                "ports": self._json_safe(port_outputs),
            }
        )

    # -------------------------------------------------------------------------
    def _resolve_port_outputs(
        self,
        step: Any,
        resolved_inputs: dict[str, Any],
        resolved_controllers: dict[str, Any],
        cache: dict[str, dict[str, Any]],
        *,
        job_id: str,
        workflow_id: str | None,
        execution_session_id: str | None,
    ) -> dict[str, Any]:
        cache_key = (
            self._build_cache_key(step, resolved_inputs, resolved_controllers)
            if step.cacheable
            else None
        )
        if cache_key is not None and cache_key in cache:
            return cache[cache_key]

        port_outputs = node_registry.execute(
            step.node_type,
            step.node_version,
            step.parameters,
            resolved_inputs,
            resolved_controllers,
            context={
                "run_id": job_id,
                "workflow_id": workflow_id or "",
                "execution_session_id": execution_session_id or "",
                "node_id": step.node_id,
            },
        )
        if cache_key is not None:
            cache[cache_key] = port_outputs
        return port_outputs

    # -------------------------------------------------------------------------
    def _complete_step(
        self,
        job_id: str,
        step_id: str,
        output_state_public: dict[str, Any],
        progress: float,
    ) -> None:
        self._set_step_state(
            job_id,
            step_id,
            status="completed",
            completed_at=datetime.now(timezone.utc),
            output=output_state_public,
        )
        execution_run_repository.update_run(job_id, progress=progress)
        job_manager.update_progress(job_id, progress)
        execution_event_service.publish(
            run_id=job_id,
            event_type="execution.step.completed",
            step_id=step_id,
            request_id=self._request_id_for_run(job_id),
            payload={"output": output_state_public, "progress": progress},
        )

    # -------------------------------------------------------------------------
    def _fail_step(self, job_id: str, step_id: str, message: str) -> None:
        self._set_step_state(
            job_id,
            step_id,
            status="failed",
            completed_at=datetime.now(timezone.utc),
            error=message,
        )
        execution_run_repository.update_run(job_id, status="failed", error=message)
        release_run_tool_resources(job_id)
        execution_event_service.publish(
            run_id=job_id,
            event_type="execution.step.failed",
            step_id=step_id,
            request_id=self._request_id_for_run(job_id),
            payload={"error": message},
        )
        execution_event_service.publish(
            run_id=job_id,
            event_type="execution.failed",
            request_id=self._request_id_for_run(job_id),
            payload={"error": message},
        )

    # -------------------------------------------------------------------------
    def _request_id_for_run(self, run_id: str) -> str | None:
        run = execution_run_repository.get_run(run_id)
        return run.request_id if run is not None else None

    # -------------------------------------------------------------------------
    def _resolve_inputs(
        self,
        step,
        outputs_by_step: dict[str, dict[str, Any]],
        step_lookup: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        manifest = node_registry.get(step.node_type, step.node_version)
        manifests_by_input = {
            port.name: port for port in (manifest.inputs if manifest else [])
        }
        manifests_by_controller = {
            port.name: port for port in (manifest.controllers if manifest else [])
        }
        resolved_inputs: dict[str, Any] = {}
        resolved_controllers: dict[str, Any] = {}

        for binding in step.bindings:
            binding_is_controller = binding.binding_type == "controller"
            value = self._resolve_binding_value(
                binding, binding_is_controller, outputs_by_step
            )
            target_manifest_map, target_values = self._resolve_binding_target(
                binding_is_controller,
                manifests_by_input,
                manifests_by_controller,
                resolved_inputs,
                resolved_controllers,
            )
            self._assign_binding_value(
                binding.input_name, value, target_manifest_map, target_values
            )

        return resolved_inputs, resolved_controllers

    # -------------------------------------------------------------------------
    def _resolve_binding_value(
        self,
        binding: Any,
        binding_is_controller: bool,
        outputs_by_step: dict[str, dict[str, Any]],
    ) -> Any:
        source_ports = outputs_by_step.get(binding.source_node_id, {})
        value = source_ports.get(binding.source_output, self.SKIP_SENTINEL)
        if not binding_is_controller:
            return self._publish_named_output(value)
        return value

    # -------------------------------------------------------------------------
    def _should_skip_step(
        self, step: Any, outputs_by_step: dict[str, dict[str, Any]]
    ) -> bool:
        input_bindings = [
            binding for binding in step.bindings if binding.binding_type != "controller"
        ]
        if not input_bindings:
            return False
        values = [
            outputs_by_step.get(binding.source_node_id, {}).get(
                binding.source_output, self.SKIP_SENTINEL
            )
            for binding in input_bindings
        ]
        return all(self._is_skip_value(value) for value in values)

    # -------------------------------------------------------------------------
    def _is_skip_value(self, value: Any) -> bool:
        return value == self.SKIP_SENTINEL or value is None

    # -------------------------------------------------------------------------
    def _skip_step(self, job_id: str, step_id: str) -> None:
        self._set_step_state(
            job_id,
            step_id,
            status="skipped",
            completed_at=datetime.now(timezone.utc),
            blocked_reason="All bound inputs were skipped or missing",
        )

    # -------------------------------------------------------------------------
    def _is_pause_output(self, outputs: dict[str, Any]) -> bool:
        return bool(outputs.get("paused"))

    # -------------------------------------------------------------------------
    def _pause_run(
        self,
        job_id: str,
        step: Any,
        outputs: dict[str, Any],
        output_state: dict[str, Any],
    ) -> None:
        resume_token = secrets.token_urlsafe(32)
        expected_schema = outputs.get("expected_reviewed_payload_schema")
        if not isinstance(expected_schema, dict):
            expected_schema = {"type": "object"}
        checkpoint = PauseCheckpoint(
            node_id=step.node_id,
            step_id=step.step_id,
            resume_token=resume_token,
            pause_payload=outputs.get("pause_payload") or {},
            expected_reviewed_payload_schema=expected_schema,
        )
        execution_run_repository.pause_run(
            job_id,
            step.step_id,
            checkpoint,
            output_state,
        )
        execution_event_service.publish(
            run_id=job_id,
            event_type="execution.paused",
            request_id=self._request_id_for_run(job_id),
            step_id=step.step_id,
            payload={
                "node_id": step.node_id,
                "pause_payload": outputs.get("pause_payload") or {},
            },
        )

    # -------------------------------------------------------------------------
    def _publish_named_output(self, value: Any) -> Any:
        json_fields = extract_top_level_json_fields(value)
        return json_fields if json_fields else value

    # -------------------------------------------------------------------------
    def _resolve_binding_target(
        self,
        binding_is_controller: bool,
        manifests_by_input: dict[str, Any],
        manifests_by_controller: dict[str, Any],
        resolved_inputs: dict[str, Any],
        resolved_controllers: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        if binding_is_controller:
            return manifests_by_controller, resolved_controllers
        return manifests_by_input, resolved_inputs

    # -------------------------------------------------------------------------
    def _assign_binding_value(
        self,
        input_name: str,
        value: Any,
        target_manifest_map: dict[str, Any],
        target_values: dict[str, Any],
    ) -> None:
        if input_name not in target_values:
            target_port = target_manifest_map.get(input_name)
            target_values[input_name] = (
                [value] if target_port and target_port.accepts_multiple else value
            )
            return

        current = target_values[input_name]
        if isinstance(current, list):
            current.append(value)
            return
        target_values[input_name] = value

    # -------------------------------------------------------------------------
    def _json_safe(self, value: Any) -> Any:
        return json.loads(json.dumps(value, default=str))

    # -------------------------------------------------------------------------
    def _build_cache_key(
        self,
        step,
        resolved_inputs: dict[str, Any],
        resolved_controllers: dict[str, Any],
    ) -> str:
        payload = json.dumps(
            {
                "node_type": step.node_type,
                "node_version": step.node_version,
                "parameters": self._json_safe(step.parameters),
                "inputs": self._json_safe(resolved_inputs),
                "controllers": self._json_safe(resolved_controllers),
            },
            sort_keys=True,
            default=str,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    # -------------------------------------------------------------------------
    def _extract_terminal_output(
        self,
        node_type: str,
        resolved_inputs: dict[str, Any],
        port_outputs: dict[str, Any],
    ) -> dict[str, Any] | None:
        if node_type == "TEXT_OUTPUT":
            return {
                "text": str(port_outputs.get("result", resolved_inputs.get("text", "")))
            }
        if node_type == "IMAGE_OUTPUT":
            image = port_outputs.get("result", resolved_inputs.get("image"))
            return {"image": image}
        if node_type == "JSON_OUTPUT":
            raw_value = port_outputs.get("result", resolved_inputs.get("value"))
            if isinstance(raw_value, str):
                trimmed = raw_value.strip()
                if not trimmed:
                    return {"json": ""}
                try:
                    parsed = json.loads(trimmed)
                    if isinstance(parsed, dict):
                        return {"json": parsed, **parsed}
                    return {"json": parsed}
                except json.JSONDecodeError:
                    return {"json": raw_value}
            if isinstance(raw_value, dict):
                return {"json": raw_value, **raw_value}
            return {"json": raw_value}
        return None

    # -------------------------------------------------------------------------
    def _set_step_state(self, run_id: str, step_id: str, **updates: Any) -> None:
        execution_run_repository.update_step(run_id, step_id, **updates)

    # -------------------------------------------------------------------------
    def _redact_output_state(self, output_state: dict[str, Any]) -> dict[str, Any]:
        redacted = redact_sensitive_payload(output_state)
        if isinstance(redacted, dict):
            return redacted
        return {"output": redacted}


execution_service = ExecutionService()
