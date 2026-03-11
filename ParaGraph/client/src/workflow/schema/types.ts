export type NodeCategory = 'input' | 'model' | 'processing' | 'output' | 'serialization' | 'control'
export type NodeDataType =
    | 'TEXT'
    | 'IMAGE'
    | 'VIDEO'
    | 'AUDIO'
    | 'EMBEDDING'
    | 'TOKEN_IDS'
    | 'JSON'
    | 'MODEL_HANDLE'
    | 'DATASET'
    | 'BOOLEAN'
    | 'ANY'

export interface NodePortDefinition {
    name: string
    data_type: NodeDataType
    required: boolean
    accepts_multiple: boolean
    description?: string
}

export interface NodeParameterDefinition {
    name: string
    data_type: NodeDataType
    default: unknown
    constraints: Record<string, unknown>
    ui_control: string
    description?: string
}

export interface NodeUiDefinition {
    default_width: number
    accent_color: string
    icon?: string
    collapsed_by_default: boolean
}

export interface NodeRuntimeDefinition {
    executor_key: string
    cacheable: boolean
    deterministic: boolean
    side_effecting: boolean
}

export interface NodeManifest {
    id: string
    version: number
    name: string
    category: NodeCategory
    description: string
    inputs: NodePortDefinition[]
    outputs: NodePortDefinition[]
    parameters: NodeParameterDefinition[]
    ui: NodeUiDefinition
    runtime: NodeRuntimeDefinition
}

export interface NodeCatalogResponse {
    nodes: NodeManifest[]
}

export interface WorkflowNodeInstance {
    node_id: string
    node_type: string
    node_version: number
    parameters: Record<string, unknown>
}

export interface WorkflowConnection {
    from_node: string
    from_output: string
    to_node: string
    to_input: string
}

export interface WorkflowDefinition {
    schema_version: number
    nodes: WorkflowNodeInstance[]
    connections: WorkflowConnection[]
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

export interface ExecutionBinding {
    input_name: string
    source_node_id: string
    source_output: string
}

export interface ExecutionStepPlan {
    step_id: string
    node_id: string
    node_type: string
    node_version: number
    category: NodeCategory
    executor_key: string
    parameters: Record<string, unknown>
    bindings: ExecutionBinding[]
    timeout_ms?: number | null
    retries: number
    cacheable: boolean
}

export interface CompiledExecutionPlan {
    plan_id: string
    schema_version: number
    step_order: string[]
    steps: ExecutionStepPlan[]
    metadata: Record<string, unknown>
}

export interface CompilerDiagnostic {
    code: string
    message: string
    level: string
    node_id?: string | null
    connection?: WorkflowConnection | null
}

export interface CompileWorkflowResponse {
    valid: boolean
    diagnostics: CompilerDiagnostic[]
    plan?: CompiledExecutionPlan | null
}

export interface StartExecutionResponse {
    run_id: string
    status: string
    poll_interval: number
}

export type ExecutionStatus = 'queued' | 'running' | 'completed' | 'failed' | 'cancelled'

export interface ExecutionStepState {
    step_id: string
    node_id: string
    node_type: string
    status: 'queued' | 'running' | 'completed' | 'failed' | 'skipped'
    started_at?: string | null
    completed_at?: string | null
    output: Record<string, unknown>
    error?: string | null
}

export interface ExecutionRunState {
    run_id: string
    workflow_id?: string | null
    plan_id: string
    status: ExecutionStatus
    created_at: string
    updated_at: string
    progress: number
    steps: ExecutionStepState[]
    outputs: Record<string, Record<string, unknown>>
    error?: string | null
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

export interface ProviderModelDefinition {
    provider: string
    model: string
    label: string
    supports_image: boolean
    supports_reasoning: boolean
    supports_structured_output: boolean
}

export interface ProviderModelCatalogResponse {
    models: ProviderModelDefinition[]
}

export interface AccessKeyConfiguration {
    provider: string
    api_key: string | null
    base_url: string | null
    metadata: Record<string, unknown>
}

export interface OllamaConfiguration {
    base_url: string
    chat_model: string
    embedding_model: string
}

export interface AppConfigurationPayload {
    session_name: string
    access_keys: AccessKeyConfiguration[]
    ollama: OllamaConfiguration
}
