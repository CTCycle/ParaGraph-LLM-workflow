import { NodeCategory } from './types'

export type NodeCategoryFilter = 'all' | NodeCategory

export const NODE_CATEGORY_ORDER: NodeCategory[] = [
    'input',
    'model',
    'processing',
    'fragmentation',
    'output',
    'serialization',
    'control',
]

export const NODE_CATEGORY_LABELS: Record<NodeCategory, string> = {
    input: 'Input',
    model: 'Model',
    processing: 'Processing',
    fragmentation: 'Fragmentation',
    output: 'Output',
    serialization: 'Serialization',
    control: 'Control',
}

export function toNodeCategoryFilter(value: string): NodeCategoryFilter {
    if (
        value === 'input' ||
        value === 'model' ||
        value === 'processing' ||
        value === 'fragmentation' ||
        value === 'output' ||
        value === 'serialization' ||
        value === 'control'
    ) {
        return value
    }
    return 'all'
}

