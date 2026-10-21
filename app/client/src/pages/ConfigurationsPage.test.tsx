import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import * as workflowApi from '../app/services/configurationsApi'
import * as providersApi from '../app/services/providersApi'
import ConfigurationsPage from './ConfigurationsPage'
import { createConfigurationPayload, createProviderCatalog } from '../test/fixtures'

function createRedactedConfigurationPayload() {
    const payload = createConfigurationPayload()
    return {
        ...payload,
        provider_configurations: payload.provider_configurations.map((item) => ({
            ...item,
            api_key: null,
        })),
    }
}

vi.mock('../app/services/configurationsApi', () => ({
    activateConfigurationProfile: vi.fn(),
    fetchConfigurations: vi.fn(),
    listConfigurationProfiles: vi.fn(),
    saveConfigurations: vi.fn(),
    saveConfigurationProfile: vi.fn(),
    pingOllama: vi.fn(),
    pingProvider: vi.fn(),
}))

vi.mock('../app/services/providersApi', () => ({
    fetchProviderCatalog: vi.fn(),
}))

describe('ConfigurationsPage settings persistence and profile flows', () => {
    it('loads profiles, loads a selected profile, and saves a named profile', async () => {
        const fetchConfigurationsMock = vi.mocked(workflowApi.fetchConfigurations)
        const listConfigurationProfilesMock = vi.mocked(workflowApi.listConfigurationProfiles)
        const activateConfigurationProfileMock = vi.mocked(workflowApi.activateConfigurationProfile)
        const saveConfigurationsMock = vi.mocked(workflowApi.saveConfigurations)
        const saveConfigurationProfileMock = vi.mocked(workflowApi.saveConfigurationProfile)
        const pingOllamaMock = vi.mocked(workflowApi.pingOllama)
        const pingProviderMock = vi.mocked(workflowApi.pingProvider)
        const fetchProviderCatalogMock = vi.mocked(providersApi.fetchProviderCatalog)

        fetchConfigurationsMock.mockResolvedValue(createConfigurationPayload())
        saveConfigurationsMock.mockImplementation(async (payload) => payload)
        activateConfigurationProfileMock.mockResolvedValue(createConfigurationPayload())
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
        expect(activateConfigurationProfileMock).toHaveBeenCalledWith('workstation', 'default')

        await userEvent.click(screen.getByRole('button', { name: 'Save profile' }))
        const saveDialog = await screen.findByRole('dialog', { name: 'Save configuration' })

        await userEvent.click(within(saveDialog).getByRole('button', { name: 'Save profile' }))
        await expect(within(saveDialog).getByRole('alert')).toHaveTextContent('Enter a configuration name')

        await userEvent.click(within(saveDialog).getByRole('button', { name: 'Cancel' }))
        await waitFor(() => {
            expect(screen.queryByRole('dialog', { name: 'Save configuration' })).toBeNull()
        })
        expect(screen.queryByText('Enter a configuration name')).toBeNull()

        await userEvent.click(screen.getByRole('button', { name: 'Save profile' }))
        const reopenedSaveDialog = await screen.findByRole('dialog', { name: 'Save configuration' })

        await userEvent.type(within(reopenedSaveDialog).getByRole('textbox', { name: 'Configuration name' }), 'team profile')
        await userEvent.click(within(reopenedSaveDialog).getByRole('button', { name: 'Save profile' }))

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

    it('automatically persists every provider setting after a short typing debounce', async () => {
        const user = userEvent.setup()
        const saveConfigurationsMock = vi.mocked(workflowApi.saveConfigurations)
        vi.mocked(workflowApi.fetchConfigurations).mockResolvedValue(createRedactedConfigurationPayload())
        vi.mocked(saveConfigurationsMock).mockImplementation(async (payload) => payload)
        vi.mocked(providersApi.fetchProviderCatalog).mockResolvedValue(createProviderCatalog())

        render(<ConfigurationsPage />)
        await screen.findByText('Configuration loaded')

        const baseUrls = screen.getAllByLabelText('Base URL')
        await user.clear(baseUrls[0]!)
        await user.type(baseUrls[0]!, 'http://localhost:11435')

        await user.selectOptions(screen.getByLabelText('Cloud Provider'), 'gemini')
        await user.type(screen.getAllByLabelText('API Key')[0]!, 'gemini-secret')
        await user.type(screen.getAllByLabelText('Base URL')[1]!, 'https://gemini.example/v1')
        await user.type(screen.getByLabelText('Hugging Face API Key'), 'hf-updated')

        await user.selectOptions(screen.getByLabelText('Provider'), 'lmstudio')
        const localBaseUrl = screen.getAllByLabelText('Base URL')[2]!
        await user.clear(localBaseUrl)
        await user.type(localBaseUrl, 'http://localhost:4321/v1')
        const apiKeys = screen.getAllByLabelText('API Key')
        await user.type(apiKeys[1]!, 'local-secret')
        const chatModel = screen.getByLabelText('Chat Model')
        await user.clear(chatModel)
        await user.type(chatModel, 'local-chat')
        const embeddingModel = screen.getByLabelText('Embedding Model')
        await user.clear(embeddingModel)
        await user.type(embeddingModel, 'local-embed')

        await waitFor(() => {
            expect(saveConfigurationsMock).toHaveBeenCalled()
            const latestPayload = saveConfigurationsMock.mock.calls[saveConfigurationsMock.mock.calls.length - 1]?.[0]
            expect(latestPayload?.provider_configurations).toEqual(expect.arrayContaining([
                expect.objectContaining({
                    provider: 'ollama',
                    base_url: 'http://localhost:11435',
                }),
                expect.objectContaining({
                    provider: 'gemini',
                    api_key: 'gemini-secret',
                    base_url: 'https://gemini.example/v1',
                }),
                expect.objectContaining({
                    provider: 'huggingface',
                    api_key: 'hf-updated',
                }),
                expect.objectContaining({
                    provider: 'lmstudio',
                    api_key: 'local-secret',
                    base_url: 'http://localhost:4321/v1',
                    metadata: { chat_model: 'local-chat', embedding_model: 'local-embed' },
                }),
            ]))
        })
        expect(await screen.findByText('Changes saved')).toHaveAttribute('role', 'status')
    }, 15_000)

    it('serializes rapid updates and sends the newest value after an in-flight save', async () => {
        const user = userEvent.setup()
        const saveConfigurationsMock = vi.mocked(workflowApi.saveConfigurations)
        let finishFirstSave!: (payload: ReturnType<typeof createConfigurationPayload>) => void
        saveConfigurationsMock
            .mockImplementationOnce(() => new Promise((resolve) => { finishFirstSave = resolve }))
            .mockImplementation(async (payload) => payload)
        vi.mocked(workflowApi.fetchConfigurations).mockResolvedValue(createConfigurationPayload())
        vi.mocked(providersApi.fetchProviderCatalog).mockResolvedValue(createProviderCatalog())

        render(<ConfigurationsPage />)
        await screen.findByText('Configuration loaded')
        const ollamaBaseUrl = screen.getAllByLabelText('Base URL')[0]!
        await user.clear(ollamaBaseUrl)
        await user.type(ollamaBaseUrl, 'http://localhost:11435')

        await waitFor(() => expect(saveConfigurationsMock).toHaveBeenCalledOnce(), { timeout: 2_000 })
        await user.clear(ollamaBaseUrl)
        await user.type(ollamaBaseUrl, 'http://localhost:11436')
        await new Promise((resolve) => window.setTimeout(resolve, 450))
        expect(saveConfigurationsMock).toHaveBeenCalledOnce()

        finishFirstSave(createConfigurationPayload())
        await waitFor(() => expect(saveConfigurationsMock).toHaveBeenCalledTimes(2))
        expect(saveConfigurationsMock.mock.calls[1]?.[0].provider_configurations).toEqual(expect.arrayContaining([
            expect.objectContaining({ provider: 'ollama', base_url: 'http://localhost:11436' }),
        ]))
    }, 15_000)

    it('keeps an edited value visible and reports persistence failures', async () => {
        const user = userEvent.setup()
        vi.mocked(workflowApi.fetchConfigurations).mockResolvedValue(createConfigurationPayload())
        vi.mocked(workflowApi.saveConfigurations).mockRejectedValue(new Error('Database is read-only'))
        vi.mocked(providersApi.fetchProviderCatalog).mockResolvedValue(createProviderCatalog())

        render(<ConfigurationsPage />)
        await screen.findByText('Configuration loaded')
        const ollamaBaseUrl = screen.getAllByLabelText('Base URL')[0]!
        await user.clear(ollamaBaseUrl)
        await user.type(ollamaBaseUrl, 'http://localhost:11435')

        expect(await screen.findByRole('alert')).toHaveTextContent('Database is read-only')
        expect(ollamaBaseUrl).toHaveValue('http://localhost:11435')
    }, 15_000)
})
