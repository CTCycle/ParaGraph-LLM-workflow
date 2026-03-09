import { LegacyWorkflowGraph, VisualGraph, WorkflowDefinition } from '../../workflow/schema/types'

export function toLegacyWorkflowGraph(definition: WorkflowDefinition, visual: VisualGraph): LegacyWorkflowGraph {
    const visualByNode = new Map(visual.nodes.map((node) => [node.node_id, node]))

    return {
        nodes: definition.nodes.map((node, index) => {
            const position = visualByNode.get(node.node_id)
            return {
                id: node.node_id,
                type: node.node_type,
                position: {
                    x: position?.x ?? 120 + index * 24,
                    y: position?.y ?? 120 + index * 16,
                },
                params: { ...node.config },
            }
        }),
        edges: definition.edges.map((edge) => ({
            id: edge.edge_id,
            source: edge.source.node_id,
            sourceHandle: edge.source.port,
            target: edge.target.node_id,
            targetHandle: edge.target.port,
        })),
    }
}