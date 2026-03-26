import { NodeCategory } from './types'

export type NodeCategoryFilter = 'all' | NodeCategory

export const NODE_CATEGORY_ORDER: NodeCategory[] = [
    'input',
    'prompt',
    'model',
    'processing',
    'text_segmentation',
    'output',
    'serialization',
    'database',
    'control',
]

export const NODE_CATEGORY_LABELS: Record<NodeCategory, string> = {
    input: 'Input',
    prompt: 'Prompt',
    model: 'Model',
    processing: 'Processing',
    text_segmentation: 'Text Segmentation',
    output: 'Output',
    serialization: 'Serialization',
    database: 'Database',
    control: 'Control',
}

export function toNodeCategoryFilter(value: string): NodeCategoryFilter {
    if (
        value === 'input' ||
        value === 'prompt' ||
        value === 'model' ||
        value === 'processing' ||
        value === 'text_segmentation' ||
        value === 'output' ||
        value === 'serialization' ||
        value === 'database' ||
        value === 'control'
    ) {
        return value
    }
    return 'all'
}

