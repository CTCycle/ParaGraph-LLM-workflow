import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import * as workflowApi from '../app/services/workflowApi'
import NodesPage from './NodesPage'
import { createNodeManifest } from '../test/fixtures'

vi.mock('../app/services/workflowApi', () => ({
    fetchNodeCatalog: vi.fn(),
    importNodeManifest: vi.fn(),
}))

describe('NodesPage import modal', () => {
    it('validates JSON and handles import success and error paths', async () => {
        const fetchNodeCatalogMock = vi.mocked(workflowApi.fetchNodeCatalog)
        const importNodeManifestMock = vi.mocked(workflowApi.importNodeManifest)

        const initialManifest = createNodeManifest()
        fetchNodeCatalogMock.mockResolvedValue({ nodes: [initialManifest] })
        importNodeManifestMock.mockImplementation(async (manifest) => {
            if (manifest.id === 'FAIL_NODE') {
                throw new Error('Duplicate node id/version')
            }
            return manifest
        })

        render(<NodesPage />)
        await screen.findByText('Prompt')

        await userEvent.click(screen.getByRole('button', { name: 'Open custom node JSON import' }))
        const dialog = screen.getByRole('dialog', { name: 'Custom node JSON import' })
        const textarea = within(dialog).getByRole('textbox')

        fireEvent.change(textarea, { target: { value: '{"bad":"payload"}' } })
        await userEvent.click(within(dialog).getByRole('button', { name: 'Validate' }))
        await screen.findByText('JSON must contain a node manifest object')

        const customManifest = createNodeManifest({
            id: 'CUSTOM_NODE',
            name: 'Custom Node',
            category: 'processing',
            description: 'A custom node',
        })
        fireEvent.change(textarea, { target: { value: JSON.stringify(customManifest) } })
        await userEvent.click(within(dialog).getByRole('button', { name: 'Validate' }))
        await screen.findByText('Valid manifest: CUSTOM_NODE v1')

        await userEvent.click(within(dialog).getByRole('button', { name: 'Import Node' }))
        await waitFor(() => {
            expect(screen.queryByRole('dialog', { name: 'Custom node JSON import' })).not.toBeInTheDocument()
        })
        await screen.findByText('Imported CUSTOM_NODE v1')

        await userEvent.click(screen.getByRole('button', { name: 'Open custom node JSON import' }))
        const secondDialog = screen.getByRole('dialog', { name: 'Custom node JSON import' })
        const secondTextarea = within(secondDialog).getByRole('textbox')

        const failingManifest = createNodeManifest({
            id: 'FAIL_NODE',
            name: 'Broken Node',
            category: 'processing',
            description: 'Expected import failure',
        })
        fireEvent.change(secondTextarea, { target: { value: JSON.stringify(failingManifest) } })
        await userEvent.click(within(secondDialog).getByRole('button', { name: 'Import Node' }))
        await screen.findByText('Duplicate node id/version')
    })
    it('shows prompt and text segmentation category filters', async () => {
        const fetchNodeCatalogMock = vi.mocked(workflowApi.fetchNodeCatalog)
        fetchNodeCatalogMock.mockResolvedValue({
            nodes: [
                createNodeManifest({ id: 'PROMPT', name: 'Prompt Node', category: 'prompt' }),
                createNodeManifest({ id: 'RECURSIVE_SPLIT_CHUNKS', name: 'Recursive Split', category: 'text_segmentation' }),
            ],
        })

        render(<NodesPage />)
        await screen.findByText('Prompt Node')

        expect(screen.getByRole('checkbox', { name: /Prompt/i })).toBeInTheDocument()
        expect(screen.getByRole('checkbox', { name: /Text Segmentation/i })).toBeInTheDocument()
    })
})

