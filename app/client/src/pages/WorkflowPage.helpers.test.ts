import { describe, expect, it } from 'vitest'

import {
    buildNodeGlowLevelMap,
    formatListEditorValue,
    normalizeStringList,
    parseListEditorDraft,
    pushNodeGlowTrail,
} from './WorkflowPage'

describe('WorkflowPage helper behavior', () => {
    it('builds a short glow trail and assigns decreasing glow levels', () => {
        let trail = pushNodeGlowTrail([], 'node-a')
        trail = pushNodeGlowTrail(trail, 'node-b')
        trail = pushNodeGlowTrail(trail, 'node-c')

        const levels = buildNodeGlowLevelMap('node-c', trail)

        expect(trail).toEqual(['node-c', 'node-b', 'node-a'])
        expect(levels['node-c']).toBe(3)
        expect(levels['node-b']).toBe(2)
        expect(levels['node-a']).toBe(1)
    })

    it('preserves meaningful whitespace in separator lists when requested', () => {
        const defaultNormalized = normalizeStringList(' \n\n\t\n', { trimItems: true })
        const preserveNormalized = normalizeStringList(' \n\n\t\n', { trimItems: false })

        expect(defaultNormalized).toEqual([])
        expect(preserveNormalized).toEqual([' ', '\t'])
    })

    it('keeps Enter/newline draft text visible while still parsing list values', () => {
        const draft = 'alpha\n'
        const parsed = parseListEditorDraft(draft)
        const display = formatListEditorValue([], draft)

        expect(parsed).toEqual(['alpha'])
        expect(display).toBe('alpha\n')
    })

})
