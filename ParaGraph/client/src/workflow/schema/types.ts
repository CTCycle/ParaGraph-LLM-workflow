export type NodeCategory = 'input' | 'process' | 'output'
export type PortDirection = 'input' | 'output'

export interface WorkflowPortRef {
    node_id: string
    port: string
}

export interface WorkflowNodeSpec {
    node_id: string
    node_type: string
    config: Record<string, unknown>
}

export interface WorkflowEdgeSpec {
    edge_id: string
    source: WorkflowPortRef
    target: WorkflowPortRef
}

export interface WorkflowDefinition {
    schema_version: number
    nodes: WorkflowNodeSpec[]
    edges: WorkflowEdgeSpec[]
    metadata: Record<string, unknown>
}

export interface VisualNodeState {
    node_id: string
    x: number
    y: number
    width: number
    height: number
    collapsed: boolean
}

export interface VisualGraph {
    schema_version: number
    nodes: VisualNodeState[]
    groups: Record<string, unknown>[]
    comments: Record<string, unknown>[]
}

export interface WorkflowDocument {
    workflow_id: string
    name: string
    latest_version: number
    definition: WorkflowDefinition
    visual_graph: VisualGraph
    created_at: string
    updated_at: string
}

export interface PortSchema {
    handle: string
    label: string
    direction: PortDirection
    data_type: string
}

export interface ConfigFieldSchema {
    key: string
    label: string
    field_type: string
    required: boolean
    default: unknown
    options: string[]
    description?: string
}

export interface NodeExecutionSemantics {
    purity: 'pure' | 'side_effecting'
    scheduling: 'sync' | 'async'
    determinism: 'deterministic' | 'provider_dependent'
    cacheable: boolean
    streamable: boolean
    retryable: boolean
    emits_artifacts: boolean
    requires_secrets: boolean
}

export interface NodeDefinition {
    type: string
    version: number
    label: string
    description: string
    category: NodeCategory
    ports: PortSchema[]
    config_schema: ConfigFieldSchema[]
    semantics: NodeExecutionSemantics
}

export interface NodeCatalogResponse {
    nodes: NodeDefinition[]
}

export interface ProviderCapability {
    provider: string
    supports_chat: boolean
    supports_embeddings: boolean
    supports_structured_output: boolean
    supports_streaming: boolean
    supports_tool_calling: boolean
}

export interface ProviderCatalogResponse {
    providers: ProviderCapability[]
}

export interface LegacyWorkflowGraph {
    nodes: Array<{
        id: string
        type: string
        position: { x: number; y: number }
        params: Record<string, unknown>
    }>
    edges: Array<{
        id: string
        source: string
        sourceHandle: string
        target: string
        targetHandle: string
    }>
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

export type ExecutionEventType =
    | 'execution.queued'
    | 'execution.started'
    | 'execution.step.started'
    | 'execution.step.progress'
    | 'execution.step.completed'
    | 'execution.step.failed'
    | 'execution.completed'
    | 'execution.failed'

export interface ExecutionEventEnvelope {
    event_type: ExecutionEventType
    run_id: string
    step_id: string | null
    sequence: number
    timestamp: string
    payload: Record<string, unknown>
}