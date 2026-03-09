import { LegacyWorkflowGraph, VisualGraph, WorkflowDefinition } from './types'

export const WORKFLOW_SCHEMA_VERSION = 1
export const WORKFLOW_STORAGE_KEY = 'paragraph.workflow.document.v1'
export const LEGACY_STORAGE_KEY = 'paragraph.workflow.graph'

export function buildEmptyWorkflowDefinition(): WorkflowDefinition {
    return {
        schema_version: WORKFLOW_SCHEMA_VERSION,
        nodes: [],
        edges: [],
        metadata: {},
    }
}

export function buildEmptyVisualGraph(): VisualGraph {
    return {
        schema_version: WORKFLOW_SCHEMA_VERSION,
        nodes: [],
        groups: [],
        comments: [],
    }
}

export function migrateLegacyGraphToDocument(
    workflowId: string,
    name: string,
    legacyGraph: LegacyWorkflowGraph,
): { definition: WorkflowDefinition; visualGraph: VisualGraph } {
    const definition: WorkflowDefinition = {
        schema_version: WORKFLOW_SCHEMA_VERSION,
        nodes: legacyGraph.nodes.map((node) => ({
            node_id: node.id,
            node_type: node.type,
            config: { ...node.params },
        })),
        edges: legacyGraph.edges.map((edge) => ({
            edge_id: edge.id,
            source: {
                node_id: edge.source,
                port: edge.sourceHandle,
            },
            target: {
                node_id: edge.target,
                port: edge.targetHandle,
            },
        })),
        metadata: {
            migrated_from: 'legacy_workflow_graph',
            workflow_id: workflowId,
            workflow_name: name,
        },
    }

    const visualGraph: VisualGraph = {
        schema_version: WORKFLOW_SCHEMA_VERSION,
        nodes: legacyGraph.nodes.map((node) => ({
            node_id: node.id,
            x: node.position.x,
            y: node.position.y,
            width: 280,
            height: 180,
            collapsed: false,
        })),
        groups: [],
        comments: [],
    }

    return { definition, visualGraph }
}
