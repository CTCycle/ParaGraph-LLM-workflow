from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from ParaGraph.server.common.security import redact_sensitive_payload
from ParaGraph.server.domain.execution import CompiledExecutionPlan, ExecutionRunState, ExecutionStepState
from ParaGraph.server.repositories.workflow import execution_run_repository
from ParaGraph.server.services.jobs import job_manager
from ParaGraph.server.services.runtime.events import execution_event_service
from ParaGraph.server.services.workflow.nodes import node_registry


class ExecutionService:
    OUTPUT_NAME_PARAMETER = "__output_name"

    def start_execution(self, plan: CompiledExecutionPlan, workflow_id: str | None = None) -> str:
        return job_manager.start_job(
            job_type="workflow",
            runner=self.execute_plan_job,
            kwargs={"plan": plan, "workflow_id": workflow_id},
        )

    def get_run(self, run_id: str) -> ExecutionRunState | None:
        return execution_run_repository.get_run(run_id)

    def execute_plan_job(self, plan: CompiledExecutionPlan, workflow_id: str | None, job_id: str) -> dict[str, Any]:
        steps_state = [
            ExecutionStepState(step_id=step.step_id, node_id=step.node_id, node_type=step.node_type)
            for step in plan.steps
        ]
        run = ExecutionRunState(
            run_id=job_id,
            workflow_id=workflow_id,
            plan_id=plan.plan_id,
            status="queued",
            steps=steps_state,
        )
        execution_run_repository.create_run(run)
        execution_event_service.publish(run_id=job_id, event_type="execution.queued", payload={"plan_id": plan.plan_id})

        execution_run_repository.update_run(job_id, status="running", progress=0.0)
        execution_event_service.publish(run_id=job_id, event_type="execution.started", payload={"plan_id": plan.plan_id})

        outputs_by_step: dict[str, dict[str, Any]] = {}
        output_payload: dict[str, dict[str, Any]] = {}
        cache: dict[str, dict[str, Any]] = {}
        step_lookup = {step.step_id: step for step in plan.steps}
        total_steps = len(plan.step_order) or 1

        for index, step_id in enumerate(plan.step_order, start=1):
            if job_manager.should_stop(job_id):
                execution_run_repository.update_run(job_id, status="cancelled")
                return {}

            step = step_lookup[step_id]
            self._set_step_state(job_id, step_id, status="running", started_at=datetime.now(timezone.utc))
            execution_event_service.publish(
                run_id=job_id,
                event_type="execution.step.started",
                step_id=step_id,
                payload={"node_type": step.node_type, "node_id": step.node_id},
            )

            try:
                resolved_inputs, resolved_controllers = self._resolve_inputs(step, outputs_by_step, step_lookup)
                cache_key = self._build_cache_key(step, resolved_inputs, resolved_controllers) if step.cacheable else None
                if cache_key is not None and cache_key in cache:
                    port_outputs = cache[cache_key]
                else:
                    port_outputs = node_registry.execute(
                        step.node_type,
                        step.node_version,
                        step.parameters,
                        resolved_inputs,
                        resolved_controllers,
                    )
                    if cache_key is not None:
                        cache[cache_key] = port_outputs

                outputs_by_step[step_id] = port_outputs
                output_state_public = self._redact_output_state(
                    {
                        "inputs": self._json_safe(resolved_inputs),
                        "ports": self._json_safe(port_outputs),
                    }
                )

                result = self._extract_terminal_output(step.node_type, resolved_inputs, port_outputs)
                if result is not None:
                    output_payload[step.node_id] = result
                    job_manager.update_result(job_id, {"outputs": dict(output_payload)})

                computed_progress = (index / total_steps) * 100.0
                progress = computed_progress if index < total_steps else 99.0
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
                    payload={"output": output_state_public, "progress": progress},
                )
            except Exception as exc:  # noqa: BLE001
                message = str(exc)
                self._set_step_state(
                    job_id,
                    step_id,
                    status="failed",
                    completed_at=datetime.now(timezone.utc),
                    error=message,
                )
                execution_run_repository.update_run(job_id, status="failed", error=message)
                execution_event_service.publish(
                    run_id=job_id,
                    event_type="execution.step.failed",
                    step_id=step_id,
                    payload={"error": message},
                )
                execution_event_service.publish(run_id=job_id, event_type="execution.failed", payload={"error": message})
                raise

        execution_run_repository.update_run(job_id, status="completed", outputs=output_payload, progress=100.0)
        execution_event_service.publish(run_id=job_id, event_type="execution.completed", payload={"outputs": output_payload})
        return {"outputs": output_payload}

    def _resolve_inputs(
        self,
        step,
        outputs_by_step: dict[str, dict[str, Any]],
        step_lookup: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        manifest = node_registry.get(step.node_type, step.node_version)
        manifests_by_input = {port.name: port for port in (manifest.inputs if manifest else [])}
        manifests_by_controller = {port.name: port for port in (manifest.controllers if manifest else [])}
        resolved_inputs: dict[str, Any] = {}
        resolved_controllers: dict[str, Any] = {}

        for binding in step.bindings:
            source_ports = outputs_by_step.get(binding.source_node_id, {})
            value = source_ports.get(binding.source_output)
            binding_is_controller = binding.binding_type == "controller"
            source_step = step_lookup.get(binding.source_node_id)
            output_name = self._resolve_output_name(source_step.parameters if source_step is not None else {})
            if not binding_is_controller and output_name:
                value = {output_name: value}
            target_manifest_map = manifests_by_controller if binding_is_controller else manifests_by_input
            target_values = resolved_controllers if binding_is_controller else resolved_inputs

            if binding.input_name not in target_values:
                target_port = target_manifest_map.get(binding.input_name)
                if target_port and target_port.accepts_multiple:
                    target_values[binding.input_name] = [value]
                else:
                    target_values[binding.input_name] = value
                continue

            current = target_values[binding.input_name]
            if isinstance(current, list):
                current.append(value)
            else:
                target_values[binding.input_name] = value

        return resolved_inputs, resolved_controllers

    def _resolve_output_name(self, parameters: dict[str, Any]) -> str | None:
        raw_value = parameters.get(self.OUTPUT_NAME_PARAMETER)
        if not isinstance(raw_value, str):
            return None
        normalized = raw_value.strip()
        return normalized or None

    def _json_safe(self, value: Any) -> Any:
        return json.loads(json.dumps(value, default=str))

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

    def _extract_terminal_output(
        self,
        node_type: str,
        resolved_inputs: dict[str, Any],
        port_outputs: dict[str, Any],
    ) -> dict[str, Any] | None:
        if node_type == "TEXT_OUTPUT":
            return {"text": str(port_outputs.get("result", resolved_inputs.get("text", "")))}
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
                    return {"json": json.loads(trimmed)}
                except json.JSONDecodeError:
                    return {"json": raw_value}
            return {"json": raw_value}
        return None

    def _set_step_state(self, run_id: str, step_id: str, **updates: Any) -> None:
        run = execution_run_repository.get_run(run_id)
        if run is None:
            return
        updated_steps: list[ExecutionStepState] = []
        for step in run.steps:
            if step.step_id != step_id:
                updated_steps.append(step)
                continue
            payload = step.model_dump()
            payload.update(updates)
            updated_steps.append(ExecutionStepState.model_validate(payload))
        execution_run_repository.set_steps(run_id, updated_steps)

    def _redact_output_state(self, output_state: dict[str, Any]) -> dict[str, Any]:
        redacted = redact_sensitive_payload(output_state)
        if isinstance(redacted, dict):
            return redacted
        return {"output": redacted}


execution_service = ExecutionService()
