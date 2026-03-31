import { describe, expect, it } from 'vitest'

import { NODE_CATEGORY_LABELS, NODE_CATEGORY_ORDER, toNodeCategoryFilter } from './nodeCategory'

describe('nodeCategory schema', () => {
    it('uses prompt, retrieval, and text segmentation categories with no fragmentation fallback', () => {
        expect(NODE_CATEGORY_ORDER).toContain('prompt')
        expect(NODE_CATEGORY_ORDER).toContain('retrieval')
        expect(NODE_CATEGORY_ORDER).toContain('text_segmentation')
        expect(NODE_CATEGORY_ORDER).not.toContain('fragmentation')

        expect(NODE_CATEGORY_LABELS.prompt).toBe('Prompt')
        expect(NODE_CATEGORY_LABELS.retrieval).toBe('Retrieval')
        expect(NODE_CATEGORY_LABELS.text_segmentation).toBe('Text Segmentation')

        expect(toNodeCategoryFilter('prompt')).toBe('prompt')
        expect(toNodeCategoryFilter('retrieval')).toBe('retrieval')
        expect(toNodeCategoryFilter('text_segmentation')).toBe('text_segmentation')
        expect(toNodeCategoryFilter('fragmentation')).toBe('all')
    })
})

