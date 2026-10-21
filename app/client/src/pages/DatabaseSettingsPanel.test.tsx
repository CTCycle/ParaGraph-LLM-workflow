import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as databaseApi from '../app/services/databaseApi'
import DatabaseSettingsPanel from './DatabaseSettingsPanel'

vi.mock('../app/services/databaseApi', () => ({
    fetchDatabaseConfiguration: vi.fn(),
    testDatabaseConfiguration: vi.fn(),
    applyDatabaseConfiguration: vi.fn(),
}))

const connectedStatus: databaseApi.DatabaseConfigurationStatus = {
    backend: 'sqlite',
    database_path: 'database.db',
    insert_batch_size: 1000,
    resolved_path: 'C:/data/database.db',
    connected: true,
    error: null,
}

describe('DatabaseSettingsPanel', () => {
    beforeEach(() => vi.clearAllMocks())

    it('tests and applies a SQLite database then refreshes provider state', async () => {
        const onDatabaseChanged = vi.fn().mockResolvedValue(undefined)
        vi.mocked(databaseApi.fetchDatabaseConfiguration).mockResolvedValue(connectedStatus)
        vi.mocked(databaseApi.testDatabaseConfiguration).mockResolvedValue({
            ok: true,
            message: 'Connection is available',
        })
        vi.mocked(databaseApi.applyDatabaseConfiguration).mockResolvedValue({
            ...connectedStatus,
            database_path: 'alternate.db',
            resolved_path: 'C:/data/alternate.db',
            insert_batch_size: 24,
        })
        render(<DatabaseSettingsPanel onDatabaseChanged={onDatabaseChanged} />)

        await screen.findByText('Connected')
        await userEvent.clear(screen.getByRole('textbox', { name: 'Database file path' }))
        await userEvent.type(screen.getByRole('textbox', { name: 'Database file path' }), 'alternate.db')
        await userEvent.clear(screen.getByRole('spinbutton', { name: 'Insert batch size' }))
        await userEvent.type(screen.getByRole('spinbutton', { name: 'Insert batch size' }), '24')

        await userEvent.click(screen.getByRole('button', { name: 'Test Connection' }))
        expect(await screen.findByText('Connection is available')).toBeInTheDocument()
        await userEvent.click(screen.getByRole('button', { name: 'Apply' }))

        expect(await screen.findByText(/No settings or other data were copied/)).toBeInTheDocument()
        expect(databaseApi.applyDatabaseConfiguration).toHaveBeenCalledWith({
            backend: 'sqlite',
            database_path: 'alternate.db',
            insert_batch_size: 24,
        })
        expect(onDatabaseChanged).toHaveBeenCalledOnce()
        expect(screen.getByText('C:/data/alternate.db')).toBeInTheDocument()
    })

    it('keeps the form available when the active database is unavailable', async () => {
        vi.mocked(databaseApi.fetchDatabaseConfiguration).mockResolvedValue({
            ...connectedStatus,
            connected: false,
            resolved_path: null,
            error: 'Database file is unavailable',
        })
        vi.mocked(databaseApi.applyDatabaseConfiguration).mockResolvedValue(connectedStatus)
        render(<DatabaseSettingsPanel onDatabaseChanged={vi.fn().mockResolvedValue(undefined)} />)

        expect(await screen.findByRole('alert')).toHaveTextContent('Database unavailable: Database file is unavailable')
        expect(screen.getByRole('textbox', { name: 'Database file path' })).toBeEnabled()
        expect(screen.getByRole('button', { name: 'Apply' })).toBeEnabled()
    })
})
