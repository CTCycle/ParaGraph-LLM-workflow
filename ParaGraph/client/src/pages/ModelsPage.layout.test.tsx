import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

function readModelsPageCss(): string {
    return readFileSync('src/pages/ModelsPage.css', 'utf-8')
}

describe('ModelsPage toolbar density styles', () => {
    it('keeps desktop search/filter controls in single-row grid layouts', () => {
        const css = readModelsPageCss()
        expect(css).toContain('.models-toolbar {')
        expect(css).toContain('grid-template-columns: minmax(220px, 1.6fr) minmax(140px, 0.8fr);')
        expect(css).toContain('.models-toolbar-hf {')
        expect(css).toContain('1.5fr')
    })
})
