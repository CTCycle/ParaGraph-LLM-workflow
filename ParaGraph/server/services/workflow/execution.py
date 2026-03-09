from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ParaGraph.server.repositories.workflow import execution_run_repository
from ParaGraph.server.entities.execution import (
    CompiledExecutionPlan,
    ExecutionRunState,
    ExecutionStepState,
)
from ParaGraph.server.services.jobs import job_manager
from ParaGraph.server.services.runtime.events import execution_event_service
from ParaGraph.server.services.workflow.provider import provider_service


class ExecutionService:
    def start_execution(self, plan: CompiledExecutionPlan, workflow_id: str | None = None) -> str:
        job_id = job_manager.start_job(
            job_type="workflow",
            runner=self.execute_plan_job,
            kwargs={"plan": plan, "workflow_id": workflow_id},
        )
        return job_id

    def get_run(self, run_id: str) -> ExecutionRunState | None:
        return execution_run_repository.get_run(run_id)

    def execute_plan_job(self, plan: CompiledExecutionPlan, workflow_id: str | None, job_id: str) -> dict[str, Any]:
        steps_state = [
            ExecutionStepState(
                step_id=step.step_id,
                node_id=step.node_id,
                node_type=step.node_type,
            )
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

        execution_event_service.publish(
            run_id=job_id,
            event_type="execution.queued",
            payload={"plan_id": plan.plan_id},
        )

        run = execution_run_repository.update_run(job_id, status="running", progress=0.0) or run
        execution_event_service.publish(
            run_id=job_id,
            event_type="execution.started",
            payload={"plan_id": plan.plan_id},
        )

        outputs_by_step: dict[str, dict[str, Any]] = {}
        output_payload: dict[str, dict[str, Any]] = {}

        step_lookup = {step.step_id: step for step in plan.steps}
        total_steps = len(plan.step_order) or 1

        for index, step_id in enumerate(plan.step_order, start=1):
            if job_manager.should_stop(job_id):
                execution_run_repository.update_run(job_id, status="cancelled")
                return {}

            plan_step = step_lookup[step_id]
            self._set_step_state(job_id, step_id, status="running", started_at=datetime.now(timezone.utc))
            execution_event_service.publish(
                run_id=job_id,
                event_type="execution.step.started",
                step_id=step_id,
                payload={"node_type": plan_step.node_type, "node_id": plan_step.node_id},
            )

            try:
                step_output = self._execute_step(plan_step, outputs_by_step)
                outputs_by_step[step_id] = step_output

                if plan_step.node_type == "Output":
                    output_payload[plan_step.node_id] = {"text": str(step_output.get("text", ""))}
                    job_manager.update_result(job_id, {"outputs": dict(output_payload)})

                progress = (index / total_steps) * 100.0
                self._set_step_state(
                    job_id,
                    step_id,
                    status="completed",
                    completed_at=datetime.now(timezone.utc),
                    output=step_output,
                )
                execution_run_repository.update_run(job_id, progress=progress)
                job_manager.update_progress(job_id, progress)

                execution_event_service.publish(
                    run_id=job_id,
                    event_type="execution.step.completed",
                    step_id=step_id,
                    payload={"output": step_output, "progress": progress},
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
                execution_event_service.publish(
                    run_id=job_id,
                    event_type="execution.failed",
                    payload={"error": message},
                )
                raise

        execution_run_repository.update_run(job_id, status="completed", outputs=output_payload, progress=100.0)
        execution_event_service.publish(
            run_id=job_id,
            event_type="execution.completed",
            payload={"outputs": output_payload},
        )
        return {"outputs": output_payload}

    def _execute_step(self, step, outputs_by_step: dict[str, dict[str, Any]]) -> dict[str, Any]:
        config = step.config

        if step.node_type == "Prompt":
            text = str(config.get("text") or config.get("prompt") or "").strip()
            return {"text": text, "ports": {"prompt_out": text}}

        if step.node_type == "LLM":
            incoming_text = self._collect_text_inputs(step.bindings, outputs_by_step)
            if not incoming_text:
                incoming_text = str(config.get("text") or config.get("prompt") or "").strip()
            if not incoming_text:
                raise ValueError(f"LLM node '{step.node_id}' does not have input text")

            provider = str(config.get("provider", "ollama")).lower()
            model = str(config.get("model") or self._default_model(provider))
            system_prompt = str(config.get("system_prompt", "")).strip()
            response_format = str(config.get("response_format") or config.get("format") or "text").lower()
            json_mode = "json" if response_format == "json" else None

            messages: list[dict[str, str]] = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": incoming_text})

            options: dict[str, Any] = {
                "temperature": self._coerce_float(config.get("temperature"), 0.2),
                "max_output_tokens": int(self._coerce_float(config.get("max_tokens"), 512)),
            }

            text = provider_service.chat(
                provider=provider,
                model=model,
                messages=messages,
                response_format=json_mode,
                options=options,
            )
            return {"text": text, "ports": {"response_out": text}}

        if step.node_type == "Output":
            text = self._collect_text_inputs(step.bindings, outputs_by_step)
            return {"text": text, "ports": {"text_in": text}}

        if step.node_type in {"Retrieval", "VectorDB"}:
            query = self._collect_text_inputs(step.bindings, outputs_by_step)
            snippets = [
                {
                    "source": str(config.get("knowledge_source") or config.get("index_name") or "local"),
                    "snippet": f"Placeholder context for query: {query}",
                }
            ]
            return {"text": "\n".join(item["snippet"] for item in snippets), "documents": snippets}

        fallback = str(config.get("text", ""))
        return {"text": fallback}

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

    def _collect_text_inputs(self, bindings, outputs_by_step: dict[str, dict[str, Any]]) -> str:
        collected: list[str] = []
        for binding in bindings:
            source = outputs_by_step.get(binding.source_step_id, {})
            ports = source.get("ports", {})
            value = ports.get(binding.source_output)
            if value is None:
                value = source.get("text")
            if value is None:
                continue
            text = str(value).strip()
            if text:
                collected.append(text)
        return "\n".join(collected).strip()

    def _coerce_float(self, value: Any, default: float) -> float:
        if value is None:
            return default
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def _default_model(self, provider: str) -> str:
        normalized = provider.lower()
        if normalized == "openai":
            return "gpt-4o-mini"
        if normalized == "gemini":
            return "gemini-1.5-flash"
        if normalized == "anthropic":
            return "claude-3-5-sonnet-latest"
        return "llama3.2"


execution_service = ExecutionService()