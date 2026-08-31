import type {
    HuggingFaceModelDownloadResponse,
    NodeManifest,
    VisualGraph,
    WorkflowDefinition,
    WorkflowTemplateManifest,
} from './apiTypes.generated'

export type * from './apiTypes.generated'

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

export type ChatHistoryNodeType = 'CHAT_HISTORY_MEMORY' | 'CHAT_HISTORY_PERSISTED'

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
    | 'TOKENIZER_OUTPUT'
    | 'METADATA'
    | 'METADATA_LIST'
    | 'TOOL_DEFINITION'
    | 'TOOL_COLLECTION_HANDLE'
    | 'TOOL_CALL_RESULT'
    | 'SQL_OPERATION_RESULT'
    | 'JSON'
    | 'MODEL_HANDLE'
    | 'CHAT_HISTORY_HANDLE'
    | 'DATASET'
    | 'BOOLEAN'
    | 'ANY'

export type VectorMetric = 'cosine' | 'l2' | 'dot'
export type VectorSearchMode = 'vector' | 'keyword' | 'hybrid'
export type VectorSearchEngine = 'native' | 'faiss_augmented'
export type VectorFilterOperator = 'eq' | 'in' | 'exists' | 'contains' | 'gt' | 'gte' | 'lt' | 'lte'
export type VectorScoreSemantics = 'normalized_similarity' | 'native_similarity'

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

export interface WorkflowOpenIntentAddNode {
    type: 'add-node'
    node_id: string
    node_version: number
}

export interface WorkflowOpenIntentLoadTemplate {
    type: 'load-template'
    template: WorkflowTemplateManifest
}

export type WorkflowOpenIntent = WorkflowOpenIntentAddNode | WorkflowOpenIntentLoadTemplate

export interface WorkflowNavigationState {
    workflow_intent?: WorkflowOpenIntent
}

export type ExecutionStatus = 'queued' | 'running' | 'completed' | 'failed' | 'cancelled' | 'paused'

export type ExecutionEventType =
    | 'execution.queued'
    | 'execution.started'
    | 'execution.step.started'
    | 'execution.step.progress'
    | 'execution.step.completed'
    | 'execution.step.failed'
    | 'execution.cancellation.requested'
    | 'execution.cancelled'
    | 'execution.step.retry.started'
    | 'execution.step.retry.failed'
    | 'execution.step.timeout'
    | 'execution.paused'
    | 'execution.resumed'
    | 'execution.recovered'
    | 'execution.completed'
    | 'execution.failed'

export type ModelVisibilityFilter = 'all' | 'public' | 'private' | 'gated'
export type HuggingFaceSortBy = 'relevance' | 'downloads' | 'likes' | 'updated'
export type HuggingFaceDownloadJobStatus = HuggingFaceModelDownloadResponse['status']
