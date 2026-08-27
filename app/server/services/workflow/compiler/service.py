from __future__ import annotations

from collections import defaultdict, deque
from uuid import uuid4

from server.contracts.execution import (
    CompiledExecutionPlan,
    ExecutionBinding,
    ExecutionStepPlan,
)
from server.contracts.workflow_model import (
    CompilerDiagnostic,
    CompileWorkflowResponse,
    WorkflowConnection,
    WorkflowDefinition,
)
from server.services.workflow.nodes import node_registry
from server.services.workflow.provider import provider_service
from server.services.workflow.vector_stores import get_vector_store_adapter
from server.services.workflow.vector_stores.base import (
    validate_vector_request_capabilities,
)


MODEL_NODE_TYPES = {"LLM_CHAT", "LLM_STRUCTURED"}
STRUCTURED_NODE_TYPES = {"LLM_STRUCTURED"}
CHAT_NODE_TYPES = {"CHAT_INPUT"}

###############################################################################
def _resolve_provider(parameters: dict[str, object], default: str = "ollama") -> str:
    provider = str(parameters.get("provider", default)).strip().lower()
    return provider or default

###############################################################################
def _binding_sort_key(connection: WorkflowConnection) -> tuple[str, str, str]:
    target_name = connection.to_input or connection.to_controller or ""
    source_name = connection.from_output or connection.from_controller or ""
    return (target_name, connection.from_node, source_name)

###############################################################################
class CompilerService:

    # -------------------------------------------------------------------------
    def _active_definition(
        self, definition: WorkflowDefinition
    ) -> tuple[WorkflowDefinition, list[str]]:
        skipped_node_ids = [node.node_id for node in definition.nodes if node.skipped]
        if not skipped_node_ids:
            return definition, []

        active_node_ids = {
            node.node_id for node in definition.nodes if not node.skipped
        }
        active_definition = definition.model_copy(
            update={
                "nodes": [
                    node for node in definition.nodes if node.node_id in active_node_ids
                ],
                "connections": [
                    connection
                    for connection in definition.connections
                    if connection.from_node in active_node_ids
                    and connection.to_node in active_node_ids
                ],
            }
        )
        return active_definition, skipped_node_ids

    # -------------------------------------------------------------------------
    def compile(
        self,
        definition: WorkflowDefinition,
        *,
        require_access_keys: bool = True,
    ) -> CompileWorkflowResponse:
        active_definition, skipped_node_ids = self._active_definition(definition)
        effective_definition = active_definition

        diagnostics, validated_parameters = self._collect_diagnostics(
            effective_definition,
            require_access_keys=require_access_keys,
        )
        chat_terminal_outputs = self._collect_chat_terminal_outputs(
            effective_definition, diagnostics
        )
        if any(diagnostic.level == "error" for diagnostic in diagnostics):
            return CompileWorkflowResponse(
                valid=False, diagnostics=diagnostics, plan=None
            )

        ordered_node_ids = self._topological_order(effective_definition)
        incoming: dict[str, list[WorkflowConnection]] = defaultdict(list)
        for connection in effective_definition.connections:
            incoming[connection.to_node].append(connection)

        steps: list[ExecutionStepPlan] = []
        for node_id in ordered_node_ids:
            node = next(
                item for item in effective_definition.nodes if item.node_id == node_id
            )
            manifest = node_registry.get(node.node_type, node.node_version)
            if manifest is None:
                continue
            sorted_connections = sorted(
                incoming.get(node.node_id, []), key=_binding_sort_key
            )
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
                    timeout_ms=node.timeout_ms,
                    retries=node.retries,
                    cacheable=manifest.runtime.cacheable,
                    side_effecting=manifest.runtime.side_effecting,
                    destructive=manifest.runtime.destructive,
                    idempotent=manifest.runtime.idempotent,
                )
            )

        plan_metadata: dict[str, object] = {
            "schema_version": definition.schema_version,
            **definition.metadata,
        }
        if skipped_node_ids:
            plan_metadata["skipped_node_ids"] = skipped_node_ids
        if chat_terminal_outputs:
            plan_metadata["chat_terminal_outputs"] = chat_terminal_outputs

        return CompileWorkflowResponse(
            valid=True,
            diagnostics=diagnostics,
            plan=CompiledExecutionPlan(
                plan_id=f"plan_{uuid4().hex[:12]}",
                step_order=[step.step_id for step in steps],
                steps=steps,
                metadata=plan_metadata,
            ),
        )

    # -------------------------------------------------------------------------
    def _collect_chat_terminal_outputs(
        self,
        definition: WorkflowDefinition,
        diagnostics: list[CompilerDiagnostic],
    ) -> dict[str, str]:
        node_by_id = {node.node_id: node for node in definition.nodes}
        terminal_node_ids = {
            node.node_id
            for node in definition.nodes
            if (
                (manifest := node_registry.get(node.node_type, node.node_version))
                is not None
                and manifest.category == "output"
            )
        }
        adjacency: dict[str, list[str]] = defaultdict(list)
        for connection in definition.connections:
            if connection.connection_type != "data":
                continue
            if connection.from_node in node_by_id and connection.to_node in node_by_id:
                adjacency[connection.from_node].append(connection.to_node)

        terminal_outputs: dict[str, str] = {}
        for chat_node in definition.nodes:
            if chat_node.node_type not in CHAT_NODE_TYPES:
                continue
            reachable: set[str] = set()
            queue = deque([chat_node.node_id])
            while queue:
                current = queue.popleft()
                for target in adjacency.get(current, []):
                    if target in reachable:
                        continue
                    reachable.add(target)
                    queue.append(target)

            reachable_terminals = sorted(reachable.intersection(terminal_node_ids))
            if len(reachable_terminals) != 1:
                count_label = "none" if not reachable_terminals else str(len(reachable_terminals))
                diagnostics.append(
                    CompilerDiagnostic(
                        code="chat_terminal_output_count",
                        level="error",
                        message=(
                            f"Chat node '{chat_node.node_id}' must reach exactly one "
                            f"terminal output; found {count_label}."
                        ),
                        node_id=chat_node.node_id,
                    )
                )
                continue
            terminal_outputs[chat_node.node_id] = reachable_terminals[0]

        return terminal_outputs

    # -------------------------------------------------------------------------
    def _collect_diagnostics(
        self,
        definition: WorkflowDefinition,
        *,
        require_access_keys: bool,
    ) -> tuple[list[CompilerDiagnostic], dict[str, dict[str, object]]]:
        diagnostics: list[CompilerDiagnostic] = []
        validated_parameters_by_node: dict[str, dict[str, object]] = {}
        node_ids_seen: set[str] = set()
        node_by_id = {node.node_id: node for node in definition.nodes}
        connection_keys: set[tuple[str, str, str, str, str]] = set()
        inbound_counts: dict[tuple[str, str], int] = defaultdict(int)
        inbound_by_node_input: dict[str, dict[str, int]] = defaultdict(
            lambda: defaultdict(int)
        )
        model_binding_by_node: dict[str, WorkflowConnection] = {}
        similarity_store_binding_by_node: dict[str, WorkflowConnection] = {}

        if "global_nodes" in definition.metadata:
            diagnostics.append(
                CompilerDiagnostic(
                    code="unsupported_global_connector_metadata",
                    message=(
                        "global_nodes metadata is unsupported; connect provider, "
                        "memory, and store nodes with typed controller edges"
                    ),
                )
            )

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

            if node.timeout_ms is not None and node.timeout_ms <= 0:
                diagnostics.append(
                    CompilerDiagnostic(
                        code="invalid_timeout",
                        message=f"Node '{node.node_id}' timeout_ms must be greater than zero",
                        node_id=node.node_id,
                    )
                )
            if node.retries < 0:
                diagnostics.append(
                    CompilerDiagnostic(
                        code="invalid_retries",
                        message=f"Node '{node.node_id}' retries must be zero or greater",
                        node_id=node.node_id,
                    )
                )
            elif (
                node.retries > 0
                and manifest.runtime.side_effecting
                and not manifest.runtime.idempotent
            ):
                diagnostics.append(
                    CompilerDiagnostic(
                        code="unsafe_side_effect_retry",
                        message=(
                            f"Node '{node.node_id}' is side-effecting and cannot be "
                            "retried without an idempotency contract"
                        ),
                        node_id=node.node_id,
                    )
                )

            for parameter in manifest.parameters:
                required = bool(parameter.constraints.get("required"))
                if (
                    required
                    and parameter.name not in node.parameters
                    and parameter.default is None
                ):
                    diagnostics.append(
                        CompilerDiagnostic(
                            code="missing_parameter",
                            message=f"Node '{node.node_id}' is missing required parameter '{parameter.name}'",
                            node_id=node.node_id,
                        )
                    )

            try:
                validated_parameters_by_node[node.node_id] = (
                    node_registry.validate_parameters(
                        node.node_type,
                        node.node_version,
                        node.parameters,
                    )
                )
            except ValueError as exc:
                diagnostic_code = "invalid_parameter"
                if node.node_type in STRUCTURED_NODE_TYPES and "response_schema" in str(
                    exc
                ):
                    diagnostic_code = "invalid_response_schema"
                diagnostics.append(
                    CompilerDiagnostic(
                        code=diagnostic_code,
                        message=str(exc),
                        node_id=node.node_id,
                    )
                )

            if node.node_type == "VECTOR_STORE":
                parameters = validated_parameters_by_node.get(
                    node.node_id, node.parameters
                )
                backend = str(parameters.get("provider") or "lancedb").strip().lower()
                try:
                    capabilities = get_vector_store_adapter(
                        backend
                    ).describe_capabilities()
                    validate_vector_request_capabilities(
                        capabilities,
                        metric=str(parameters.get("distance_metric") or "cosine"),
                        namespace=str(parameters.get("namespace") or ""),
                        create_keyword_index=bool(
                            parameters.get("create_keyword_index", False)
                        ),
                    )
                except ValueError as exc:
                    diagnostics.append(
                        CompilerDiagnostic(
                            code="unsupported_vector_capability",
                            message=str(exc),
                            node_id=node.node_id,
                        )
                    )

        for connection in definition.connections:
            source_name = (
                connection.from_output
                if connection.connection_type == "data"
                else connection.from_controller
            )
            target_name = (
                connection.to_input
                if connection.connection_type == "data"
                else connection.to_controller
            )
            connection_key = (
                connection.connection_type,
                connection.from_node,
                source_name or "",
                connection.to_node,
                target_name or "",
            )
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

            source_manifest = node_registry.get(
                source_node.node_type, source_node.node_version
            )
            target_manifest = node_registry.get(
                target_node.node_type, target_node.node_version
            )
            if source_manifest is None or target_manifest is None:
                continue

            if connection.connection_type == "controller":
                source_port = next(
                    (
                        port
                        for port in source_manifest.controllers
                        if port.name == (connection.from_controller or "")
                    ),
                    None,
                )
                target_port = next(
                    (
                        port
                        for port in target_manifest.controllers
                        if port.name == (connection.to_controller or "")
                    ),
                    None,
                )
                source_label = "controller"
                target_label = "controller"
                source_name = connection.from_controller or ""
                target_name = connection.to_controller or ""
            else:
                source_port = next(
                    (
                        port
                        for port in source_manifest.outputs
                        if port.name == (connection.from_output or "")
                    ),
                    None,
                )
                target_port = next(
                    (
                        port
                        for port in target_manifest.inputs
                        if port.name == (connection.to_input or "")
                    ),
                    None,
                )
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
            if connection.connection_type == "controller" and target_name == "store":
                similarity_store_binding_by_node.setdefault(
                    connection.to_node, connection
                )
            if (
                inbound_counts[(connection.to_node, target_name)] > 1
                and not target_port.accepts_multiple
            ):
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
                if (
                    controller.required
                    and inbound_counts[(node.node_id, controller.name)] == 0
                ):
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
                        CompilerDiagnostic(
                            code="invalid_model_selection",
                            message=str(exc),
                            node_id=node.node_id,
                        )
                    )
                continue

            if node.node_type in MODEL_NODE_TYPES:
                user_prompt_count = inbound_by_node_input[node.node_id].get(
                    "user_prompt", 0
                )
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
                        source_parameters = validated_parameters_by_node.get(
                            source_node.node_id, source_node.parameters
                        )
                        provider = _resolve_provider(source_parameters)
                        model_name = str(
                            source_parameters.get("model_name") or ""
                        ).strip()

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
                        require_access_key=require_access_keys,
                    )
                except ValueError as exc:
                    diagnostics.append(
                        CompilerDiagnostic(
                            code="provider_capability_error",
                            message=str(exc),
                            node_id=node.node_id,
                        )
                    )

            if node.node_type == "SIMILARITY_SEARCH":
                store_binding = similarity_store_binding_by_node.get(node.node_id)
                if store_binding is not None:
                    source_node = node_by_id.get(store_binding.from_node)
                    if (
                        source_node is not None
                        and source_node.node_type == "VECTOR_STORE"
                    ):
                        source_parameters = validated_parameters_by_node.get(
                            source_node.node_id, source_node.parameters
                        )
                        backend = (
                            str(source_parameters.get("provider") or "lancedb")
                            .strip()
                            .lower()
                        )

                        similarity_metric = (
                            str(parameters.get("similarity_strategy") or "cosine")
                            .strip()
                            .lower()
                        )
                        if similarity_metric == "euclidean":
                            similarity_metric = "l2"
                        store_metric = (
                            str(source_parameters.get("distance_metric") or "cosine")
                            .strip()
                            .lower()
                        )
                        if store_metric == "euclidean":
                            store_metric = "l2"
                        if similarity_metric != store_metric:
                            diagnostics.append(
                                CompilerDiagnostic(
                                    code="similarity_metric_mismatch",
                                    message=(
                                        f"Node '{node.node_id}' similarity_strategy '{similarity_metric}' does not match "
                                        f"connected VECTOR_STORE distance_metric '{store_metric}'."
                                    ),
                                    node_id=node.node_id,
                                )
                            )

                        search_mode = (
                            str(parameters.get("search_mode") or "vector")
                            .strip()
                            .lower()
                        )
                        search_engine = (
                            str(parameters.get("search_engine") or "native")
                            .strip()
                            .lower()
                        )
                        filter_spec = parameters.get("metadata_filter")
                        if not isinstance(filter_spec, dict):
                            filter_spec = None
                        keyword_query = str(
                            parameters.get("keyword_query") or ""
                        ).strip() or None
                        try:
                            capabilities = get_vector_store_adapter(
                                backend
                            ).describe_capabilities()
                        except ValueError as exc:
                            diagnostics.append(
                                CompilerDiagnostic(
                                    code="unsupported_vector_backend",
                                    message=str(exc),
                                    node_id=node.node_id,
                                )
                            )
                            continue

                        capability_checks = (
                            (
                                "unsupported_similarity_metric",
                                {"metric": similarity_metric},
                            ),
                            (
                                "unsupported_similarity_mode",
                                {"search_mode": search_mode},
                            ),
                            (
                                "unsupported_similarity_engine",
                                {"search_engine": search_engine},
                            ),
                            (
                                "unsupported_similarity_namespace",
                                {
                                    "namespace": str(
                                        source_parameters.get("namespace") or ""
                                    )
                                },
                            ),
                            (
                                "unsupported_similarity_filter",
                                {
                                    "filter_spec": filter_spec,
                                    "keyword_query": keyword_query,
                                    "search_mode": search_mode,
                                },
                            ),
                        )
                        for diagnostic_code, check_kwargs in capability_checks:
                            try:
                                validate_vector_request_capabilities(
                                    capabilities, **check_kwargs
                                )
                            except ValueError as exc:
                                diagnostics.append(
                                    CompilerDiagnostic(
                                        code=diagnostic_code,
                                        message=str(exc),
                                        node_id=node.node_id,
                                    )
                                )

        try:
            self._topological_order(definition)
        except ValueError as exc:
            diagnostics.append(CompilerDiagnostic(code="graph_cycle", message=str(exc)))

        diagnostics.extend(self._collect_graph_diagnostics(definition))

        return diagnostics, validated_parameters_by_node

    # -------------------------------------------------------------------------
    def _collect_graph_diagnostics(
        self, definition: WorkflowDefinition
    ) -> list[CompilerDiagnostic]:
        diagnostics: list[CompilerDiagnostic] = []
        node_by_id = {node.node_id: node for node in definition.nodes}
        manifests = {
            node.node_id: node_registry.get(node.node_type, node.node_version)
            for node in definition.nodes
        }
        connected_node_ids: set[str] = set()
        undirected_adjacency: dict[str, set[str]] = defaultdict(set)
        reverse_adjacency: dict[str, set[str]] = defaultdict(set)

        for connection in definition.connections:
            if (
                connection.from_node not in node_by_id
                or connection.to_node not in node_by_id
            ):
                continue
            connected_node_ids.update((connection.from_node, connection.to_node))
            undirected_adjacency[connection.from_node].add(connection.to_node)
            undirected_adjacency[connection.to_node].add(connection.from_node)
            reverse_adjacency[connection.to_node].add(connection.from_node)

            source_node = node_by_id[connection.from_node]
            if (
                connection.connection_type == "data"
                and source_node.node_type == "IF_TEXT_CONTAINS"
                and connection.from_output in {"true", "false"}
            ):
                diagnostics.append(
                    CompilerDiagnostic(
                        code="conditional_output_connection",
                        level="warning",
                        message=(
                            f"Connection from conditional output "
                            f"'{connection.from_node}.{connection.from_output}' "
                            "may not produce a value at runtime"
                        ),
                        connection=connection,
                    )
                )

        terminal_node_ids = {
            node_id
            for node_id, manifest in manifests.items()
            if manifest is not None and manifest.category == "output"
        }
        if definition.nodes and not terminal_node_ids:
            diagnostics.append(
                CompilerDiagnostic(
                    code="missing_terminal_output",
                    level="warning",
                    message="Workflow has no terminal output node",
                )
            )

        components: list[list[str]] = []
        unvisited = set(node_by_id)
        while unvisited:
            root = min(unvisited)
            queue = deque([root])
            unvisited.remove(root)
            component: list[str] = []
            while queue:
                current = queue.popleft()
                component.append(current)
                for neighbor in sorted(undirected_adjacency[current]):
                    if neighbor in unvisited:
                        unvisited.remove(neighbor)
                        queue.append(neighbor)
            components.append(sorted(component))

        if len(definition.nodes) > 1 and len(components) > 1:
            for component in components:
                identifiers = ", ".join(component)
                diagnostics.append(
                    CompilerDiagnostic(
                        code="disconnected_execution_component",
                        message=(
                            "Workflow contains an independent executable component "
                            f"with nodes: {identifiers}"
                        ),
                        node_id=component[0],
                    )
                )

        contributing_node_ids = set(terminal_node_ids)
        queue = deque(sorted(terminal_node_ids))
        while queue:
            current = queue.popleft()
            for source in sorted(reverse_adjacency[current]):
                if source in contributing_node_ids:
                    continue
                contributing_node_ids.add(source)
                queue.append(source)

        for node in definition.nodes:
            manifest = manifests[node.node_id]
            if manifest is None:
                continue
            if node.node_id not in connected_node_ids:
                code = (
                    "disconnected_side_effecting_node"
                    if manifest.runtime.side_effecting
                    else "disconnected_node"
                )
                diagnostics.append(
                    CompilerDiagnostic(
                        code=code,
                        level="error"
                        if manifest.runtime.side_effecting
                        else "warning",
                        message=f"Node '{node.node_id}' is disconnected",
                        node_id=node.node_id,
                    )
                )
            if (
                terminal_node_ids
                and node.node_id not in contributing_node_ids
                and not manifest.runtime.side_effecting
            ):
                diagnostics.append(
                    CompilerDiagnostic(
                        code="node_not_contributing_to_output",
                        level="warning",
                        message=(
                            f"Node '{node.node_id}' does not contribute to any "
                            "terminal output"
                        ),
                        node_id=node.node_id,
                    )
                )
        return diagnostics

    # -------------------------------------------------------------------------
    def _topological_order(self, definition: WorkflowDefinition) -> list[str]:
        node_ids = [node.node_id for node in definition.nodes]
        indegree = {node_id: 0 for node_id in node_ids}
        adjacency: dict[str, list[str]] = defaultdict(list)

        for connection in definition.connections:
            if (
                connection.from_node not in indegree
                or connection.to_node not in indegree
            ):
                continue
            adjacency[connection.from_node].append(connection.to_node)
            indegree[connection.to_node] += 1

        queue = deque(
            sorted(node_id for node_id, count in indegree.items() if count == 0)
        )
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
