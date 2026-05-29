import { useEffect, useMemo, useState } from 'react'

import { useErrorMessage } from '../app/hooks/useErrorMessage'
import { usePageMetadata } from '../app/hooks/usePageMetadata'
import { useModalState } from '../app/hooks/useModalState'
import {
    fetchConfigurations,
    listConfigurationProfiles,
    loadConfigurationProfile,
    pingOllama,
    saveConfigurationProfile,
} from '../app/services/configurationsApi'
import ModalActionButtons from '../components/ModalActionButtons'
import ModalDialog from '../components/ModalDialog'
import { AccessKeyConfiguration, AppConfigurationPayload, ConfigurationProfileSummary } from '../workflow/schema/types'
import './ConfigurationsPage.css'

type CloudProvider = 'openai' | 'gemini' | 'claude'

type ProviderCredential = {
    apiKey: string
}

type ConfigurationFormValues = {
    cloudCredentials: Record<CloudProvider, ProviderCredential>
    huggingFaceKey: string
    ollamaBaseUrl: string
    ollamaChatModel: string
    ollamaEmbeddingModel: string
    selectedCloudProvider: CloudProvider
}

type InlineStatusTone = 'neutral' | 'success' | 'error'

const DEFAULT_SESSION_NAME = 'default'
const MASKED_API_KEY_VALUE = '__PG_MASKED_API_KEY__'
const MASKED_API_KEY_DISPLAY = '********'
const CLOUD_PROVIDER_OPTIONS: Array<{ value: CloudProvider; label: string }> = [
    { value: 'openai', label: 'OpenAI' },
    { value: 'gemini', label: 'Gemini' },
    { value: 'claude', label: 'Claude' },
]

const EMPTY_CLOUD_CREDENTIALS: Record<CloudProvider, ProviderCredential> = {
    openai: { apiKey: '' },
    gemini: { apiKey: '' },
    claude: { apiKey: '' },
}

function normalizeText(value: string | null | undefined): string {
    return (value || '').trim()
}

function toCloudProvider(value: string): CloudProvider {
    if (value === 'openai' || value === 'gemini' || value === 'claude') {
        return value
    }
    return 'openai'
}

function normalizeApiKeyField(value: string | null | undefined): string {
    const normalized = normalizeText(value)
    if (!normalized) {
        return ''
    }
    if (normalized === MASKED_API_KEY_VALUE) {
        return MASKED_API_KEY_DISPLAY
    }
    return normalized
}

function toApiKeyPayload(value: string): string | null {
    const normalized = normalizeText(value)
    if (!normalized) {
        return null
    }
    if (normalized === MASKED_API_KEY_DISPLAY) {
        return MASKED_API_KEY_VALUE
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

function mapPayloadToForm(payload: AppConfigurationPayload): ConfigurationFormValues {
    const cloudCredentials: Record<CloudProvider, ProviderCredential> = {
        openai: { ...EMPTY_CLOUD_CREDENTIALS.openai },
        gemini: { ...EMPTY_CLOUD_CREDENTIALS.gemini },
        claude: { ...EMPTY_CLOUD_CREDENTIALS.claude },
    }

    let huggingFaceKey = ''
    let selectedCloudProvider: CloudProvider = 'openai'

    payload.access_keys.forEach((item) => {
        if (item.provider === 'huggingface') {
            huggingFaceKey = normalizeApiKeyField(item.api_key)
            return
        }

        const provider = toCloudProvider(item.provider)
        cloudCredentials[provider] = {
            apiKey: normalizeApiKeyField(item.api_key),
        }
        if (normalizeApiKeyField(item.api_key)) {
            selectedCloudProvider = provider
        }
    })

    return {
        cloudCredentials,
        huggingFaceKey,
        ollamaBaseUrl: normalizeText(payload.ollama.base_url),
        ollamaChatModel: normalizeText(payload.ollama.chat_model),
        ollamaEmbeddingModel: normalizeText(payload.ollama.embedding_model),
        selectedCloudProvider,
    }
}

export default function ConfigurationsPage() {
    usePageMetadata({
        title: 'Configurations',
        description:
            'Configure Ollama defaults and provider access keys for ParaGraph workflow execution in your current session.',
    })
    const [selectedCloudProvider, setSelectedCloudProvider] = useState<CloudProvider>('openai')
    const [cloudCredentials, setCloudCredentials] =
        useState<Record<CloudProvider, ProviderCredential>>(EMPTY_CLOUD_CREDENTIALS)
    const [huggingFaceKey, setHuggingFaceKey] = useState('')
    const [ollamaBaseUrl, setOllamaBaseUrl] = useState('http://127.0.0.1:11434')
    const [ollamaChatModel, setOllamaChatModel] = useState('llama3.2')
    const [ollamaEmbeddingModel, setOllamaEmbeddingModel] = useState('nomic-embed-text')
    const [statusMessage, setStatusMessage] = useState<string | null>(null)
    const [ollamaStatus, setOllamaStatus] = useState<string | null>(null)
    const [ollamaStatusTone, setOllamaStatusTone] = useState<InlineStatusTone>('neutral')
    const [isLoading, setIsLoading] = useState(true)
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

    const currentCloudCredentials = useMemo(
        () => cloudCredentials[selectedCloudProvider],
        [cloudCredentials, selectedCloudProvider],
    )

    function applyPayload(payload: AppConfigurationPayload): void {
        const mapped = mapPayloadToForm(payload)
        setCloudCredentials(mapped.cloudCredentials)
        setHuggingFaceKey(mapped.huggingFaceKey)
        setOllamaBaseUrl(mapped.ollamaBaseUrl || 'http://127.0.0.1:11434')
        setOllamaChatModel(mapped.ollamaChatModel || 'llama3.2')
        setOllamaEmbeddingModel(mapped.ollamaEmbeddingModel || 'nomic-embed-text')
        setSelectedCloudProvider(mapped.selectedCloudProvider)
    }

    async function loadCurrentConfiguration(): Promise<void> {
        setIsLoading(true)
        try {
            const payload = await fetchConfigurations(DEFAULT_SESSION_NAME)
            applyPayload(payload)
            setStatusMessage('Configuration loaded')
        } catch (error) {
            setStatusMessage(getErrorMessage(error, 'Unable to load configuration'))
        } finally {
            setIsLoading(false)
        }
    }

    useEffect(() => {
        void loadCurrentConfiguration()
    }, [])

    function buildPayload(): AppConfigurationPayload {
        const accessKeys: AccessKeyConfiguration[] = CLOUD_PROVIDER_OPTIONS.map((option) => ({
            provider: option.value,
            api_key: toApiKeyPayload(cloudCredentials[option.value].apiKey),
            base_url: null,
            metadata: {},
        }))

        accessKeys.push({
            provider: 'huggingface',
            api_key: toApiKeyPayload(huggingFaceKey),
            base_url: null,
            metadata: {},
        })

        return {
            session_name: DEFAULT_SESSION_NAME,
            access_keys: accessKeys,
            ollama: {
                base_url: normalizeText(ollamaBaseUrl) || 'http://127.0.0.1:11434',
                chat_model: normalizeText(ollamaChatModel) || 'llama3.2',
                embedding_model: normalizeText(ollamaEmbeddingModel) || 'nomic-embed-text',
            },
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

    function openSaveModal(): void {
        setSaveProfileName('')
        setSaveProfileError(null)
        saveModal.open()
    }

    function updateCurrentCloudCredential(field: keyof ProviderCredential, value: string): void {
        setCloudCredentials((current) => ({
            ...current,
            [selectedCloudProvider]: {
                ...current[selectedCloudProvider],
                [field]: value,
            },
        }))
    }

    return (
        <section className="config-page">
            <header className="config-page-header">
                <h1>Runtime and Access Settings</h1>
                <p className="config-page-lede">Manage local Ollama defaults and cloud credentials used by this ParaGraph session.</p>
            </header>

            <div className="config-page-layout">
                <section className="config-panel config-panel-column">
                    <div className="config-panel-header">
                        <div>
                            <h2>Ollama</h2>
                            <p>Set the local runtime endpoint used for model discovery and execution.</p>
                        </div>
                        <div className="config-panel-actions">
                            <button type="button" onClick={() => void handlePingOllama()} disabled={isPingingOllama || isLoading}>
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
                                placeholder="http://127.0.0.1:11434"
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
                            <h2>Access Keys</h2>
                            <p>Manage API keys for cloud providers and Hugging Face.</p>
                        </div>
                        <div className="config-panel-actions">
                            <button type="button" onClick={() => void openLoadModal()} disabled={isLoading || isLoadingProfiles}>
                                Load
                            </button>
                            <button
                                type="button"
                                onClick={() => {
                                    openSaveModal()
                                }}
                                disabled={isLoading || isSavingProfile}
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
                                onChange={(event) => setSelectedCloudProvider(toCloudProvider(event.target.value))}
                            >
                                {CLOUD_PROVIDER_OPTIONS.map((option) => (
                                    <option key={option.value} value={option.value}>
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
                                placeholder="sk-..."
                                autoComplete="new-password"
                                onChange={(event) => updateCurrentCloudCredential('apiKey', event.target.value)}
                            />
                        </label>

                        <label>
                            <span>Hugging Face API Key</span>
                            <input
                                type="password"
                                value={huggingFaceKey}
                                placeholder="hf_..."
                                autoComplete="new-password"
                                onChange={(event) => setHuggingFaceKey(event.target.value)}
                            />
                        </label>
                    </form>

                    {statusMessage && <p className="config-panel-note">{statusMessage}</p>}
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



