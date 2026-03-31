from __future__ import annotations

from collections import defaultdict, deque
from uuid import uuid4

from ParaGraph.server.domain.execution import CompiledExecutionPlan, ExecutionBinding, ExecutionStepPlan
from ParaGraph.server.domain.workflowmodel import CompilerDiagnostic, CompileWorkflowResponse, WorkflowConnection, WorkflowDefinition
from ParaGraph.server.services.workflow.nodes import node_registry
from ParaGraph.server.services.workflow.provider import provider_service


MODEL_NODE_TYPES = {"LLM_CHAT", "LLM_STRUCTURED"}
STRUCTURED_NODE_TYPES = {"LLM_STRUCTURED"}
GLOBAL_CONTROLLER_KINDS: dict[str, str] = {
    "MODEL_HANDLE": "model_provider",
    "DATABASE_CONNECTION": "database_provider",
    "VECTOR_STORE_HANDLE": "vector_store",
}


def _resolve_provider(parameters: dict[str, object], default: str = "ollama") -> str:
    provider = str(parameters.get("provider", default)).strip().lower()
    if provider == "anthropic":
        return "claude"
    return provider or default


def _binding_sort_key(connection: WorkflowConnection) -> tuple[str, str, str]:
    target_name = connection.to_input or connection.to_controller or ""
    source_name = connection.from_output or connection.from_controller or ""
    return (target_name, connection.from_node, source_name)


class CompilerService:
    def _active_definition(self, definition: WorkflowDefinition) -> tuple[WorkflowDefinition, list[str]]:
        skipped_node_ids = [node.node_id for node in definition.nodes if node.skipped]
        if not skipped_node_ids:
            return definition, []

        active_node_ids = {node.node_id for node in definition.nodes if not node.skipped}
        active_definition = definition.model_copy(
            update={
                "nodes": [node for node in definition.nodes if node.node_id in active_node_ids],
                "connections": [
                    connection
                    for connection in definition.connections
                    if connection.from_node in active_node_ids and connection.to_node in active_node_ids
                ],
            }
        )
        return active_definition, skipped_node_ids

    def compile(self, definition: WorkflowDefinition) -> CompileWorkflowResponse:
        active_definition, skipped_node_ids = self._active_definition(definition)
        effective_definition = self._inject_global_controller_connections(active_definition)

        diagnostics, validated_parameters = self._collect_diagnostics(effective_definition)
        if diagnostics:
            return CompileWorkflowResponse(valid=False, diagnostics=diagnostics, plan=None)

        ordered_node_ids = self._topological_order(effective_definition)
        incoming: dict[str, list[WorkflowConnection]] = defaultdict(list)
        for connection in effective_definition.connections:
            incoming[connection.to_node].append(connection)

        steps: list[ExecutionStepPlan] = []
        for node_id in ordered_node_ids:
            node = next(item for item in effective_definition.nodes if item.node_id == node_id)
            manifest = node_registry.get(node.node_type, node.node_version)
            if manifest is None:
                continue
            sorted_connections = sorted(incoming.get(node.node_id, []), key=_binding_sort_key)
            bindings: list[ExecutionBinding] = []
            for connection in sorted_connections:
                if connection.connection_type == "controller":
                    bindings.append(
                        ExecutionBinding(
                            binding_type="controller",
                            input_name=connection.to_controller or "",
                            source_node_id=connection.from_node,
                            source_output=connection.from_controller or "",
                        )
                    )
                    continue

                bindings.append(
                    ExecutionBinding(
                        binding_type="input",
                        input_name=connection.to_input or "",
                        source_node_id=connection.from_node,
                        source_output=connection.from_output or "",
                    )
                )
            steps.append(
                ExecutionStepPlan(
                    step_id=node.node_id,
                    node_id=node.node_id,
                    node_type=node.node_type,
                    node_version=node.node_version,
                    category=manifest.category,
                    executor_key=manifest.runtime.executor_key,
                    parameters=validated_parameters.get(node.node_id, node.parameters),
                    bindings=bindings,
                    cacheable=manifest.runtime.cacheable,
                )
            )

        plan_metadata: dict[str, object] = {"schema_version": definition.schema_version, **definition.metadata}
        if skipped_node_ids:
            plan_metadata["skipped_node_ids"] = skipped_node_ids

        return CompileWorkflowResponse(
            valid=True,
            diagnostics=[],
            plan=CompiledExecutionPlan(
                plan_id=f"plan_{uuid4().hex[:12]}",
                step_order=[step.step_id for step in steps],
                steps=steps,
                metadata=plan_metadata,
            ),
        )

    def _inject_global_controller_connections(self, definition: WorkflowDefinition) -> WorkflowDefinition:
        if not definition.nodes:
            return definition

        node_by_id = {node.node_id: node for node in definition.nodes}
        global_node_ids = self._read_global_node_ids(definition, node_by_id)
        if not global_node_ids:
            return definition

        existing_keys: set[tuple[str, str, str, str, str]] = set()
        inbound_controller_counts: dict[tuple[str, str], int] = defaultdict(int)
        for connection in definition.connections:
            if connection.connection_type != "controller":
                continue
            source_name = connection.from_controller or ""
            target_name = connection.to_controller or ""
            existing_keys.add((connection.connection_type, connection.from_node, source_name, connection.to_node, target_name))
            inbound_controller_counts[(connection.to_node, target_name)] += 1

        injected: list[WorkflowConnection] = []
        for node in definition.nodes:
            target_manifest = node_registry.get(node.node_type, node.node_version)
            if target_manifest is None:
                continue

            for controller in target_manifest.controllers:
                if self._controller_scope(controller.scope) == "source":
                    continue
                if inbound_controller_counts[(node.node_id, controller.name)] > 0:
                    continue

                global_kind = GLOBAL_CONTROLLER_KINDS.get(controller.data_type)
                if not global_kind:
                    continue
                global_node_id = global_node_ids.get(global_kind)
                if not global_node_id or global_node_id == node.node_id:
                    continue

                source_node = node_by_id.get(global_node_id)
                if source_node is None:
                    continue
                source_manifest = node_registry.get(source_node.node_type, source_node.node_version)
                if source_manifest is None:
                    continue

                source_controller_name = self._resolve_global_source_controller_name(source_manifest, controller.data_type)
                if source_controller_name is None:
                    continue

                connection_key = ("controller", global_node_id, source_controller_name, node.node_id, controller.name)
                if connection_key in existing_keys:
                    continue
                existing_keys.add(connection_key)
                inbound_controller_counts[(node.node_id, controller.name)] += 1
                injected.append(
                    WorkflowConnection(
                        from_node=global_node_id,
                        to_node=node.node_id,
                        connection_type="controller",
                        from_controller=source_controller_name,
                        to_controller=controller.name,
                    )
                )

        if not injected:
            return definition
        return definition.model_copy(update={"connections": [*definition.connections, *injected]})

    def _resolve_global_source_controller_name(self, source_manifest, target_data_type: str) -> str | None:
        for controller in source_manifest.controllers:
            scope = self._controller_scope(controller.scope)
            if scope == "target":
                continue
            compatible = (
                controller.data_type == target_data_type
                or controller.data_type == "ANY"
                or target_data_type == "ANY"
            )
            if compatible:
                return controller.name
        return None

    def _read_global_node_ids(
        self,
        definition: WorkflowDefinition,
        node_by_id: dict[str, object],
    ) -> dict[str, str]:
        metadata = definition.metadata if isinstance(definition.metadata, dict) else {}
        raw_globals = metadata.get("global_nodes")
        if not isinstance(raw_globals, dict):
            return {}

        normalized: dict[str, str] = {}
        aliases = {
            "model_provider": "model_provider",
            "model": "model_provider",
            "database_provider": "database_provider",
            "database": "database_provider",
            "vector_store": "vector_store",
            "vector_storage": "vector_store",
        }
        for raw_key, raw_node_id in raw_globals.items():
            key = aliases.get(str(raw_key).strip().lower())
            if key is None or not isinstance(raw_node_id, str):
                continue
            node_id = raw_node_id.strip()
            if node_id and node_id in node_by_id:
                normalized[key] = node_id
        return normalized

    @staticmethod
    def _controller_scope(scope: str | None) -> str:
        if scope in {"source", "target", "both"}:
            return scope
        return "target"

    def _collect_diagnostics(self, definition: WorkflowDefinition) -> tuple[list[CompilerDiagnostic], dict[str, dict[str, object]]]:
        diagnostics: list[CompilerDiagnostic] = []
        validated_parameters_by_node: dict[str, dict[str, object]] = {}
        node_ids_seen: set[str] = set()
        node_by_id = {node.node_id: node for node in definition.nodes}
        connection_keys: set[tuple[str, str, str, str, str]] = set()
        inbound_counts: dict[tuple[str, str], int] = defaultdict(int)
        inbound_by_node_input: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        model_binding_by_node: dict[str, WorkflowConnection] = {}

        for node in definition.nodes:
            if node.node_id in node_ids_seen:
                diagnostics.append(
                    CompilerDiagnostic(code="duplicate_node_id", message=f"Duplicate node id: {node.node_id}", node_id=node.node_id)
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

            try:
                validated_parameters_by_node[node.node_id] = node_registry.validate_parameters(
                    node.node_type,
                    node.node_version,
                    node.parameters,
                )
            except ValueError as exc:
                diagnostic_code = "invalid_parameter"
                if node.node_type in STRUCTURED_NODE_TYPES and "response_schema" in str(exc):
                    diagnostic_code = "invalid_response_schema"
                diagnostics.append(
                    CompilerDiagnostic(
                        code=diagnostic_code,
                        message=str(exc),
                        node_id=node.node_id,
                    )
                )

        for connection in definition.connections:
            source_name = connection.from_output if connection.connection_type == "data" else connection.from_controller
            target_name = connection.to_input if connection.connection_type == "data" else connection.to_controller
            connection_key = (connection.connection_type, connection.from_node, source_name or "", connection.to_node, target_name or "")
            if connection_key in connection_keys:
                diagnostics.append(
                    CompilerDiagnostic(code="duplicate_connection", message="Duplicate connection detected", connection=connection)
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

            if connection.connection_type == "controller":
                source_port = next(
                    (port for port in source_manifest.controllers if port.name == (connection.from_controller or "")),
                    None,
                )
                target_port = next(
                    (port for port in target_manifest.controllers if port.name == (connection.to_controller or "")),
                    None,
                )
                source_label = "controller"
                target_label = "controller"
                source_name = connection.from_controller or ""
                target_name = connection.to_controller or ""
            else:
                source_port = next((port for port in source_manifest.outputs if port.name == (connection.from_output or "")), None)
                target_port = next((port for port in target_manifest.inputs if port.name == (connection.to_input or "")), None)
                source_label = "output"
                target_label = "input"
                source_name = connection.from_output or ""
                target_name = connection.to_input or ""

            if source_port is None:
                diagnostics.append(
                    CompilerDiagnostic(
                        code="missing_source_port",
                        message=f"Unknown source {source_label} '{source_name}' on '{connection.from_node}'",
                        connection=connection,
                    )
                )
                continue
            if target_port is None:
                diagnostics.append(
                    CompilerDiagnostic(
                        code="missing_target_port",
                        message=f"Unknown target {target_label} '{target_name}' on '{connection.to_node}'",
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
                            f"Type mismatch on {connection.from_node}.{source_name} -> "
                            f"{connection.to_node}.{target_name}: "
                            f"{source_port.data_type} -> {target_port.data_type}"
                        ),
                        connection=connection,
                    )
                )

            inbound_counts[(connection.to_node, target_name)] += 1
            if connection.connection_type == "data":
                inbound_by_node_input[connection.to_node][target_name] += 1
            if connection.connection_type == "controller" and target_name == "model":
                model_binding_by_node.setdefault(connection.to_node, connection)
            if inbound_counts[(connection.to_node, target_name)] > 1 and not target_port.accepts_multiple:
                diagnostics.append(
                    CompilerDiagnostic(
                        code="input_multiplicity",
                        message=f"{target_label.capitalize()} '{target_name}' on '{connection.to_node}' does not accept multiple connections",
                        connection=connection,
                    )
                )

        for node in definition.nodes:
            manifest = node_registry.get(node.node_type, node.node_version)
            if manifest is None:
                continue
            parameters = validated_parameters_by_node.get(node.node_id, node.parameters)
            for port in manifest.inputs:
                if port.required and inbound_counts[(node.node_id, port.name)] == 0:
                    diagnostics.append(
                        CompilerDiagnostic(
                            code="missing_required_input",
                            message=f"Node '{node.node_id}' is missing required input '{port.name}'",
                            node_id=node.node_id,
                        )
                    )
            for controller in manifest.controllers:
                if controller.required and inbound_counts[(node.node_id, controller.name)] == 0:
                    diagnostics.append(
                        CompilerDiagnostic(
                            code="missing_required_controller",
                            message=f"Node '{node.node_id}' is missing required controller '{controller.name}'",
                            node_id=node.node_id,
                        )
                    )

            if node.node_type == "MODEL_PROVIDER":
                provider = _resolve_provider(parameters)
                model_name = str(parameters.get("model_name") or "").strip()
                if not model_name:
                    diagnostics.append(
                        CompilerDiagnostic(
                            code="missing_model_selection",
                            message=f"Node '{node.node_id}' requires a selected model",
                            node_id=node.node_id,
                        )
                    )
                    continue
                try:
                    provider_service.get_model_metadata(provider, model_name)
                except ValueError as exc:
                    diagnostics.append(
                        CompilerDiagnostic(code="invalid_model_selection", message=str(exc), node_id=node.node_id)
                    )
                continue

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

                provider: str | None = None
                model_name = ""
                model_binding = model_binding_by_node.get(node.node_id)
                if model_binding is not None:
                    source_node = node_by_id.get(model_binding.from_node)
                    if source_node is not None:
                        source_parameters = validated_parameters_by_node.get(source_node.node_id, source_node.parameters)
                        provider = _resolve_provider(source_parameters)
                        model_name = str(source_parameters.get("model_name") or "").strip()

                if not model_name:
                    diagnostics.append(
                        CompilerDiagnostic(
                            code="missing_model_selection",
                            message=f"Node '{node.node_id}' requires a connected model provider node",
                            node_id=node.node_id,
                        )
                    )
                    continue

                try:
                    provider_service.validate_model_request(
                        provider=provider or "ollama",
                        model=model_name,
                        structured_output=node.node_type in STRUCTURED_NODE_TYPES,
                        requires_image=image_count > 0,
                        use_reasoning=bool(parameters.get("use_reasoning", False)),
                    )
                except ValueError as exc:
                    diagnostics.append(
                        CompilerDiagnostic(code="provider_capability_error", message=str(exc), node_id=node.node_id)
                    )

            if node.node_type == "EMBEDDING_MODEL":
                provider = str(parameters.get("provider", "ollama")).lower()
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

        return diagnostics, validated_parameters_by_node

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
