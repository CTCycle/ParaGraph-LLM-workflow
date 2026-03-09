from __future__ import annotations

from collections import defaultdict, deque
from uuid import uuid4

from ParaGraph.server.entities.execution import CompiledExecutionPlan, ExecutionBinding, ExecutionStepPlan
from ParaGraph.server.entities.workflowmodel import CompilerDiagnostic, CompileWorkflowResponse, WorkflowDefinition
from ParaGraph.server.services.workflow.nodes import node_registry
from ParaGraph.server.services.workflow.provider import provider_service


ALLOWED_CATEGORY_EDGES = {
    ("input", "process"),
    ("process", "process"),
    ("process", "output"),
}

RUNTIME_SUPPORTED_NODE_TYPES = {"Prompt", "LLM", "Output"}


class CompilerService:
    def validate(self, definition: WorkflowDefinition) -> CompileWorkflowResponse:
        diagnostics = self._collect_diagnostics(definition)
        return CompileWorkflowResponse(valid=not diagnostics, diagnostics=diagnostics)

    def compile(self, definition: WorkflowDefinition) -> tuple[CompiledExecutionPlan | None, list[CompilerDiagnostic]]:
        diagnostics = self._collect_diagnostics(definition)
        if diagnostics:
            return None, diagnostics

        ordered_node_ids = self._topological_order(definition)
        incoming = defaultdict(list)
        for edge in definition.edges:
            incoming[edge.target.node_id].append(edge)

        steps: list[ExecutionStepPlan] = []
        for node_id in ordered_node_ids:
            node = next(item for item in definition.nodes if item.node_id == node_id)
            bindings = [
                ExecutionBinding(
                    input_port=edge.target.port,
                    source_step_id=edge.source.node_id,
                    source_output=edge.source.port,
                )
                for edge in sorted(incoming.get(node.node_id, []), key=lambda item: item.edge_id)
            ]
            definition_metadata = node_registry.get(node.node_type)
            step = ExecutionStepPlan(
                step_id=node.node_id,
                node_id=node.node_id,
                node_type=node.node_type,
                config=node.config,
                bindings=bindings,
                retries=1 if definition_metadata and definition_metadata.semantics.retryable else 0,
                cacheable=bool(definition_metadata and definition_metadata.semantics.cacheable),
            )
            steps.append(step)

        plan = CompiledExecutionPlan(
            plan_id=f"plan_{uuid4().hex[:12]}",
            step_order=[step.step_id for step in steps],
            steps=steps,
            metadata={"schema_version": definition.schema_version},
        )
        return plan, []

    def _collect_diagnostics(self, definition: WorkflowDefinition) -> list[CompilerDiagnostic]:
        diagnostics: list[CompilerDiagnostic] = []
        node_ids_seen: set[str] = set()
        edge_ids_seen: set[str] = set()

        node_by_id = {node.node_id: node for node in definition.nodes}

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
            if node_registry.get(node.node_type) is None:
                diagnostics.append(
                    CompilerDiagnostic(
                        code="unknown_node_type",
                        message=f"Unknown node type '{node.node_type}' for node '{node.node_id}'",
                        node_id=node.node_id,
                    )
                )

        for edge in definition.edges:
            if edge.edge_id in edge_ids_seen:
                diagnostics.append(
                    CompilerDiagnostic(
                        code="duplicate_edge_id",
                        message=f"Duplicate edge id: {edge.edge_id}",
                        edge_id=edge.edge_id,
                    )
                )
            edge_ids_seen.add(edge.edge_id)

            source_node = node_by_id.get(edge.source.node_id)
            target_node = node_by_id.get(edge.target.node_id)
            if source_node is None:
                diagnostics.append(
                    CompilerDiagnostic(
                        code="missing_source_node",
                        message=f"Edge '{edge.edge_id}' references missing source node '{edge.source.node_id}'",
                        edge_id=edge.edge_id,
                    )
                )
                continue
            if target_node is None:
                diagnostics.append(
                    CompilerDiagnostic(
                        code="missing_target_node",
                        message=f"Edge '{edge.edge_id}' references missing target node '{edge.target.node_id}'",
                        edge_id=edge.edge_id,
                    )
                )
                continue

            source_def = node_registry.get(source_node.node_type)
            target_def = node_registry.get(target_node.node_type)
            if source_def is None or target_def is None:
                continue

            if source_def.category == "output":
                diagnostics.append(
                    CompilerDiagnostic(
                        code="invalid_output_source",
                        message=f"Node '{source_node.node_id}' is output and cannot have outgoing edges",
                        node_id=source_node.node_id,
                        edge_id=edge.edge_id,
                    )
                )

            category_pair = (source_def.category, target_def.category)
            if category_pair not in ALLOWED_CATEGORY_EDGES:
                diagnostics.append(
                    CompilerDiagnostic(
                        code="invalid_category_flow",
                        message=(
                            f"Invalid category flow '{source_def.category}->{target_def.category}' "
                            f"on edge '{edge.edge_id}'"
                        ),
                        edge_id=edge.edge_id,
                    )
                )

            source_port = next(
                (port for port in source_def.ports if port.direction == "output" and port.handle == edge.source.port),
                None,
            )
            if source_port is None:
                diagnostics.append(
                    CompilerDiagnostic(
                        code="missing_source_port",
                        message=(
                            f"Edge '{edge.edge_id}' references unknown source handle '{edge.source.port}' "
                            f"on node '{source_node.node_id}'"
                        ),
                        edge_id=edge.edge_id,
                    )
                )
                continue

            target_port = next(
                (port for port in target_def.ports if port.direction == "input" and port.handle == edge.target.port),
                None,
            )
            if target_port is None:
                diagnostics.append(
                    CompilerDiagnostic(
                        code="missing_target_port",
                        message=(
                            f"Edge '{edge.edge_id}' references unknown target handle '{edge.target.port}' "
                            f"on node '{target_node.node_id}'"
                        ),
                        edge_id=edge.edge_id,
                    )
                )
                continue

            compatible = (
                source_port.data_type == target_port.data_type
                or source_port.data_type == "any"
                or target_port.data_type == "any"
            )
            if not compatible:
                diagnostics.append(
                    CompilerDiagnostic(
                        code="port_type_mismatch",
                        message=(
                            f"Type mismatch on edge '{edge.edge_id}': "
                            f"{source_port.data_type} -> {target_port.data_type}"
                        ),
                        edge_id=edge.edge_id,
                    )
                )

        try:
            self._topological_order(definition)
        except ValueError as exc:
            diagnostics.append(
                CompilerDiagnostic(
                    code="graph_cycle",
                    message=str(exc),
                )
            )

        connected_node_ids: set[str] = set()
        for edge in definition.edges:
            connected_node_ids.add(edge.source.node_id)
            connected_node_ids.add(edge.target.node_id)
        for node_id in sorted(connected_node_ids):
            node = node_by_id.get(node_id)
            if node is None:
                continue
            if node.node_type not in RUNTIME_SUPPORTED_NODE_TYPES:
                diagnostics.append(
                    CompilerDiagnostic(
                        code="unsupported_runtime_node",
                        message=(
                            f"Node '{node.node_id}' type '{node.node_type}' is connected "
                            "but not supported by the MVP executor"
                        ),
                        node_id=node.node_id,
                    )
                )

        for node in definition.nodes:
            if node.node_type != "LLM":
                continue
            provider = str(node.config.get("provider", "ollama")).lower()
            response_format = str(node.config.get("response_format", "text")).lower()
            structured = response_format == "json"
            try:
                provider_service.assert_capabilities(provider, structured_output=structured)
            except ValueError as exc:
                diagnostics.append(
                    CompilerDiagnostic(
                        code="provider_capability_error",
                        message=str(exc),
                        node_id=node.node_id,
                    )
                )

        return diagnostics

    def _topological_order(self, definition: WorkflowDefinition) -> list[str]:
        node_ids = [node.node_id for node in definition.nodes]
        indegree = {node_id: 0 for node_id in node_ids}
        adjacency: dict[str, list[str]] = defaultdict(list)

        for edge in definition.edges:
            if edge.source.node_id not in indegree or edge.target.node_id not in indegree:
                continue
            adjacency[edge.source.node_id].append(edge.target.node_id)
            indegree[edge.target.node_id] += 1

        queue = deque(sorted(node_id for node_id, count in indegree.items() if count == 0))
        ordered: list[str] = []

        while queue:
            current = queue.popleft()
            ordered.append(current)
            for target in adjacency[current]:
                indegree[target] -= 1
                if indegree[target] == 0:
                    queue.append(target)

        if len(ordered) != len(node_ids):
            raise ValueError("Workflow graph contains a cycle")
        return ordered


compiler_service = CompilerService()