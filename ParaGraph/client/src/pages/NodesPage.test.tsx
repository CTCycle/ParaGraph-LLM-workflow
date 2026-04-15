import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as nodesApi from '../app/services/nodesApi'
import * as workflowsApi from '../app/services/workflowsApi'
import NodesPage from './NodesPage'
import { createNodeManifest } from '../test/fixtures'

const navigateMock = vi.fn()

vi.mock('react-router-dom', () => ({
    useNavigate: () => navigateMock,
}))

vi.mock('../app/services/nodesApi', () => ({
    fetchNodeCatalog: vi.fn(),
    importNodeManifest: vi.fn(),
}))

vi.mock('../app/services/workflowsApi', () => ({
    fetchWorkflowTemplates: vi.fn(),
}))

describe('NodesPage', () => {
    beforeEach(() => {
        vi.clearAllMocks()
        navigateMock.mockReset()
    })

    it('validates JSON and handles import success and error paths', async () => {
        const fetchNodeCatalogMock = vi.mocked(nodesApi.fetchNodeCatalog)
        const importNodeManifestMock = vi.mocked(nodesApi.importNodeManifest)
        const fetchWorkflowTemplatesMock = vi.mocked(workflowsApi.fetchWorkflowTemplates)

        const initialManifest = createNodeManifest()
        fetchNodeCatalogMock.mockResolvedValue({ nodes: [initialManifest] })
        fetchWorkflowTemplatesMock.mockResolvedValue({ templates: [] })
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

    it('renders nodes/templates split and routes add/load actions to workflow intents', async () => {
        const fetchNodeCatalogMock = vi.mocked(nodesApi.fetchNodeCatalog)
        const fetchWorkflowTemplatesMock = vi.mocked(workflowsApi.fetchWorkflowTemplates)
        fetchNodeCatalogMock.mockResolvedValue({
            nodes: [
                createNodeManifest({ id: 'PROMPT', name: 'Prompt Node', category: 'prompt' }),
                createNodeManifest({ id: 'RECURSIVE_SPLIT_CHUNKS', name: 'Recursive Split', category: 'text_segmentation' }),
            ],
        })
        fetchWorkflowTemplatesMock.mockResolvedValue({
            templates: [
                {
                    id: 'template-1',
                    name: 'Simple Chat',
                    description: 'A test template',
                    tags: ['chat'],
                    definition: {
                        schema_version: 2,
                        nodes: [],
                        connections: [],
                        metadata: {},
                    },
                    visual_graph: {
                        schema_version: 2,
                        nodes: [],
                        groups: [],
                        comments: [],
                    },
                    required_nodes: [createNodeManifest({ id: 'PROMPT', name: 'Prompt Node' })],
                    metadata: {},
                },
            ],
        })

        render(<NodesPage />)
        await screen.findByText('Prompt Node')
        await screen.findByText('Simple Chat')

        expect(screen.getByRole('heading', { name: 'Node preview' })).toBeInTheDocument()
        expect(screen.getByRole('heading', { name: 'Templates' })).toBeInTheDocument()

        await userEvent.click(screen.getByRole('button', { name: 'Add Prompt Node to canvas' }))
        expect(navigateMock).toHaveBeenCalledWith('/', {
            state: {
                workflow_intent: {
                    type: 'add-node',
                    node_id: 'PROMPT',
                    node_version: 1,
                },
            },
        })

        await userEvent.click(screen.getByRole('button', { name: 'Use template' }))
        expect(navigateMock).toHaveBeenCalledWith('/', {
            state: {
                workflow_intent: {
                    type: 'load-template',
                    template: expect.objectContaining({ id: 'template-1' }),
                },
            },
        })
    })

    it('shows prompt and text segmentation category filters', async () => {
        const fetchNodeCatalogMock = vi.mocked(nodesApi.fetchNodeCatalog)
        const fetchWorkflowTemplatesMock = vi.mocked(workflowsApi.fetchWorkflowTemplates)
        fetchNodeCatalogMock.mockResolvedValue({
            nodes: [
                createNodeManifest({ id: 'PROMPT', name: 'Prompt Node', category: 'prompt' }),
                createNodeManifest({ id: 'RECURSIVE_SPLIT_CHUNKS', name: 'Recursive Split', category: 'text_segmentation' }),
            ],
        })
        fetchWorkflowTemplatesMock.mockResolvedValue({ templates: [] })

        render(<NodesPage />)
        await screen.findByText('Prompt Node')

        expect(screen.getByRole('checkbox', { name: /Prompt/i })).toBeInTheDocument()
        expect(screen.getByRole('checkbox', { name: /Text Segmentation/i })).toBeInTheDocument()
    })
})
