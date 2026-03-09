import { NodeDefinition, WorkflowDefinition } from '../../workflow/schema/types'

const ALLOWED_CATEGORY_PAIRS = new Set(['input->process', 'process->process', 'process->output'])

export function validateEdgeCompatibility(
    definition: WorkflowDefinition,
    nodeCatalog: NodeDefinition[],
    edge: WorkflowDefinition['edges'][number],
): string | null {
    if (edge.source.node_id === edge.target.node_id) {
        return 'Self loops are not allowed'
    }

    const sourceNode = definition.nodes.find((node) => node.node_id === edge.source.node_id)
    const targetNode = definition.nodes.find((node) => node.node_id === edge.target.node_id)
    if (!sourceNode || !targetNode) {
        return 'Edge references missing node'
    }

    const sourceDefinition = nodeCatalog.find((entry) => entry.type === sourceNode.node_type)
    const targetDefinition = nodeCatalog.find((entry) => entry.type === targetNode.node_type)
    if (!sourceDefinition || !targetDefinition) {
        return 'Unknown node type'
    }

    const categoryPair = `${sourceDefinition.category}->${targetDefinition.category}`
    if (!ALLOWED_CATEGORY_PAIRS.has(categoryPair)) {
        return `Invalid category flow ${categoryPair}`
    }

    const sourcePort = sourceDefinition.ports.find(
        (port) => port.direction === 'output' && port.handle === edge.source.port,
    )
    const targetPort = targetDefinition.ports.find(
        (port) => port.direction === 'input' && port.handle === edge.target.port,
    )

    if (!sourcePort || !targetPort) {
        return 'Unknown port handle'
    }

    const compatible =
        sourcePort.data_type === targetPort.data_type ||
        sourcePort.data_type === 'any' ||
        targetPort.data_type === 'any'

    if (!compatible) {
        return `Type mismatch ${sourcePort.data_type} -> ${targetPort.data_type}`
    }

    return null
}