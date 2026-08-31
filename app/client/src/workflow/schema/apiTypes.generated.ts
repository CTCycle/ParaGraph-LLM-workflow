// This file is generated from the FastAPI OpenAPI component schemas.
// Do not edit it manually. Run app/scripts/generate_frontend_api_contracts.py.

export interface AppConfigurationPayload {
    session_name: string
    provider_configurations: ProviderConfiguration[]
}

export interface Body_upload_directory_nodes_uploads_directory_post {
    files: string[]
}

export interface ChatHistoryHandle {
    node_type: "CHAT_HISTORY_MEMORY" | "CHAT_HISTORY_PERSISTED"
    node_id: string
    workflow_id: string
    execution_session_id: string
    max_messages: number
    separator: string
    keep_prompt_type: boolean
    execution_owned: boolean
}

export interface ChatHistoryMessage {
    role: "system" | "user" | "assistant"
    content: string
    timestamp: string
}

export interface ChatHistoryResponse {
    messages: ChatHistoryMessage[]
}

export interface CompileWorkflowRequest {
    definition: WorkflowDefinition
}

export interface CompileWorkflowResponse {
    valid: boolean
    diagnostics: CompilerDiagnostic[]
    plan?: CompiledExecutionPlan | null
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
    level: "error" | "warning"
    node_id?: string | null
    connection?: WorkflowConnection | null
}

export interface ConfigurationProfileListResponse {
    session_name: string
    profiles: ConfigurationProfileSummary[]
}

export interface ConfigurationProfileSummary {
    profile_name: string
    created_at: string
    updated_at: string
}

export interface DatabaseConnectionCheckRequest {
    node_type: "SQL_DATABASE" | "SQL_FILE_DATABASE"
    node_version: number
    parameters: Record<string, unknown>
}

export interface DatabaseConnectionCheckResponse {
    ok: boolean
    message: string
}

export interface DatabaseSchemaColumn {
    name: string
    type: string
    nullable: boolean
    default?: unknown | null
    primary_key: boolean
}

export interface DatabaseSchemaForeignKey {
    name?: string | null
    columns: string[]
    referred_table?: string | null
    referred_columns: string[]
}

export interface DatabaseSchemaIndex {
    name?: string | null
    columns: string[]
    unique: boolean
}

export interface DatabaseSchemaPrimaryKey {
    name?: string | null
    columns: string[]
}

export interface DatabaseSchemaRequest {
    node_type: "SQL_DATABASE" | "SQL_FILE_DATABASE"
    node_version: number
    parameters: Record<string, unknown>
}

export interface DatabaseSchemaResponse {
    tables: DatabaseSchemaTable[]
}

export interface DatabaseSchemaTable {
    name: string
    columns: DatabaseSchemaColumn[]
    primary_key: DatabaseSchemaPrimaryKey
    foreign_keys: DatabaseSchemaForeignKey[]
    indexes: DatabaseSchemaIndex[]
}

export interface EventHistoryResponse {
    run_id: string
    request_id?: string | null
    events: ExecutionEventEnvelope[]
}

export interface ExecutionActionResponse {
    run_id: string
    status: "queued" | "running" | "completed" | "failed" | "cancelled" | "paused"
    message: string
}

export interface ExecutionBinding {
    binding_type: "input" | "controller"
    input_name: string
    source_node_id: string
    source_output: string
}

export interface ExecutionEventEnvelope {
    event_type: "execution.queued" | "execution.started" | "execution.step.started" | "execution.step.progress" | "execution.step.completed" | "execution.step.failed" | "execution.cancellation.requested" | "execution.cancelled" | "execution.step.retry.started" | "execution.step.retry.failed" | "execution.step.timeout" | "execution.paused" | "execution.resumed" | "execution.recovered" | "execution.completed" | "execution.failed"
    run_id: string
    request_id?: string | null
    step_id?: string | null
    sequence: number
    timestamp: string
    payload: Record<string, unknown>
}

export interface ExecutionRunState {
    run_id: string
    request_id?: string | null
    workflow_id?: string | null
    execution_session_id?: string | null
    plan_id: string
    status: "queued" | "running" | "completed" | "failed" | "cancelled" | "paused"
    created_at: string
    updated_at: string
    progress: number
    steps: ExecutionStepState[]
    outputs: Record<string, Record<string, unknown>>
    error?: string | null
    pause_payload?: Record<string, unknown> | null
    resume_token?: string | null
    pause_checkpoint?: PauseCheckpoint | null
    plan?: CompiledExecutionPlan | null
    cancellation_requested: boolean
}

export interface ExecutionStepPlan {
    step_id: string
    node_id: string
    node_type: string
    node_version: number
    category: string
    executor_key: string
    parameters: Record<string, unknown>
    bindings: ExecutionBinding[]
    timeout_ms?: number | null
    retries: number
    cacheable: boolean
    side_effecting: boolean
    destructive: boolean
    idempotent: boolean
}

export interface ExecutionStepState {
    step_id: string
    node_id: string
    node_type: string
    status: "queued" | "running" | "paused" | "completed" | "failed" | "skipped"
    started_at?: string | null
    completed_at?: string | null
    output: Record<string, unknown>
    error?: string | null
    pause_payload?: Record<string, unknown> | null
    resume_token?: string | null
    position: number
    attempt_count: number
    blocked_reason?: string | null
}

export interface HTTPValidationError {
    detail: ValidationError[]
}

export interface HuggingFaceModelCatalogResponse {
    models: HuggingFaceModelDefinition[]
    page: number
    page_size: number
    has_more: boolean
    using_token: boolean
    warning?: string | null
    available_tasks: string[]
    available_libraries: string[]
}

export interface HuggingFaceModelDefinition {
    repo_id: string
    author?: string | null
    task?: string | null
    library?: string | null
    likes?: number | null
    downloads?: number | null
    visibility: "public" | "private" | "gated" | "unknown"
    private?: boolean | null
    gated?: boolean | null
    last_modified?: string | null
    url: string
    downloaded: boolean
    size_bytes?: number | null
}

export interface HuggingFaceModelDownloadCancelResponse {
    ok: boolean
    job_id: string
    repo_id: string
    message: string
}

export interface HuggingFaceModelDownloadRequest {
    repo_id: string
}

export interface HuggingFaceModelDownloadResponse {
    ok: boolean
    repo_id: string
    message: string
    destination_path: string
    already_downloaded: boolean
    job_id?: string | null
    status: "pending" | "running" | "completed" | "failed" | "cancelled"
    progress: number
    downloaded_bytes: number
    total_bytes?: number | null
    poll_interval: number
}

export interface HuggingFaceModelDownloadStatusResponse {
    job_id: string
    repo_id: string
    destination_path: string
    status: "pending" | "running" | "completed" | "failed" | "cancelled"
    progress: number
    message?: string | null
    downloaded_bytes: number
    total_bytes?: number | null
    error?: string | null
}

export interface NodeCatalogResponse {
    nodes: NodeManifest[]
    vector_store_capabilities: VectorStoreCapabilities[]
}

export interface NodeControllerDefinition {
    name: string
    data_type: "TEXT" | "IMAGE" | "VIDEO" | "AUDIO" | "DOCUMENT" | "DOCUMENT_LIST" | "DATABASE_CONNECTION" | "CHUNK" | "CHUNK_LIST" | "EMBEDDING" | "VECTOR_POINT_LIST" | "VECTOR_STORE_HANDLE" | "RETRIEVAL_RESULTS" | "TOKENIZER_OUTPUT" | "METADATA" | "METADATA_LIST" | "TOOL_DEFINITION" | "TOOL_COLLECTION_HANDLE" | "TOOL_CALL_RESULT" | "SQL_OPERATION_RESULT" | "JSON" | "MODEL_HANDLE" | "CHAT_HISTORY_HANDLE" | "DATASET" | "BOOLEAN" | "ANY"
    required: boolean
    accepts_multiple: boolean
    scope: "source" | "target" | "both"
    description?: string | null
}

export interface NodeManifest {
    id: string
    version: number
    name: string
    category: "input" | "web" | "prompt" | "model" | "memory" | "processing" | "retrieval" | "embeddings" | "text_segmentation" | "output" | "serialization" | "vector_storage" | "database" | "control"
    description: string
    inputs: NodePortDefinition[]
    outputs: NodePortDefinition[]
    controllers: NodeControllerDefinition[]
    parameters: NodeParameterDefinition[]
    ui: NodeUiDefinition
    runtime: NodeRuntimeDefinition
}

export interface NodeParameterDefinition {
    name: string
    data_type: "TEXT" | "IMAGE" | "VIDEO" | "AUDIO" | "DOCUMENT" | "DOCUMENT_LIST" | "DATABASE_CONNECTION" | "CHUNK" | "CHUNK_LIST" | "EMBEDDING" | "VECTOR_POINT_LIST" | "VECTOR_STORE_HANDLE" | "RETRIEVAL_RESULTS" | "TOKENIZER_OUTPUT" | "METADATA" | "METADATA_LIST" | "TOOL_DEFINITION" | "TOOL_COLLECTION_HANDLE" | "TOOL_CALL_RESULT" | "SQL_OPERATION_RESULT" | "JSON" | "MODEL_HANDLE" | "CHAT_HISTORY_HANDLE" | "DATASET" | "BOOLEAN" | "ANY"
    default?: unknown | null
    constraints: Record<string, unknown>
    ui_control: string
    description?: string | null
}

export interface NodePluginRuntimeDefinition {
    script_path: string
    entrypoint: string
}

export interface NodePortDefinition {
    name: string
    data_type: "TEXT" | "IMAGE" | "VIDEO" | "AUDIO" | "DOCUMENT" | "DOCUMENT_LIST" | "DATABASE_CONNECTION" | "CHUNK" | "CHUNK_LIST" | "EMBEDDING" | "VECTOR_POINT_LIST" | "VECTOR_STORE_HANDLE" | "RETRIEVAL_RESULTS" | "TOKENIZER_OUTPUT" | "METADATA" | "METADATA_LIST" | "TOOL_DEFINITION" | "TOOL_COLLECTION_HANDLE" | "TOOL_CALL_RESULT" | "SQL_OPERATION_RESULT" | "JSON" | "MODEL_HANDLE" | "CHAT_HISTORY_HANDLE" | "DATASET" | "BOOLEAN" | "ANY"
    required: boolean
    accepts_multiple: boolean
    description?: string | null
}

export interface NodeRuntimeDefinition {
    executor_key: string
    cacheable: boolean
    deterministic: boolean
    side_effecting: boolean
    destructive: boolean
    idempotent: boolean
    plugin?: NodePluginRuntimeDefinition | null
}

export interface NodeUiDefinition {
    default_width: number
    accent_color: string
    icon?: string | null
    collapsed_by_default: boolean
}

export interface OllamaLibraryCatalogResponse {
    models: OllamaLibraryModelDefinition[]
    total_count: number
    pulled_count: number
    refreshed_at: string
    source: string
}

export interface OllamaLibraryModelDefinition {
    model: string
    description?: string | null
    homepage: string
    pulled: boolean
}

export interface OllamaModelPullRequest {
    model: string
}

export interface OllamaModelPullResponse {
    ok: boolean
    model: string
    message: string
}

export interface OllamaPingRequest {
    base_url?: string | null
}

export interface OllamaStatusResponse {
    ok: boolean
    message: string
    base_url: string
    model_count: number
}

export interface PauseCheckpoint {
    node_id: string
    step_id: string
    resume_token: string
    pause_payload: Record<string, unknown>
    expected_reviewed_payload_schema: Record<string, unknown>
}

export interface ProviderCapability {
    provider: string
    label: string
    configuration_kind: "local" | "cloud" | "remote"
    model_source: "live" | "hosted_registry" | "downloaded_filesystem"
    default_base_url?: string | null
    default_chat_model?: string | null
    default_embedding_model?: string | null
    requires_api_key: boolean
    supports_status_check: boolean
    supports_chat: boolean
    supports_embeddings: boolean
    supports_structured_output: boolean
    supports_streaming: boolean
    supports_tool_calling: boolean
    supports_tool_selection: boolean
    supports_native_tool_protocol: boolean
}

export interface ProviderCatalogResponse {
    providers: ProviderCapability[]
}

export interface ProviderConfiguration {
    provider: string
    api_key?: string | null
    has_api_key: boolean
    base_url?: string | null
    metadata: Record<string, unknown>
}

export interface ProviderModelCatalogResponse {
    models: ProviderModelDefinition[]
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

export interface ProviderPingRequest {
    provider: string
    base_url?: string | null
    api_key?: string | null
}

export interface ProviderStatusResponse {
    ok: boolean
    provider: string
    message: string
    base_url: string
    model_count: number
}

export interface ResumeExecutionRequest {
    resume_token: string
    reviewed_payload?: Record<string, unknown> | null
}

export interface StartExecutionRequest {
    workflow_id?: string | null
    execution_session_id?: string | null
    plan: CompiledExecutionPlan
}

export interface StartExecutionResponse {
    run_id: string
    request_id?: string | null
    status: "queued" | "running" | "completed" | "failed" | "cancelled" | "paused"
    execution_session_id?: string | null
    poll_interval: number
}

export interface UploadedDirectoryResponse {
    path: string
    file_count: number
    files: string[]
}

export interface ValidationError {
    loc: (string | number)[]
    msg: string
    type: string
    input: unknown
    ctx: Record<string, unknown>
}

export interface VectorStoreCapabilities {
    backend: string
    supported_metrics: ("cosine" | "l2" | "dot")[]
    supported_search_modes: ("vector" | "keyword" | "hybrid")[]
    supported_search_engines: ("native" | "faiss_augmented")[]
    supports_namespaces: boolean
    supports_metadata_filtering: boolean
    supported_filter_operators: ("eq" | "in" | "exists" | "contains" | "gt" | "gte" | "lt" | "lte")[]
    supports_filter_groups: boolean
    supports_minimum_should_match: boolean
    supports_keyword_index: boolean
    supported_operations: ("insert" | "upsert" | "update" | "delete_ids" | "delete_document" | "delete_filter" | "inspect" | "delete_collection" | "reload" | "search" | "close")[]
    score_semantics_by_metric: Record<string, "normalized_similarity" | "native_similarity">
}

export interface VectorStoreConnectionCheckRequest {
    node_type: "VECTOR_STORE"
    node_version: number
    parameters: Record<string, unknown>
}

export interface VectorStoreConnectionCheckResponse {
    ok: boolean
    message: string
}

export interface VisualGraph {
    schema_version: 2
    nodes: VisualNodeState[]
    groups: Record<string, unknown>[]
    comments: Record<string, unknown>[]
}

export interface VisualNodeState {
    node_id: string
    x: number
    y: number
    width: number
    height: number
    collapsed: boolean
    items_expanded: boolean
    pinged: boolean
    skipped: boolean
}

export interface WorkflowConnection {
    from_node: string
    to_node: string
    connection_type: "data" | "controller"
    from_output?: string | null
    to_input?: string | null
    from_controller?: string | null
    to_controller?: string | null
}

export interface WorkflowDefinition {
    schema_version: 2
    nodes: WorkflowNodeInstance[]
    connections: WorkflowConnection[]
    metadata: Record<string, unknown>
}

export interface WorkflowNodeInstance {
    node_id: string
    node_type: string
    node_version: number
    parameters: Record<string, unknown>
    timeout_ms?: number | null
    retries: number
    skipped: boolean
}

export interface WorkflowTemplateListResponse {
    templates: WorkflowTemplateManifest[]
}

export interface WorkflowTemplateManifest {
    id: string
    name: string
    description: string
    tags: string[]
    definition: WorkflowDefinition
    visual_graph: VisualGraph
    required_nodes: NodeManifest[]
    metadata: Record<string, unknown>
}
