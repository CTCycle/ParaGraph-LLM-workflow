import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import * as workflowApi from '../app/services/configurationsApi'
import * as providersApi from '../app/services/providersApi'
import ConfigurationsPage from './ConfigurationsPage'
import { createConfigurationPayload, createProviderCatalog } from '../test/fixtures'

vi.mock('../app/services/configurationsApi', () => ({
    fetchConfigurations: vi.fn(),
    listConfigurationProfiles: vi.fn(),
    loadConfigurationProfile: vi.fn(),
    saveConfigurationProfile: vi.fn(),
    pingOllama: vi.fn(),
    pingProvider: vi.fn(),
}))

vi.mock('../app/services/providersApi', () => ({
    fetchProviderCatalog: vi.fn(),
}))

describe('ConfigurationsPage profile modal flows', () => {
    it('loads profiles, loads a selected profile, and saves a named profile', async () => {
        const fetchConfigurationsMock = vi.mocked(workflowApi.fetchConfigurations)
        const listConfigurationProfilesMock = vi.mocked(workflowApi.listConfigurationProfiles)
        const loadConfigurationProfileMock = vi.mocked(workflowApi.loadConfigurationProfile)
        const saveConfigurationProfileMock = vi.mocked(workflowApi.saveConfigurationProfile)
        const pingOllamaMock = vi.mocked(workflowApi.pingOllama)
        const pingProviderMock = vi.mocked(workflowApi.pingProvider)
        const fetchProviderCatalogMock = vi.mocked(providersApi.fetchProviderCatalog)

        fetchConfigurationsMock.mockResolvedValue(createConfigurationPayload())
        fetchProviderCatalogMock.mockResolvedValue(createProviderCatalog())
        listConfigurationProfilesMock.mockResolvedValue({
            session_name: 'default',
            profiles: [
                {
                    profile_name: 'workstation',
                    created_at: '2026-03-24T10:00:00Z',
                    updated_at: '2026-03-24T10:00:00Z',
                },
                {
                    profile_name: 'travel',
                    created_at: '2026-03-23T09:00:00Z',
                    updated_at: '2026-03-23T09:00:00Z',
                },
            ],
        })
        loadConfigurationProfileMock.mockResolvedValue(
            createConfigurationPayload({
                provider_configurations: [
                    { provider: 'openai', api_key: 'sk-loaded', has_api_key: true, base_url: null, metadata: {} },
                    { provider: 'huggingface', api_key: 'hf-loaded', has_api_key: true, base_url: null, metadata: {} },
                ],
            }),
        )
        saveConfigurationProfileMock.mockResolvedValue(createConfigurationPayload())
        pingOllamaMock.mockResolvedValue({
            ok: true,
            message: 'Ollama reachable (12 models)',
            base_url: 'http://127.0.0.1:11434',
            model_count: 12,
        })
        pingProviderMock.mockResolvedValue({
            ok: true,
            provider: 'lmstudio',
            message: 'lmstudio reachable (1 model discovered).',
            base_url: 'http://localhost:1234/v1',
            model_count: 1,
        })

        render(<ConfigurationsPage />)

        await screen.findByText('Configuration loaded')

        await userEvent.click(screen.getByRole('button', { name: 'Load' }))
        const loadDialog = await screen.findByRole('dialog', { name: 'Load configuration' })
        await userEvent.click(within(loadDialog).getByRole('button', { name: 'Load' }))

        await screen.findByText("Loaded configuration 'workstation'")
        expect(loadConfigurationProfileMock).toHaveBeenCalledWith('workstation', 'default')

        await userEvent.click(screen.getByRole('button', { name: 'Save' }))
        const saveDialog = await screen.findByRole('dialog', { name: 'Save configuration' })

        await userEvent.click(within(saveDialog).getByRole('button', { name: 'Save' }))
        await expect(within(saveDialog).getByRole('alert')).toHaveTextContent('Enter a configuration name')

        await userEvent.click(within(saveDialog).getByRole('button', { name: 'Cancel' }))
        await waitFor(() => {
            expect(screen.queryByRole('dialog', { name: 'Save configuration' })).toBeNull()
        })
        expect(screen.queryByText('Enter a configuration name')).toBeNull()

        await userEvent.click(screen.getByRole('button', { name: 'Save' }))
        const reopenedSaveDialog = await screen.findByRole('dialog', { name: 'Save configuration' })

        await userEvent.type(within(reopenedSaveDialog).getByRole('textbox', { name: 'Configuration name' }), 'team profile')
        await userEvent.click(within(reopenedSaveDialog).getByRole('button', { name: 'Save' }))

        await screen.findByText("Saved configuration 'team profile'")

        const statusButtons = screen.getAllByRole('button', { name: 'Check Status' })
        await userEvent.click(statusButtons[0])
        await screen.findByText('Ollama reachable (12 models)')
        await userEvent.click(statusButtons[1])
        await screen.findByText('lmstudio reachable (1 model discovered).')

        await waitFor(() => {
            expect(saveConfigurationProfileMock).toHaveBeenCalledWith('team profile', expect.any(Object))
        })
        expect(saveConfigurationProfileMock).toHaveBeenCalledWith(
            'team profile',
            expect.objectContaining({
                provider_configurations: expect.arrayContaining([
                    expect.objectContaining({
                        provider: 'openai',
                        api_key: null,
                        has_api_key: true,
                    }),
                    expect.objectContaining({
                        provider: 'huggingface',
                        api_key: null,
                        has_api_key: true,
                    }),
                ]),
            }),
        )
        expect(saveConfigurationProfileMock.mock.calls[0]?.[1]).not.toHaveProperty('access_keys')
    }, 15_000)

    it('renders ollama connectivity failures with strong error styling and alert semantics', async () => {
        const fetchConfigurationsMock = vi.mocked(workflowApi.fetchConfigurations)
        const pingOllamaMock = vi.mocked(workflowApi.pingOllama)
        const fetchProviderCatalogMock = vi.mocked(providersApi.fetchProviderCatalog)

        fetchConfigurationsMock.mockResolvedValue(createConfigurationPayload())
        fetchProviderCatalogMock.mockResolvedValue(createProviderCatalog())
        pingOllamaMock.mockRejectedValue(new Error('Unable to reach Ollama at http://127.0.0.1:1'))

        render(<ConfigurationsPage />)

        await screen.findByText('Configuration loaded')
        await userEvent.click(screen.getAllByRole('button', { name: 'Check Status' })[0])

        const alert = await screen.findByRole('alert')
        expect(alert).toHaveClass('config-panel-note-error')
        expect(alert).toHaveTextContent('Error:')
    })
})
