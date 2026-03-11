from __future__ import annotations

import json
from collections import defaultdict, deque
from uuid import uuid4

from ParaGraph.server.entities.execution import CompiledExecutionPlan, ExecutionBinding, ExecutionStepPlan
from ParaGraph.server.entities.workflowmodel import CompilerDiagnostic, CompileWorkflowResponse, WorkflowConnection, WorkflowDefinition
from ParaGraph.server.services.workflow.nodes import node_registry
from ParaGraph.server.services.workflow.provider import provider_service


MODEL_NODE_TYPES = {
    "OLLAMA_LLM_CHAT",
    "CLOUD_LLM_CHAT",
    "HUGGINGFACE_LLM_CHAT",
    "OLLAMA_STRUCTURED_RESPONSE",
    "CLOUD_STRUCTURED_RESPONSE",
    "HUGGINGFACE_STRUCTURED_RESPONSE",
}
STRUCTURED_NODE_TYPES = {
    "OLLAMA_STRUCTURED_RESPONSE",
    "CLOUD_STRUCTURED_RESPONSE",
    "HUGGINGFACE_STRUCTURED_RESPONSE",
}


def _parse_schema_parameter(value) -> dict:
    if isinstance(value, dict):
        schema = value
    elif isinstance(value, str):
        schema = json.loads(value)
    else:
        raise ValueError("response_schema must be a JSON object")
    if not isinstance(schema, dict):
        raise ValueError("response_schema must be a JSON object")
    allowed_keys = {"type", "properties", "required", "items", "additionalProperties", "enum"}
    unsupported = sorted(set(schema) - allowed_keys)
    if unsupported:
        raise ValueError(f"Unsupported JSON Schema keys: {', '.join(unsupported)}")
    return schema


def _resolve_provider(node_type: str, parameters: dict[str, object]) -> str:
    if node_type.startswith("OLLAMA_"):
        return "ollama"
    if node_type.startswith("HUGGINGFACE_"):
        return "huggingface"
    provider = str(parameters.get("provider", "openai")).strip().lower()
    if provider == "anthropic":
        return "claude"
    return provider


class CompilerService:
    def compile(self, definition: WorkflowDefinition) -> CompileWorkflowResponse:
        diagnostics = self._collect_diagnostics(definition)
        if diagnostics:
            return CompileWorkflowResponse(valid=False, diagnostics=diagnostics, plan=None)

        ordered_node_ids = self._topological_order(definition)
        incoming: dict[str, list[WorkflowConnection]] = defaultdict(list)
        for connection in definition.connections:
            incoming[connection.to_node].append(connection)

        steps: list[ExecutionStepPlan] = []
        for node_id in ordered_node_ids:
            node = next(item for item in definition.nodes if item.node_id == node_id)
            manifest = node_registry.get(node.node_type, node.node_version)
            if manifest is None:
                continue
            bindings = [
                ExecutionBinding(
                    input_name=connection.to_input,
                    source_node_id=connection.from_node,
                    source_output=connection.from_output,
                )
                for connection in sorted(
                    incoming.get(node.node_id, []),
                    key=lambda item: (item.to_input, item.from_node, item.from_output),
                )
            ]
            steps.append(
                ExecutionStepPlan(
                    step_id=node.node_id,
                    node_id=node.node_id,
                    node_type=node.node_type,
                    node_version=node.node_version,
                    category=manifest.category,
                    executor_key=manifest.runtime.executor_key,
                    parameters=node.parameters,
                    bindings=bindings,
                    cacheable=manifest.runtime.cacheable,
                )
            )

        return CompileWorkflowResponse(
            valid=True,
            diagnostics=[],
            plan=CompiledExecutionPlan(
                plan_id=f"plan_{uuid4().hex[:12]}",
                step_order=[step.step_id for step in steps],
                steps=steps,
                metadata={"schema_version": definition.schema_version, **definition.metadata},
            ),
        )

    def _collect_diagnostics(self, definition: WorkflowDefinition) -> list[CompilerDiagnostic]:
        diagnostics: list[CompilerDiagnostic] = []
        node_ids_seen: set[str] = set()
        node_by_id = {node.node_id: node for node in definition.nodes}
        connection_keys: set[tuple[str, str, str, str]] = set()
        inbound_counts: dict[tuple[str, str], int] = defaultdict(int)
        inbound_by_node_input: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

        for node in definition.nodes:
            if node.node_id in node_ids_seen:
                diagnostics.append(
                    CompilerDiagnostic(
                        code="duplicate_node_id",
                        message=f"Duplicate node id: {node.node_id}",
                        node_id=node.node_id,
                    )
                )
            node_ids_seen.add(node.node_id)

            manifest = node_registry.get(node.node_type, node.node_version)
            if manifest is None:
                diagnostics.append(
                    CompilerDiagnostic(
                        code="unknown_node_type",
                        message=f"Unknown node type/version '{node.node_type}' v{node.node_version}",
                        node_id=node.node_id,
                    )
                )
                continue

            for parameter in manifest.parameters:
                required = bool(parameter.constraints.get("required"))
                if required and parameter.name not in node.parameters and parameter.default is None:
                    diagnostics.append(
                        CompilerDiagnostic(
                            code="missing_parameter",
                            message=f"Node '{node.node_id}' is missing required parameter '{parameter.name}'",
                            node_id=node.node_id,
                        )
                    )

            if node.node_type in MODEL_NODE_TYPES:
                if node.node_type in STRUCTURED_NODE_TYPES:
                    try:
                        _parse_schema_parameter(node.parameters.get("response_schema"))
                    except (TypeError, ValueError, json.JSONDecodeError) as exc:
                        diagnostics.append(
                            CompilerDiagnostic(
                                code="invalid_response_schema",
                                message=str(exc),
                                node_id=node.node_id,
                            )
                        )

        for connection in definition.connections:
            connection_key = (connection.from_node, connection.from_output, connection.to_node, connection.to_input)
            if connection_key in connection_keys:
                diagnostics.append(
                    CompilerDiagnostic(
                        code="duplicate_connection",
                        message="Duplicate connection detected",
                        connection=connection,
                    )
                )
            connection_keys.add(connection_key)

            source_node = node_by_id.get(connection.from_node)
            target_node = node_by_id.get(connection.to_node)
            if source_node is None:
                diagnostics.append(
                    CompilerDiagnostic(
                        code="missing_source_node",
                        message=f"Connection references missing source node '{connection.from_node}'",
                        connection=connection,
                    )
                )
                continue
            if target_node is None:
                diagnostics.append(
                    CompilerDiagnostic(
                        code="missing_target_node",
                        message=f"Connection references missing target node '{connection.to_node}'",
                        connection=connection,
                    )
                )
                continue
            if connection.from_node == connection.to_node:
                diagnostics.append(
                    CompilerDiagnostic(
                        code="self_loop",
                        message=f"Node '{connection.from_node}' cannot connect to itself",
                        connection=connection,
                    )
                )
                continue

            source_manifest = node_registry.get(source_node.node_type, source_node.node_version)
            target_manifest = node_registry.get(target_node.node_type, target_node.node_version)
            if source_manifest is None or target_manifest is None:
                continue

            source_port = next((port for port in source_manifest.outputs if port.name == connection.from_output), None)
            target_port = next((port for port in target_manifest.inputs if port.name == connection.to_input), None)
            if source_port is None:
                diagnostics.append(
                    CompilerDiagnostic(
                        code="missing_source_port",
                        message=f"Unknown source output '{connection.from_output}' on '{connection.from_node}'",
                        connection=connection,
                    )
                )
                continue
            if target_port is None:
                diagnostics.append(
                    CompilerDiagnostic(
                        code="missing_target_port",
                        message=f"Unknown target input '{connection.to_input}' on '{connection.to_node}'",
                        connection=connection,
                    )
                )
                continue

            compatible = (
                source_port.data_type == target_port.data_type
                or source_port.data_type == "ANY"
                or target_port.data_type == "ANY"
            )
            if not compatible:
                diagnostics.append(
                    CompilerDiagnostic(
                        code="port_type_mismatch",
                        message=(
                            f"Type mismatch on {connection.from_node}.{connection.from_output} -> "
                            f"{connection.to_node}.{connection.to_input}: "
                            f"{source_port.data_type} -> {target_port.data_type}"
                        ),
                        connection=connection,
                    )
                )

            inbound_counts[(connection.to_node, connection.to_input)] += 1
            inbound_by_node_input[connection.to_node][connection.to_input] += 1
            if inbound_counts[(connection.to_node, connection.to_input)] > 1 and not target_port.accepts_multiple:
                diagnostics.append(
                    CompilerDiagnostic(
                        code="input_multiplicity",
                        message=f"Input '{connection.to_input}' on '{connection.to_node}' does not accept multiple connections",
                        connection=connection,
                    )
                )

        for node in definition.nodes:
            manifest = node_registry.get(node.node_type, node.node_version)
            if manifest is None:
                continue
            for port in manifest.inputs:
                if port.required and inbound_counts[(node.node_id, port.name)] == 0:
                    diagnostics.append(
                        CompilerDiagnostic(
                            code="missing_required_input",
                            message=f"Node '{node.node_id}' is missing required input '{port.name}'",
                            node_id=node.node_id,
                        )
                    )

            if node.node_type in MODEL_NODE_TYPES:
                user_prompt_count = inbound_by_node_input[node.node_id].get("user_prompt", 0)
                image_count = inbound_by_node_input[node.node_id].get("image", 0)
                if user_prompt_count == 0 and image_count == 0:
                    diagnostics.append(
                        CompilerDiagnostic(
                            code="missing_model_input",
                            message=f"Node '{node.node_id}' requires a user prompt or image input",
                            node_id=node.node_id,
                        )
                    )

                provider = _resolve_provider(node.node_type, node.parameters)
                model_name = str(node.parameters.get("model_name") or "").strip()
                if model_name:
                    try:
                        provider_service.validate_model_request(
                            provider=provider,
                            model=model_name,
                            structured_output=node.node_type in STRUCTURED_NODE_TYPES,
                            requires_image=image_count > 0,
                            use_reasoning=bool(node.parameters.get("use_reasoning", False)),
                        )
                    except ValueError as exc:
                        diagnostics.append(
                            CompilerDiagnostic(
                                code="provider_capability_error",
                                message=str(exc),
                                node_id=node.node_id,
                            )
                        )
            if node.node_type == "EMBEDDING_MODEL":
                provider = str(node.parameters.get("provider", "ollama")).lower()
                try:
                    provider_service.assert_capabilities(provider, embeddings=True)
                except ValueError as exc:
                    diagnostics.append(
                        CompilerDiagnostic(code="provider_capability_error", message=str(exc), node_id=node.node_id)
                    )

        try:
            self._topological_order(definition)
        except ValueError as exc:
            diagnostics.append(CompilerDiagnostic(code="graph_cycle", message=str(exc)))

        return diagnostics

    def _topological_order(self, definition: WorkflowDefinition) -> list[str]:
        node_ids = [node.node_id for node in definition.nodes]
        indegree = {node_id: 0 for node_id in node_ids}
        adjacency: dict[str, list[str]] = defaultdict(list)

        for connection in definition.connections:
            if connection.from_node not in indegree or connection.to_node not in indegree:
                continue
            adjacency[connection.from_node].append(connection.to_node)
            indegree[connection.to_node] += 1

        queue = deque(sorted(node_id for node_id, count in indegree.items() if count == 0))
        ordered: list[str] = []

        while queue:
            current = queue.popleft()
            ordered.append(current)
            for target in sorted(adjacency[current]):
                indegree[target] -= 1
                if indegree[target] == 0:
                    queue.append(target)

        if len(ordered) != len(node_ids):
            raise ValueError("Workflow graph contains a cycle")
        return ordered


compiler_service = CompilerService()
