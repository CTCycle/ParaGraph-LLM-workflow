import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import * as nodesApi from '../app/services/nodesApi'
import type { NodeManifest } from '../workflow/schema/types'
import DatabaseSchemaPage from './DatabaseSchemaPage'

vi.mock('@xyflow/react', () => ({
    Background: () => <div data-testid="schema-background" />,
    BackgroundVariant: { Dots: 'dots' },
    MarkerType: { ArrowClosed: 'arrowclosed' },
    ReactFlow: ({ nodes, edges, children }: { nodes: unknown[]; edges: unknown[]; children: ReactNode }) => (
        <div data-testid="schema-flow" data-node-count={nodes.length} data-edge-count={edges.length}>
            {children}
            {nodes.map((node) => {
                const item = node as { id: string; data: { table: { name: string } } }
                return <div key={item.id}>{item.data.table.name}</div>
            })}
        </div>
    ),
}))

vi.mock('../app/services/nodesApi', () => ({
    inspectDatabaseSchema: vi.fn(),
}))

const sqlFileManifest: NodeManifest = {
    id: 'SQL_FILE_DATABASE',
    version: 1,
    name: 'Embedded SQL Database',
    category: 'database',
    description: 'Test database',
    inputs: [],
    outputs: [],
    controllers: [],
    parameters: [],
    ui: { default_width: 360, accent_color: '#2877c7', collapsed_by_default: false },
    runtime: {
        executor_key: 'sql_file_database',
        cacheable: false,
        deterministic: false,
        side_effecting: false,
    },
}

describe('DatabaseSchemaPage', () => {
    it('loads schema from route state and renders table graph', async () => {
        vi.mocked(nodesApi.inspectDatabaseSchema).mockResolvedValue({
            tables: [
                {
                    name: 'users',
                    columns: [
                        {
                            name: 'id',
                            type: 'INTEGER',
                            nullable: false,
                            default: null,
                            primary_key: true,
                        },
                    ],
                    primary_key: { name: null, columns: ['id'] },
                    foreign_keys: [],
                    indexes: [],
                },
            ],
        })

        render(
            <MemoryRouter
                initialEntries={[
                    {
                        pathname: '/database-schema/db_1',
                        state: {
                            nodeId: 'db_1',
                            manifest: sqlFileManifest,
                            parameters: { db_path: 'demo.sqlite' },
                        },
                    },
                ]}
            >
                <Routes>
                    <Route path="/database-schema/:nodeId" element={<DatabaseSchemaPage />} />
                    <Route path="/" element={<div>Canvas</div>} />
                </Routes>
            </MemoryRouter>,
        )

        await screen.findByText('users')
        expect(screen.getByTestId('schema-flow')).toHaveAttribute('data-node-count', '1')
        expect(nodesApi.inspectDatabaseSchema).toHaveBeenCalledWith('SQL_FILE_DATABASE', 1, { db_path: 'demo.sqlite' })
    })

    it('back button returns to the canvas route', async () => {
        vi.mocked(nodesApi.inspectDatabaseSchema).mockResolvedValue({ tables: [] })

        render(
            <MemoryRouter
                initialEntries={[
                    {
                        pathname: '/database-schema/db_1',
                        state: {
                            nodeId: 'db_1',
                            manifest: sqlFileManifest,
                            parameters: {},
                        },
                    },
                ]}
            >
                <Routes>
                    <Route path="/database-schema/:nodeId" element={<DatabaseSchemaPage />} />
                    <Route path="/" element={<div>Canvas</div>} />
                </Routes>
            </MemoryRouter>,
        )

        await userEvent.click(screen.getByRole('button', { name: 'Back to canvas' }))
        await waitFor(() => expect(screen.getByText('Canvas')).toBeInTheDocument())
    })
})
