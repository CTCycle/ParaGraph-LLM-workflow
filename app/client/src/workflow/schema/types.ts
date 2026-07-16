export type NodeCategory =
    | 'input'
    | 'web'
    | 'prompt'
    | 'model'
    | 'memory'
    | 'processing'
    | 'retrieval'
    | 'embeddings'
    | 'text_segmentation'
    | 'output'
    | 'serialization'
    | 'vector_storage'
    | 'database'
    | 'control'
export type NodeDataType =
    | 'TEXT'
    | 'IMAGE'
    | 'VIDEO'
    | 'AUDIO'
    | 'DOCUMENT'
    | 'DOCUMENT_LIST'
    | 'DATABASE_CONNECTION'
    | 'CHUNK'
    | 'CHUNK_LIST'
    | 'EMBEDDING'
    | 'VECTOR_POINT_LIST'
    | 'VECTOR_STORE_HANDLE'
    | 'RETRIEVAL_RESULTS'
    | 'JSON'
    | 'MODEL_HANDLE'
    | 'CHAT_HISTORY_HANDLE'
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

export interface NodeRuntimePluginDefinition {
    script_path: string
    entrypoint: string
}

export type NodeControllerScope = 'source' | 'target' | 'both'

export interface NodeControllerDefinition {
    name: string
    data_type: NodeDataType
    required: boolean
    accepts_multiple: boolean
    scope?: NodeControllerScope
    description?: string
}

export interface NodeRuntimeDefinition {
    executor_key: string
    cacheable: boolean
    deterministic: boolean
    side_effecting: boolean
    plugin?: NodeRuntimePluginDefinition | null
}

export interface NodeManifest {
    id: string
    version: number
    name: string
    category: NodeCategory
    description: string
    inputs: NodePortDefinition[]
    outputs: NodePortDefinition[]
    controllers?: NodeControllerDefinition[]
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
    skipped?: boolean
}

export interface WorkflowConnection {
    from_node: string
    to_node: string
    connection_type?: 'data' | 'controller'
    from_output?: string
    to_input?: string
    from_controller?: string
    to_controller?: string
}

export interface WorkflowDefinition {
    schema_version: 2
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
    items_expanded?: boolean
    pinged?: boolean
    skipped?: boolean
    is_global?: boolean
}

export interface VisualGraph {
    schema_version: 2
    nodes: VisualNodeState[]
    groups: Record<string, unknown>[]
    comments: Record<string, unknown>[]
}

export interface WorkflowDocument {
    workflow_id: string
    name: string
    definition: WorkflowDefinition
    visual_graph: VisualGraph
    created_at: string
    updated_at: string
}

export interface WorkflowShareBundle {
    bundle_version: 1
    app: string
    created_at: string
    workflow: {
        name: string
        definition: WorkflowDefinition
        visual_graph: VisualGraph
    }
    required_nodes: NodeManifest[]
}

export interface WorkflowTemplate {
    id: string
    name: string
    description: string
    tags: string[]
    definition: WorkflowDefinition
    visual_graph: VisualGraph
    required_nodes: NodeManifest[]
    metadata: Record<string, unknown>
}

export interface WorkflowTemplateListResponse {
    templates: WorkflowTemplate[]
}

export interface WorkflowOpenIntentAddNode {
    type: 'add-node'
    node_id: string
    node_version: number
}

export interface WorkflowOpenIntentLoadTemplate {
    type: 'load-template'
    template: WorkflowTemplate
}

export type WorkflowOpenIntent = WorkflowOpenIntentAddNode | WorkflowOpenIntentLoadTemplate

export interface WorkflowNavigationState {
    workflow_intent?: WorkflowOpenIntent
}

export interface ExecutionBinding {
    binding_type?: 'input' | 'controller'
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
    request_id?: string | null
    status: string
    execution_session_id?: string | null
    poll_interval: number
}

export type ExecutionStatus = 'queued' | 'running' | 'completed' | 'failed' | 'cancelled' | 'paused'

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
    request_id?: string | null
    workflow_id?: string | null
    execution_session_id?: string | null
    plan_id: string
    status: ExecutionStatus
    created_at: string
    updated_at: string
    progress: number
    steps: ExecutionStepState[]
    outputs: Record<string, Record<string, unknown>>
    error?: string | null
    pause_payload?: Record<string, unknown> | null
    resume_token?: string | null
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
    request_id?: string | null
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
    supports_embeddings: boolean
    supports_reasoning: boolean
    supports_structured_output: boolean
    timeout_s?: number | null
}

export interface ProviderModelCatalogResponse {
    models: ProviderModelDefinition[]
}

export interface OllamaLibraryModelDefinition {
    model: string
    description: string | null
    homepage: string
    pulled: boolean
}

export interface OllamaLibraryCatalogResponse {
    models: OllamaLibraryModelDefinition[]
    total_count: number
    pulled_count: number
    refreshed_at: string
    source: string
}

export interface OllamaModelPullResponse {
    ok: boolean
    model: string
    message: string
}

export type ModelVisibilityFilter = 'all' | 'public' | 'private' | 'gated'
export type HuggingFaceSortBy = 'relevance' | 'downloads' | 'likes' | 'updated'

export interface HuggingFaceModelDefinition {
    repo_id: string
    author: string | null
    task: string | null
    library: string | null
    likes: number | null
    downloads: number | null
    visibility: 'public' | 'private' | 'gated' | 'unknown'
    private: boolean | null
    gated: boolean | null
    last_modified: string | null
    url: string
    downloaded: boolean
    size_bytes: number | null
}

export interface HuggingFaceModelCatalogResponse {
    models: HuggingFaceModelDefinition[]
    page: number
    page_size: number
    has_more: boolean
    using_token: boolean
    warning: string | null
    available_tasks: string[]
    available_libraries: string[]
}

export type HuggingFaceDownloadJobStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'

export interface HuggingFaceModelDownloadResponse {
    ok: boolean
    repo_id: string
    message: string
    destination_path: string
    already_downloaded: boolean
    job_id: string | null
    status: HuggingFaceDownloadJobStatus
    progress: number
    downloaded_bytes: number
    total_bytes: number | null
    poll_interval: number
}

export interface HuggingFaceModelDownloadStatusResponse {
    job_id: string
    repo_id: string
    destination_path: string
    status: HuggingFaceDownloadJobStatus
    progress: number
    message: string | null
    downloaded_bytes: number
    total_bytes: number | null
    error: string | null
}

export interface HuggingFaceModelDownloadCancelResponse {
    ok: boolean
    job_id: string
    repo_id: string
    message: string
}
export interface DocumentRecord {
    id: string
    text: string
    source_uri: string
    mime_type: string
    metadata: Record<string, unknown>
}

export interface ChunkRecord {
    id: string
    document_id: string
    text: string
    source_uri: string
    chunk_index: number
    token_count: number
    metadata: Record<string, unknown>
}

export interface VectorPoint {
    id: string
    chunk_id: string
    document_id: string
    text: string
    source_uri: string
    vector: number[]
    metadata: Record<string, unknown>
}

export interface VectorStoreHandle {
    backend: string
    index_name: string
    artifact_path: string
    metric: string
    dimension: number
    embedding_provider: string
    embedding_model: string
    metadata: Record<string, unknown>
}

export interface RetrievalHit {
    id: string
    chunk_id: string
    document_id: string
    text: string
    source_uri: string
    score: number
    metadata: Record<string, unknown>
}

export interface RetrievalResults {
    query: string
    hits: RetrievalHit[]
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

export interface ConfigurationProfileSummary {
    profile_name: string
    created_at: string
    updated_at: string
}

export interface ConfigurationProfileListResponse {
    session_name: string
    profiles: ConfigurationProfileSummary[]
}

export interface OllamaStatusResponse {
    ok: boolean
    message: string
    base_url: string
    model_count: number
}

export interface ProviderStatusResponse {
    ok: boolean
    provider: string
    message: string
    base_url: string
    model_count: number
}

export interface DatabaseConnectionCheckResponse {
    ok: boolean
    message: string
}

export interface DatabaseSchemaColumn {
    name: string
    type: string
    nullable: boolean
    default: unknown
    primary_key: boolean
}

export interface DatabaseSchemaPrimaryKey {
    name: string | null
    columns: string[]
}

export interface DatabaseSchemaForeignKey {
    name: string | null
    columns: string[]
    referred_table: string | null
    referred_columns: string[]
}

export interface DatabaseSchemaIndex {
    name: string | null
    columns: string[]
    unique: boolean
}

export interface DatabaseSchemaTable {
    name: string
    columns: DatabaseSchemaColumn[]
    primary_key: DatabaseSchemaPrimaryKey
    foreign_keys: DatabaseSchemaForeignKey[]
    indexes: DatabaseSchemaIndex[]
}

export interface DatabaseSchemaResponse {
    tables: DatabaseSchemaTable[]
}


export interface VectorStoreConnectionCheckResponse {
    ok: boolean
    message: string
}

