from __future__ import annotations

from typing import Any

from ParaGraph.server.domain.workflow import (
    CatalogResponse,
    ExecuteWorkflowResponse,
    NodeParameterSchema,
    NodePort,
    ValidateWorkflowResponse,
    WorkflowNodeDefinition,
)
from ParaGraph.server.domain.workflowmodel import (
    LegacyWorkflowGraph,
    VisualGraph,
    VisualNodeState,
    WorkflowDefinition,
    WorkflowEdgeSpec,
    WorkflowNodeSpec,
    WorkflowPortReference,
)
from ParaGraph.server.services.workflow.compiler import compiler_service
from ParaGraph.server.services.workflow.nodes import node_registry


LEGACY_NODE_ORDER = ["Prompt", "LLM", "Retrieval", "VectorDB", "Output"]


class LegacyWorkflowAdapterService:
    def legacy_graph_to_workflow(self, graph: LegacyWorkflowGraph) -> tuple[WorkflowDefinition, VisualGraph]:
        definition = WorkflowDefinition(
            schema_version=1,
            nodes=[
                WorkflowNodeSpec(
                    node_id=node.id,
                    node_type=node.type,
                    config=node.params,
                )
                for node in graph.nodes
            ],
            edges=[
                WorkflowEdgeSpec(
                    edge_id=edge.id,
                    source=WorkflowPortReference(node_id=edge.source, port=edge.sourceHandle),
                    target=WorkflowPortReference(node_id=edge.target, port=edge.targetHandle),
                )
                for edge in graph.edges
            ],
            metadata={"source": "legacy_workflow_graph"},
        )
        visual = VisualGraph(
            schema_version=1,
            nodes=[
                VisualNodeState(node_id=node.id, x=node.position.x, y=node.position.y)
                for node in graph.nodes
            ],
        )
        return definition, visual

    def validate_legacy_graph(self, graph: LegacyWorkflowGraph) -> ValidateWorkflowResponse:
        definition, _ = self.legacy_graph_to_workflow(graph)
        result = compiler_service.validate(definition)
        return ValidateWorkflowResponse(
            valid=result.valid,
            errors=[diagnostic.message for diagnostic in result.diagnostics],
        )

    def build_legacy_catalog(self) -> CatalogResponse:
        by_type = {item.type: item for item in node_registry.list()}
        definitions: list[WorkflowNodeDefinition] = []
        for node_type in LEGACY_NODE_ORDER:
            definition = by_type.get(node_type)
            if definition is None:
                continue
            definitions.append(
                WorkflowNodeDefinition(
                    type=definition.type,
                    label=definition.label,
                    description=definition.description,
                    category=definition.category,
                    ports=[
                        NodePort(
                            handle=port.handle,
                            label=port.label,
                            direction=port.direction,
                            data_type=self._legacy_data_type(port.data_type),
                        )
                        for port in definition.ports
                    ],
                    parameters=[
                        NodeParameterSchema(
                            key=param.key,
                            label=param.label,
                            field_type=param.field_type,
                            required=param.required,
                            default=param.default,
                            options=param.options,
                            description=param.description,
                        )
                        for param in definition.config_schema
                    ],
                )
            )

        return CatalogResponse(nodes=definitions)

    def _legacy_data_type(self, data_type: str) -> str:
        if data_type == "string":
            return "text"
        if data_type == "document[]":
            return "text"
        return data_type


legacy_workflow_adapter = LegacyWorkflowAdapterService()