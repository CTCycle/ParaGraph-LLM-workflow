import { NodeCategory } from './types'

export type NodeCategoryFilter = 'all' | NodeCategory

export const NODE_CATEGORY_ORDER: NodeCategory[] = [
    'input',
    'prompt',
    'model',
    'processing',
    'retrieval',
    'embeddings',
    'text_segmentation',
    'output',
    'serialization',
    'vector_storage',
    'database',
    'control',
]

export const NODE_CATEGORY_LABELS: Record<NodeCategory, string> = {
    input: 'Input',
    prompt: 'Prompt',
    model: 'Model',
    processing: 'Processing',
    retrieval: 'Retrieval',
    embeddings: 'Embeddings',
    text_segmentation: 'Text Segmentation',
    output: 'Output',
    serialization: 'Serialization',
    vector_storage: 'Vector Storage',
    database: 'Database',
    control: 'Control',
}

export function toNodeCategoryFilter(value: string): NodeCategoryFilter {
    if (
        value === 'input' ||
        value === 'prompt' ||
        value === 'model' ||
        value === 'processing' ||
        value === 'retrieval' ||
        value === 'embeddings' ||
        value === 'text_segmentation' ||
        value === 'output' ||
        value === 'serialization' ||
        value === 'vector_storage' ||
        value === 'database' ||
        value === 'control'
    ) {
        return value
    }
    return 'all'
}

