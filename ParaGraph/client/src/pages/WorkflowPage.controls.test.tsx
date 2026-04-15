import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

function readWorkflowPageSource(): string {
    return readFileSync('src/pages/WorkflowPage.tsx', 'utf-8')
}

describe('WorkflowPage canvas controls source', () => {
    it('does not define a duplicate custom fit view control button', () => {
        const source = readWorkflowPageSource()
        expect(source).not.toContain('title="Fit view"')
        expect(source).not.toContain('aria-label="Fit view"')
    })

    it('uses symbolic grid toggle glyphs instead of legacy text markers', () => {
        const source = readWorkflowPageSource()
        expect(source).toContain("{isGridVisible ? '⊞' : '⊟'}")
        expect(source).not.toContain("{isGridVisible ? '##' : '..'}")
    })
})
