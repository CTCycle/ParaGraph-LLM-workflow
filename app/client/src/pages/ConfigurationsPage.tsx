import { useEffect, useMemo, useState } from 'react'

import { useErrorMessage } from '../app/hooks/useErrorMessage'
import { usePageMetadata } from '../app/hooks/usePageMetadata'
import { useModalState } from '../app/hooks/useModalState'
import { GUIDANCE_CONTENT_VERSIONS } from '../guidance/guidanceContent'
import { useGuidance } from '../guidance/GuidanceContext'
import FeatureTip from '../guidance/FeatureTip'
import {
    fetchConfigurations,
    listConfigurationProfiles,
    loadConfigurationProfile,
    pingOllama,
    pingProvider,
    saveConfigurationProfile,
} from '../app/services/configurationsApi'
import { fetchProviderCatalog } from '../app/services/providersApi'
import ModalActionButtons from '../components/ModalActionButtons'
import ModalDialog from '../components/ModalDialog'
import {
    AppConfigurationPayload,
    ConfigurationProfileSummary,
    ProviderCapability,
} from '../workflow/schema/types'
import './ConfigurationsPage.css'

type ProviderCredential = {
    apiKey: string
    baseUrl: string
    hasApiKey: boolean
    apiKeyDirty: boolean
}

type LocalProviderSettings = ProviderCredential & {
    chatModel: string
    embeddingModel: string
}

type ConfigurationFormValues = {
    cloudCredentials: Record<string, ProviderCredential>
    localProviders: Record<string, LocalProviderSettings>
    huggingFaceKey: string
    huggingFaceHasApiKey: boolean
    huggingFaceKeyDirty: boolean
    ollamaBaseUrl: string
    ollamaChatModel: string
    ollamaEmbeddingModel: string
    selectedCloudProvider: string
    selectedLocalProvider: string
}

type InlineStatusTone = 'neutral' | 'success' | 'error'

const DEFAULT_SESSION_NAME = 'default'
function emptyProviderCredential(): ProviderCredential {
    return { apiKey: '', baseUrl: '', hasApiKey: false, apiKeyDirty: false }
}

function localProviderDefaults(metadata: ProviderCapability): LocalProviderSettings {
    return {
        ...emptyProviderCredential(),
        baseUrl: metadata.default_base_url || '',
        chatModel: metadata.default_chat_model || '',
        embeddingModel: metadata.default_embedding_model || '',
    }
}

function normalizeText(value: string | null | undefined): string {
    return (value || '').trim()
}

function metadataText(metadata: Record<string, unknown>, key: string): string {
    const value = metadata[key]
    return typeof value === 'string' ? value : ''
}

function normalizeApiKeyField(value: string | null | undefined): string {
    return normalizeText(value)
}

function toApiKeyPayload(value: string): string | null {
    const normalized = normalizeText(value)
    if (!normalized) {
        return null
    }
    return normalized
}

function formatOllamaStatusMessage(message: string, baseUrl: string): string {
    const baseMessage = normalizeText(message)
    const isConnectionIssue = /Unable to reach Ollama|ECONNREFUSED|WinError 10061|connection refused/i.test(baseMessage)
    if (!isConnectionIssue) {
        return baseMessage || 'Unable to check Ollama status'
    }

    const target = normalizeText(baseUrl) || 'the configured Ollama URL'
    return `Ollama unreachable. Check that Ollama is running at ${target}.`
}

function mapPayloadToForm(
    payload: AppConfigurationPayload,
    catalog: ProviderCapability[],
): ConfigurationFormValues {
    const cloudCredentials: Record<string, ProviderCredential> = {}
    const localProviders: Record<string, LocalProviderSettings> = {}
    const ollamaMetadata = catalog.find((item) => item.provider === 'ollama')
    let ollamaDefaults = ollamaMetadata
        ? localProviderDefaults(ollamaMetadata)
        : { ...emptyProviderCredential(), chatModel: '', embeddingModel: '' }

    for (const item of catalog) {
        if (item.configuration_kind === 'cloud') {
            cloudCredentials[item.provider] = emptyProviderCredential()
        }
        if (item.configuration_kind === 'local' && item.provider !== 'ollama') {
            localProviders[item.provider] = localProviderDefaults(item)
        }
    }

    let huggingFaceKey = ''
    let huggingFaceHasApiKey = false
    let huggingFaceKeyDirty = false
    let selectedCloudProvider = catalog.find(
        (item) => item.configuration_kind === 'cloud',
    )?.provider || ''
    const selectedLocalProvider = catalog.find(
        (item) => item.configuration_kind === 'local' && item.provider !== 'ollama',
    )?.provider || ''

    for (const item of payload.provider_configurations) {
        const hasApiKey = Boolean(item.api_key) || item.has_api_key
        const apiKey = normalizeApiKeyField(item.api_key)
        if (item.provider === 'huggingface') {
            huggingFaceKey = apiKey
            huggingFaceHasApiKey = hasApiKey
            continue
        }

        const metadata = catalog.find((candidate) => candidate.provider === item.provider)
        if (!metadata) {
            continue
        }
        if (metadata.configuration_kind === 'local' && item.provider !== 'ollama') {
            const defaults = localProviders[item.provider] || localProviderDefaults(metadata)
            localProviders[item.provider] = {
                ...defaults,
                apiKey,
                hasApiKey,
                baseUrl: normalizeText(item.base_url) || defaults.baseUrl,
                chatModel: metadataText(item.metadata, 'chat_model') || defaults.chatModel,
                embeddingModel:
                    metadataText(item.metadata, 'embedding_model') || defaults.embeddingModel,
            }
            continue
        }
        if (item.provider === 'ollama') {
            ollamaDefaults = {
                ...ollamaDefaults,
                apiKey,
                hasApiKey,
                baseUrl: normalizeText(item.base_url) || ollamaDefaults.baseUrl,
                chatModel: metadataText(item.metadata, 'chat_model') || ollamaDefaults.chatModel,
                embeddingModel:
                    metadataText(item.metadata, 'embedding_model') || ollamaDefaults.embeddingModel,
            }
            continue
        }
        if (metadata.configuration_kind === 'cloud') {
            cloudCredentials[item.provider] = {
                apiKey,
                hasApiKey,
                baseUrl: normalizeText(item.base_url),
                apiKeyDirty: false,
            }
            if (hasApiKey) {
                selectedCloudProvider = item.provider
            }
        }
    }

    return {
        cloudCredentials,
        localProviders,
        huggingFaceKey,
        huggingFaceHasApiKey,
        huggingFaceKeyDirty,
        ollamaBaseUrl: ollamaDefaults.baseUrl,
        ollamaChatModel: ollamaDefaults.chatModel,
        ollamaEmbeddingModel: ollamaDefaults.embeddingModel,
        selectedCloudProvider,
        selectedLocalProvider,
    }
}

export default function ConfigurationsPage() {
    usePageMetadata({
        title: 'Configurations',
        description:
            'Configure provider endpoints and credentials for ParaGraph workflow execution in your current session.',
    })
    const { shouldShow, markSeen, markDismissed } = useGuidance()
    const [providerCatalog, setProviderCatalog] = useState<ProviderCapability[]>([])
    const [selectedCloudProvider, setSelectedCloudProvider] = useState('')
    const [selectedLocalProvider, setSelectedLocalProvider] = useState('')
    const [cloudCredentials, setCloudCredentials] =
        useState<Record<string, ProviderCredential>>({})
    const [localProviders, setLocalProviders] =
        useState<Record<string, LocalProviderSettings>>({})
    const [huggingFaceKey, setHuggingFaceKey] = useState('')
    const [huggingFaceHasApiKey, setHuggingFaceHasApiKey] = useState(false)
    const [huggingFaceKeyDirty, setHuggingFaceKeyDirty] = useState(false)
    const [ollamaBaseUrl, setOllamaBaseUrl] = useState('')
    const [ollamaChatModel, setOllamaChatModel] = useState('')
    const [ollamaEmbeddingModel, setOllamaEmbeddingModel] = useState('')
    const [statusMessage, setStatusMessage] = useState<string | null>(null)
    const [ollamaStatus, setOllamaStatus] = useState<string | null>(null)
    const [ollamaStatusTone, setOllamaStatusTone] = useState<InlineStatusTone>('neutral')
    const [localStatus, setLocalStatus] = useState<string | null>(null)
    const [localStatusTone, setLocalStatusTone] = useState<InlineStatusTone>('neutral')
    const [isPingingLocal, setIsPingingLocal] = useState(false)
    const [isLoading, setIsLoading] = useState(true)
    const [isLoadingCatalog, setIsLoadingCatalog] = useState(true)
    const [isSavingProfile, setIsSavingProfile] = useState(false)
    const [isPingingOllama, setIsPingingOllama] = useState(false)
    const getErrorMessage = useErrorMessage()

    const loadModal = useModalState(false)
    const saveModal = useModalState(false)
    const [profiles, setProfiles] = useState<ConfigurationProfileSummary[]>([])
    const [isLoadingProfiles, setIsLoadingProfiles] = useState(false)
    const [isLoadingProfile, setIsLoadingProfile] = useState(false)
    const [selectedProfileName, setSelectedProfileName] = useState('')
    const [saveProfileName, setSaveProfileName] = useState('')
    const [saveProfileError, setSaveProfileError] = useState<string | null>(null)
    const [isSetupTipVisible, setIsSetupTipVisible] = useState(false)

    const currentCloudCredentials = useMemo(
        () => cloudCredentials[selectedCloudProvider] || emptyProviderCredential(),
        [cloudCredentials, selectedCloudProvider],
    )
    const currentLocalProvider = useMemo(
        () => localProviders[selectedLocalProvider] || {
            ...emptyProviderCredential(),
            chatModel: '',
            embeddingModel: '',
        },
        [localProviders, selectedLocalProvider],
    )

    const cloudProviderOptions = useMemo(
        () => providerCatalog.filter((item) => item.configuration_kind === 'cloud'),
        [providerCatalog],
    )
    const localProviderOptions = useMemo(
        () => providerCatalog.filter(
            (item) => item.configuration_kind === 'local' && item.provider !== 'ollama',
        ),
        [providerCatalog],
    )
    const ollamaProvider = useMemo(
        () => providerCatalog.find((item) => item.provider === 'ollama'),
        [providerCatalog],
    )
    const huggingFaceProvider = useMemo(
        () => providerCatalog.find((item) => item.provider === 'huggingface'),
        [providerCatalog],
    )

    function applyPayload(payload: AppConfigurationPayload): void {
        const mapped = mapPayloadToForm(payload, providerCatalog)
        setCloudCredentials(mapped.cloudCredentials)
        setLocalProviders(mapped.localProviders)
        setHuggingFaceKey(mapped.huggingFaceKey)
        setHuggingFaceHasApiKey(mapped.huggingFaceHasApiKey)
        setHuggingFaceKeyDirty(mapped.huggingFaceKeyDirty)
        setOllamaBaseUrl(mapped.ollamaBaseUrl)
        setOllamaChatModel(mapped.ollamaChatModel)
        setOllamaEmbeddingModel(mapped.ollamaEmbeddingModel)
        setSelectedCloudProvider(mapped.selectedCloudProvider)
        setSelectedLocalProvider(mapped.selectedLocalProvider)
    }

    async function loadCurrentConfiguration(): Promise<void> {
        setIsLoading(true)
        setIsLoadingCatalog(true)
        try {
            const [catalog, payload] = await Promise.all([
                fetchProviderCatalog(),
                fetchConfigurations(DEFAULT_SESSION_NAME),
            ])
            setProviderCatalog(catalog.providers)
            const mapped = mapPayloadToForm(payload, catalog.providers)
            setCloudCredentials(mapped.cloudCredentials)
            setLocalProviders(mapped.localProviders)
            setHuggingFaceKey(mapped.huggingFaceKey)
            setHuggingFaceHasApiKey(mapped.huggingFaceHasApiKey)
            setHuggingFaceKeyDirty(mapped.huggingFaceKeyDirty)
            setOllamaBaseUrl(mapped.ollamaBaseUrl)
            setOllamaChatModel(mapped.ollamaChatModel)
            setOllamaEmbeddingModel(mapped.ollamaEmbeddingModel)
            setSelectedCloudProvider(mapped.selectedCloudProvider)
            setSelectedLocalProvider(mapped.selectedLocalProvider)
            setStatusMessage('Configuration loaded')
        } catch (error) {
            setStatusMessage(getErrorMessage(error, 'Unable to load configuration'))
        } finally {
            setIsLoadingCatalog(false)
            setIsLoading(false)
        }
    }

    useEffect(() => {
        void loadCurrentConfiguration()
    }, [])

    useEffect(() => {
        if (isLoading || statusMessage !== 'Configuration loaded' || !shouldShow('config-setup', GUIDANCE_CONTENT_VERSIONS['config-setup'])) {
            return
        }
        setIsSetupTipVisible(true)
        markSeen('config-setup', GUIDANCE_CONTENT_VERSIONS['config-setup'])
    }, [isLoading, markSeen, shouldShow, statusMessage])

    function buildPayload(): AppConfigurationPayload {
        const huggingFaceApiKey = toApiKeyPayload(huggingFaceKey)
        const huggingFaceConfiguration = {
            provider: huggingFaceProvider?.provider || 'huggingface',
            api_key: huggingFaceKeyDirty ? huggingFaceApiKey : null,
            has_api_key: huggingFaceKeyDirty
                ? Boolean(huggingFaceApiKey)
                : huggingFaceHasApiKey,
            base_url: null,
            metadata: {},
        }
        const providerConfigurations = providerCatalog.map((metadata) => {
            if (metadata.provider === 'ollama') {
                return {
                    provider: metadata.provider,
                    api_key: null,
                    has_api_key: false,
                    base_url: normalizeText(ollamaBaseUrl) || null,
                    metadata: {
                        ...(normalizeText(ollamaChatModel)
                            ? { chat_model: normalizeText(ollamaChatModel) }
                            : {}),
                        ...(normalizeText(ollamaEmbeddingModel)
                            ? { embedding_model: normalizeText(ollamaEmbeddingModel) }
                            : {}),
                    },
                }
            }
            if (metadata.provider === huggingFaceConfiguration.provider) {
                return huggingFaceConfiguration
            }

            const credential = cloudCredentials[metadata.provider]
            const localSettings = localProviders[metadata.provider]
            const fields = localSettings || credential
            const apiKey = fields ? toApiKeyPayload(fields.apiKey) : null
            return {
                provider: metadata.provider,
                api_key: fields?.apiKeyDirty ? apiKey : null,
                has_api_key: fields?.apiKeyDirty ? Boolean(apiKey) : Boolean(fields?.hasApiKey),
                base_url: normalizeText(fields?.baseUrl) || null,
                metadata: localSettings
                    ? {
                        ...(normalizeText(localSettings.chatModel)
                            ? { chat_model: normalizeText(localSettings.chatModel) }
                            : {}),
                        ...(normalizeText(localSettings.embeddingModel)
                            ? { embedding_model: normalizeText(localSettings.embeddingModel) }
                            : {}),
                    }
                    : {},
            }
        })

        if (!providerConfigurations.some((item) => item.provider === huggingFaceConfiguration.provider)) {
            providerConfigurations.push(huggingFaceConfiguration)
        }

        return {
            session_name: DEFAULT_SESSION_NAME,
            provider_configurations: providerConfigurations,
        }
    }

    async function openLoadModal(): Promise<void> {
        loadModal.open()
        setIsLoadingProfiles(true)
        setStatusMessage(null)
        try {
            const response = await listConfigurationProfiles(DEFAULT_SESSION_NAME)
            setProfiles(response.profiles)
            setSelectedProfileName(response.profiles[0]?.profile_name ?? '')
        } catch (error) {
            setStatusMessage(getErrorMessage(error, 'Unable to list saved configurations'))
        } finally {
            setIsLoadingProfiles(false)
        }
    }

    async function handleLoadSelectedProfile(): Promise<void> {
        if (!selectedProfileName) {
            return
        }

        setIsLoadingProfile(true)
        setStatusMessage(null)
        try {
            const payload = await loadConfigurationProfile(selectedProfileName, DEFAULT_SESSION_NAME)
            applyPayload(payload)
            setStatusMessage(`Loaded configuration '${selectedProfileName}'`)
            loadModal.close()
        } catch (error) {
            setStatusMessage(getErrorMessage(error, 'Unable to load selected configuration'))
        } finally {
            setIsLoadingProfile(false)
        }
    }

    async function handleSaveProfile(): Promise<void> {
        const profileName = normalizeText(saveProfileName)
        if (!profileName) {
            setSaveProfileError('Enter a configuration name')
            return
        }

        setSaveProfileError(null)
        setIsSavingProfile(true)
        setStatusMessage(null)
        try {
            const payload = await saveConfigurationProfile(profileName, buildPayload())
            applyPayload(payload)
            setStatusMessage(`Saved configuration '${profileName}'`)
            saveModal.close()
            setSaveProfileName('')
        } catch (error) {
            setStatusMessage(getErrorMessage(error, 'Unable to save configuration'))
        } finally {
            setIsSavingProfile(false)
        }
    }

    async function handlePingOllama(): Promise<void> {
        setIsPingingOllama(true)
        setOllamaStatus(null)
        setOllamaStatusTone('neutral')
        try {
            const response = await pingOllama(normalizeText(ollamaBaseUrl) || null)
            setOllamaStatus(formatOllamaStatusMessage(response.message, ollamaBaseUrl))
            setOllamaStatusTone(response.ok ? 'success' : 'error')
        } catch (error) {
            setOllamaStatus(
                formatOllamaStatusMessage(
                    error instanceof Error ? error.message : 'Unable to check Ollama status',
                    ollamaBaseUrl,
                ),
            )
            setOllamaStatusTone('error')
        } finally {
            setIsPingingOllama(false)
        }
    }

    async function handlePingLocalProvider(): Promise<void> {
        const provider = selectedLocalProvider
        const settings = localProviders[provider] || {
            ...emptyProviderCredential(),
            chatModel: '',
            embeddingModel: '',
        }
        setIsPingingLocal(true)
        setLocalStatus(null)
        setLocalStatusTone('neutral')
        try {
            const response = await pingProvider(
                provider,
                normalizeText(settings.baseUrl) || null,
                toApiKeyPayload(settings.apiKey),
            )
            setLocalStatus(response.message)
            setLocalStatusTone(response.ok ? 'success' : 'error')
        } catch (error) {
            setLocalStatus(error instanceof Error ? error.message : 'Unable to check provider status')
            setLocalStatusTone('error')
        } finally {
            setIsPingingLocal(false)
        }
    }

    function openSaveModal(): void {
        setSaveProfileName('')
        setSaveProfileError(null)
        saveModal.open()
    }

    function updateCurrentCloudCredential(
        field: 'apiKey' | 'baseUrl',
        value: string,
    ): void {
        setCloudCredentials((current) => ({
            ...current,
            [selectedCloudProvider]: {
                ...(current[selectedCloudProvider] || emptyProviderCredential()),
                [field]: value,
                ...(field === 'apiKey' ? { apiKeyDirty: true } : {}),
            },
        }))
    }

    function updateCurrentLocalProvider(
        field: 'apiKey' | 'baseUrl' | 'chatModel' | 'embeddingModel',
        value: string,
    ): void {
        setLocalProviders((current) => ({
            ...current,
            [selectedLocalProvider]: {
                ...(current[selectedLocalProvider] || {
                    ...emptyProviderCredential(),
                    chatModel: '',
                    embeddingModel: '',
                }),
                [field]: value,
                ...(field === 'apiKey' ? { apiKeyDirty: true } : {}),
            },
        }))
    }

    function updateHuggingFaceKey(value: string): void {
        setHuggingFaceKey(value)
        setHuggingFaceKeyDirty(true)
    }

    return (
        <section className="config-page">
            <header className="config-page-header">
                <h1>Runtime and Provider Settings</h1>
                <p className="config-page-lede">Manage provider endpoints and credentials used by this ParaGraph session.</p>
                {isSetupTipVisible && (
                    <FeatureTip
                        title="Set up a provider before running"
                        onDismiss={() => {
                            setIsSetupTipVisible(false)
                            markDismissed('config-setup', GUIDANCE_CONTENT_VERSIONS['config-setup'])
                        }}
                        actions={(
                            <a href="/" className="guidance-primary-button">
                                Open workflow
                            </a>
                        )}
                    >
                        <p>Choose a local endpoint or cloud key, check its status, then select the provider and model in the workflow. Save a profile if you switch setups.</p>
                    </FeatureTip>
                )}
            </header>

            <div className="config-page-layout">
                <section className="config-panel config-panel-column">
                    <div className="config-panel-header">
                        <div>
                            <h2>Ollama</h2>
                            <p>Set the local runtime endpoint used for model discovery and execution.</p>
                        </div>
                        <div className="config-panel-actions">
                            <button type="button" onClick={() => void handlePingOllama()} disabled={isPingingOllama || isLoading || !ollamaProvider}>
                                {isPingingOllama ? 'Checking...' : 'Check Status'}
                            </button>
                        </div>
                    </div>

                    <form
                        className="config-panel-fields"
                        onSubmit={(event) => {
                            event.preventDefault()
                        }}
                    >
                        <label>
                            <span>Base URL</span>
                            <input
                                type="text"
                                value={ollamaBaseUrl}
                                onChange={(event) => setOllamaBaseUrl(event.target.value)}
                                placeholder={ollamaProvider?.default_base_url || 'Provider default'}
                            />
                        </label>
                    </form>

                    {ollamaStatus && (
                        <p
                            className={`config-panel-note ${ollamaStatusTone === 'error'
                                ? 'config-panel-note-error'
                                : ollamaStatusTone === 'success'
                                    ? 'config-panel-note-success'
                                    : ''}`}
                            role={ollamaStatusTone === 'error' ? 'alert' : 'status'}
                        >
                            {ollamaStatusTone === 'error' ? 'Error: ' : ''}
                            {ollamaStatus}
                        </p>
                    )}
                </section>

                <section className="config-panel config-panel-column">
                    <div className="config-panel-header">
                        <div>
                            <h2>Provider Configurations</h2>
                            <p>Manage API keys and endpoints from the backend provider catalog.</p>
                        </div>
                        <div className="config-panel-actions">
                            <button type="button" onClick={() => void openLoadModal()} disabled={isLoading || isLoadingProfiles || isLoadingCatalog}>
                                Load
                            </button>
                            <button
                                type="button"
                                onClick={() => {
                                    openSaveModal()
                                }}
                                disabled={isLoading || isSavingProfile || isLoadingCatalog}
                            >
                                Save
                            </button>
                        </div>
                    </div>

                    <form
                        className="config-panel-fields"
                        autoComplete="off"
                        onSubmit={(event) => {
                            event.preventDefault()
                        }}
                    >
                        <label>
                            <span>Cloud Provider</span>
                            <select
                                value={selectedCloudProvider}
                                onChange={(event) => setSelectedCloudProvider(event.target.value)}
                            >
                                {cloudProviderOptions.map((option) => (
                                    <option key={option.provider} value={option.provider}>
                                        {option.label}
                                    </option>
                                ))}
                            </select>
                        </label>

                        <label>
                            <span>API Key</span>
                            <input
                                type="password"
                                value={currentCloudCredentials.apiKey}
                                placeholder={currentCloudCredentials.hasApiKey ? 'Saved API key — leave blank to keep' : 'Enter API key'}
                                autoComplete="new-password"
                                onChange={(event) => updateCurrentCloudCredential('apiKey', event.target.value)}
                            />
                        </label>

                        <label>
                            <span>Base URL</span>
                            <input
                                type="text"
                                value={currentCloudCredentials.baseUrl}
                                placeholder={cloudProviderOptions.find((item) => item.provider === selectedCloudProvider)?.default_base_url || 'Provider default'}
                                onChange={(event) => updateCurrentCloudCredential('baseUrl', event.target.value)}
                            />
                        </label>

                        <label>
                            <span>Hugging Face API Key</span>
                            <input
                                type="password"
                                value={huggingFaceKey}
                                placeholder={huggingFaceHasApiKey ? 'Saved API key — leave blank to keep' : 'Enter Hugging Face API key'}
                                autoComplete="new-password"
                                onChange={(event) => updateHuggingFaceKey(event.target.value)}
                            />
                        </label>
                    </form>

                    {statusMessage && <p className="config-panel-note">{statusMessage}</p>}
                </section>

                <section className="config-panel config-panel-column">
                    <div className="config-panel-header">
                        <div>
                            <h2>Local OpenAI-Compatible Providers</h2>
                            <p>Configure LM Studio and llama.cpp endpoints for local model execution.</p>
                        </div>
                        <div className="config-panel-actions">
                            <button type="button" onClick={() => void handlePingLocalProvider()} disabled={isPingingLocal || isLoading || !selectedLocalProvider}>
                                {isPingingLocal ? 'Checking...' : 'Check Status'}
                            </button>
                        </div>
                    </div>

                    <form
                        className="config-panel-fields"
                        autoComplete="off"
                        onSubmit={(event) => {
                            event.preventDefault()
                        }}
                    >
                        <label>
                            <span>Provider</span>
                            <select
                                value={selectedLocalProvider}
                                onChange={(event) => setSelectedLocalProvider(event.target.value)}
                            >
                                {localProviderOptions.map((option) => (
                                    <option key={option.provider} value={option.provider}>
                                        {option.label}
                                    </option>
                                ))}
                            </select>
                        </label>

                        <label>
                            <span>Base URL</span>
                            <input
                                type="text"
                                value={currentLocalProvider.baseUrl}
                                placeholder={localProviderOptions.find((item) => item.provider === selectedLocalProvider)?.default_base_url || 'Provider default'}
                                onChange={(event) => updateCurrentLocalProvider('baseUrl', event.target.value)}
                            />
                        </label>

                        <label>
                            <span>API Key</span>
                            <input
                                type="password"
                                value={currentLocalProvider.apiKey}
                                placeholder="Optional"
                                autoComplete="new-password"
                                onChange={(event) => updateCurrentLocalProvider('apiKey', event.target.value)}
                            />
                        </label>

                        <label>
                            <span>Chat Model</span>
                            <input
                                type="text"
                                value={currentLocalProvider.chatModel}
                                placeholder={localProviderOptions.find((item) => item.provider === selectedLocalProvider)?.default_chat_model || 'Provider default'}
                                onChange={(event) => updateCurrentLocalProvider('chatModel', event.target.value)}
                            />
                        </label>

                        <label>
                            <span>Embedding Model</span>
                            <input
                                type="text"
                                value={currentLocalProvider.embeddingModel}
                                placeholder={localProviderOptions.find((item) => item.provider === selectedLocalProvider)?.default_embedding_model || 'Provider default'}
                                onChange={(event) => updateCurrentLocalProvider('embeddingModel', event.target.value)}
                            />
                        </label>
                    </form>

                    {localStatus && (
                        <p
                            className={`config-panel-note ${localStatusTone === 'error'
                                ? 'config-panel-note-error'
                                : localStatusTone === 'success'
                                    ? 'config-panel-note-success'
                                    : ''}`}
                            role={localStatusTone === 'error' ? 'alert' : 'status'}
                        >
                            {localStatusTone === 'error' ? 'Error: ' : ''}
                            {localStatus}
                        </p>
                    )}
                </section>
            </div>

            <ModalDialog
                isOpen={loadModal.isOpen}
                ariaLabel="Load configuration"
                title="Load configuration"
                description="Choose one saved configuration profile."
                onRequestClose={isLoadingProfile ? undefined : loadModal.close}
                actions={(
                    <ModalActionButtons
                        cancelLabel="Cancel"
                        confirmLabel={isLoadingProfile ? 'Loading...' : 'Load'}
                        onCancel={loadModal.close}
                        onConfirm={() => void handleLoadSelectedProfile()}
                        cancelDisabled={isLoadingProfile}
                        confirmDisabled={!selectedProfileName || isLoadingProfile || isLoadingProfiles}
                    />
                )}
            >
                <div className="config-modal-list">
                    {isLoadingProfiles && <p className="config-modal-empty">Loading...</p>}
                    {!isLoadingProfiles && profiles.length === 0 && (
                        <p className="config-modal-empty">No saved configurations found.</p>
                    )}
                    {!isLoadingProfiles &&
                        profiles.map((profile) => (
                            <label key={profile.profile_name} className="config-modal-option">
                                <input
                                    type="radio"
                                    name="configuration-profile"
                                    value={profile.profile_name}
                                    checked={selectedProfileName === profile.profile_name}
                                    onChange={(event) => setSelectedProfileName(event.target.value)}
                                />
                                <span>{profile.profile_name}</span>
                                <small>{new Date(profile.updated_at).toLocaleString()}</small>
                            </label>
                        ))}
                </div>
            </ModalDialog>

            <ModalDialog
                isOpen={saveModal.isOpen}
                ariaLabel="Save configuration"
                title="Save configuration"
                description="Name this configuration profile."
                onRequestClose={isSavingProfile ? undefined : saveModal.close}
                actions={(
                    <ModalActionButtons
                        cancelLabel="Cancel"
                        confirmLabel={isSavingProfile ? 'Saving...' : 'Save'}
                        onCancel={saveModal.close}
                        onConfirm={() => void handleSaveProfile()}
                        cancelDisabled={isSavingProfile}
                        confirmDisabled={isSavingProfile}
                    />
                )}
            >
                <label className="config-modal-input">
                    <span>Configuration name</span>
                    <input
                        type="text"
                        value={saveProfileName}
                        onChange={(event) => setSaveProfileName(event.target.value)}
                        placeholder="My setup"
                        maxLength={120}
                    />
                </label>
                {saveProfileError && (
                    <p className="config-modal-error" role="alert">
                        {saveProfileError}
                    </p>
                )}
            </ModalDialog>
        </section>
    )
}



