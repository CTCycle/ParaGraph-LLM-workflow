import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

function readModelsPageCss(): string {
    return readFileSync('src/pages/ModelsPage.css', 'utf-8')
}

describe('ModelsPage toolbar density styles', () => {
    it('keeps model filters legible and scroll-contained across breakpoints', () => {
        const css = readModelsPageCss()
        expect(css).toContain('.models-toolbar {')
        expect(css).toContain('grid-template-columns: minmax(220px, 1.6fr) minmax(140px, 0.8fr);')
        expect(css).toContain('.models-toolbar-hf {')
        expect(css).toContain('grid-template-columns:\n        minmax(0, 1fr)\n        minmax(0, 1fr)\n        minmax(0, 1fr);')
        expect(css).toContain('.models-toolbar-hf .models-search {')
        expect(css).toContain('grid-column: span 2;')
        expect(css).toContain('max-height: min(520px, calc(100vh - 360px));')
    })
})
