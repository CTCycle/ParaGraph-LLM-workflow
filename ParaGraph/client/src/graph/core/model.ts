import { VisualNodeState, WorkflowDefinition } from '../../workflow/schema/types'

export interface GraphDocument {
    definition: WorkflowDefinition
    visual: {
        nodes: VisualNodeState[]
    }
}

export function findVisualNode(document: GraphDocument, nodeId: string): VisualNodeState | undefined {
    return document.visual.nodes.find((node) => node.node_id === nodeId)
}

export function addNode(
    document: GraphDocument,
    node: WorkflowDefinition['nodes'][number],
    visual: VisualNodeState,
): GraphDocument {
    return {
        definition: {
            ...document.definition,
            nodes: [...document.definition.nodes, node],
        },
        visual: {
            nodes: [...document.visual.nodes, visual],
        },
    }
}

export function removeNode(document: GraphDocument, nodeId: string): GraphDocument {
    return {
        definition: {
            ...document.definition,
            nodes: document.definition.nodes.filter((node) => node.node_id !== nodeId),
            edges: document.definition.edges.filter(
                (edge) => edge.source.node_id !== nodeId && edge.target.node_id !== nodeId,
            ),
        },
        visual: {
            nodes: document.visual.nodes.filter((node) => node.node_id !== nodeId),
        },
    }
}

export function updateNodeConfig(
    document: GraphDocument,
    nodeId: string,
    patch: Record<string, unknown>,
): GraphDocument {
    return {
        definition: {
            ...document.definition,
            nodes: document.definition.nodes.map((node) => {
                if (node.node_id !== nodeId) {
                    return node
                }
                return {
                    ...node,
                    config: {
                        ...node.config,
                        ...patch,
                    },
                }
            }),
        },
        visual: document.visual,
    }
}

export function moveNode(document: GraphDocument, nodeId: string, x: number, y: number): GraphDocument {
    return {
        definition: document.definition,
        visual: {
            nodes: document.visual.nodes.map((node) => (node.node_id === nodeId ? { ...node, x, y } : node)),
        },
    }
}

export function addEdge(
    document: GraphDocument,
    edge: WorkflowDefinition['edges'][number],
): GraphDocument {
    const exists = document.definition.edges.some(
        (current) =>
            current.source.node_id === edge.source.node_id &&
            current.source.port === edge.source.port &&
            current.target.node_id === edge.target.node_id &&
            current.target.port === edge.target.port,
    )
    if (exists) {
        return document
    }

    return {
        definition: {
            ...document.definition,
            edges: [...document.definition.edges, edge],
        },
        visual: document.visual,
    }
}

export function removeEdge(document: GraphDocument, edgeId: string): GraphDocument {
    return {
        definition: {
            ...document.definition,
            edges: document.definition.edges.filter((edge) => edge.edge_id !== edgeId),
        },
        visual: document.visual,
    }
}