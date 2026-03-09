export type NodeCategory = 'input' | 'process' | 'output'
export type PortDirection = 'input' | 'output'

export interface WorkflowPosition {
    x: number
    y: number
}

export interface WorkflowNode {
    id: string
    type: string
    position: WorkflowPosition
    params: Record<string, unknown>
}

export interface WorkflowEdge {
    id: string
    source: string
    sourceHandle: string
    target: string
    targetHandle: string
}

export interface WorkflowGraph {
    nodes: WorkflowNode[]
    edges: WorkflowEdge[]
}

export interface WorkflowPort {
    handle: string
    label: string
    direction: PortDirection
    data_type: string
}

export interface WorkflowParameterSchema {
    key: string
    label: string
    field_type: string
    required: boolean
    default: unknown
    options: string[]
    description?: string
}

export interface WorkflowNodeDefinition {
    type: string
    label: string
    description: string
    category: NodeCategory
    ports: WorkflowPort[]
    parameters: WorkflowParameterSchema[]
}

export interface CatalogResponse {
    nodes: WorkflowNodeDefinition[]
}

export interface ValidateWorkflowResponse {
    valid: boolean
    errors: string[]
}

export interface ExecuteWorkflowResponse {
    job_id: string
    job_type: string
    status: string
    message: string
    poll_interval: number
    output_node_ids: string[]
}

export interface JobStatusResponse {
    job_id: string
    job_type: string
    status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'
    progress: number
    result?: {
        outputs?: Record<string, { text?: string }>
    }
    error?: string
}

export const WORKFLOW_ADDABLE_TYPES = ['Prompt', 'LLM', 'Output', 'Retrieval', 'VectorDB'] as const

export const WORKFLOW_ADD_EVENT = 'paragraph:workflow:add-node'
export const WORKFLOW_RUN_EVENT = 'paragraph:workflow:run'

export interface AddNodeEventDetail {
    nodeType: string
}
