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

    it('blocks new runs while the execution error modal is open', () => {
        const source = readWorkflowPageSource()
        expect(source).toContain('const isExecutionErrorModalOpen = executionErrorModal !== null')
        expect(source).toContain('if (executionErrorModal)')
        expect(source).toContain("setStatusText('Close the execution error dialog before starting a new run')")
        expect(source).toContain('disabled={isRunning || !hasRunnableNodes || isExecutionErrorModalOpen}')
    })
})
