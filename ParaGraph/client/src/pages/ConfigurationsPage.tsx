import { useEffect, useMemo, useState } from 'react'

import {
    fetchConfigurations,
    listConfigurationProfiles,
    loadConfigurationProfile,
    pingOllama,
    saveConfigurationProfile,
} from '../app/services/workflowApi'
import { AccessKeyConfiguration, AppConfigurationPayload, ConfigurationProfileSummary } from '../workflow/schema/types'
import './ConfigurationsPage.css'

type CloudProvider = 'openai' | 'gemini' | 'claude'

type ProviderCredential = {
    apiKey: string
}

const DEFAULT_SESSION_NAME = 'default'
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
    if (value === 'anthropic') {
        return 'claude'
    }
    return 'openai'
}

function mapPayloadToForm(payload: AppConfigurationPayload): {
    cloudCredentials: Record<CloudProvider, ProviderCredential>
    huggingFaceKey: string
    ollamaBaseUrl: string
    ollamaChatModel: string
    ollamaEmbeddingModel: string
    selectedCloudProvider: CloudProvider
} {
    const cloudCredentials: Record<CloudProvider, ProviderCredential> = {
        openai: { ...EMPTY_CLOUD_CREDENTIALS.openai },
        gemini: { ...EMPTY_CLOUD_CREDENTIALS.gemini },
        claude: { ...EMPTY_CLOUD_CREDENTIALS.claude },
    }

    let huggingFaceKey = ''
    let selectedCloudProvider: CloudProvider = 'openai'

    payload.access_keys.forEach((item) => {
        if (item.provider === 'huggingface') {
            huggingFaceKey = normalizeText(item.api_key)
            return
        }

        const provider = toCloudProvider(item.provider)
        cloudCredentials[provider] = {
            apiKey: normalizeText(item.api_key),
        }
        if (normalizeText(item.api_key)) {
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
    const [selectedCloudProvider, setSelectedCloudProvider] = useState<CloudProvider>('openai')
    const [cloudCredentials, setCloudCredentials] =
        useState<Record<CloudProvider, ProviderCredential>>(EMPTY_CLOUD_CREDENTIALS)
    const [huggingFaceKey, setHuggingFaceKey] = useState('')
    const [ollamaBaseUrl, setOllamaBaseUrl] = useState('http://127.0.0.1:11434')
    const [ollamaChatModel, setOllamaChatModel] = useState('llama3.2')
    const [ollamaEmbeddingModel, setOllamaEmbeddingModel] = useState('nomic-embed-text')
    const [statusMessage, setStatusMessage] = useState<string | null>(null)
    const [ollamaStatus, setOllamaStatus] = useState<string | null>(null)
    const [isLoading, setIsLoading] = useState(true)
    const [isSavingProfile, setIsSavingProfile] = useState(false)
    const [isPingingOllama, setIsPingingOllama] = useState(false)

    const [isLoadModalOpen, setIsLoadModalOpen] = useState(false)
    const [isSaveModalOpen, setIsSaveModalOpen] = useState(false)
    const [profiles, setProfiles] = useState<ConfigurationProfileSummary[]>([])
    const [isLoadingProfiles, setIsLoadingProfiles] = useState(false)
    const [isLoadingProfile, setIsLoadingProfile] = useState(false)
    const [selectedProfileName, setSelectedProfileName] = useState('')
    const [saveProfileName, setSaveProfileName] = useState('')

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
            setStatusMessage(error instanceof Error ? error.message : 'Unable to load configuration')
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
            api_key: normalizeText(cloudCredentials[option.value].apiKey) || null,
            base_url: null,
            metadata: {},
        }))

        accessKeys.push({
            provider: 'huggingface',
            api_key: normalizeText(huggingFaceKey) || null,
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
        setIsLoadModalOpen(true)
        setIsLoadingProfiles(true)
        setStatusMessage(null)
        try {
            const response = await listConfigurationProfiles(DEFAULT_SESSION_NAME)
            setProfiles(response.profiles)
            setSelectedProfileName(response.profiles[0]?.profile_name ?? '')
        } catch (error) {
            setStatusMessage(error instanceof Error ? error.message : 'Unable to list saved configurations')
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
            setIsLoadModalOpen(false)
        } catch (error) {
            setStatusMessage(error instanceof Error ? error.message : 'Unable to load selected configuration')
        } finally {
            setIsLoadingProfile(false)
        }
    }

    async function handleSaveProfile(): Promise<void> {
        const profileName = normalizeText(saveProfileName)
        if (!profileName) {
            setStatusMessage('Enter a configuration name')
            return
        }

        setIsSavingProfile(true)
        setStatusMessage(null)
        try {
            const payload = await saveConfigurationProfile(profileName, buildPayload())
            applyPayload(payload)
            setStatusMessage(`Saved configuration '${profileName}'`)
            setIsSaveModalOpen(false)
            setSaveProfileName('')
        } catch (error) {
            setStatusMessage(error instanceof Error ? error.message : 'Unable to save configuration')
        } finally {
            setIsSavingProfile(false)
        }
    }

    async function handlePingOllama(): Promise<void> {
        setIsPingingOllama(true)
        setOllamaStatus(null)
        try {
            const response = await pingOllama(normalizeText(ollamaBaseUrl) || null)
            setOllamaStatus(response.message)
        } catch (error) {
            setOllamaStatus(error instanceof Error ? error.message : 'Unable to check Ollama status')
        } finally {
            setIsPingingOllama(false)
        }
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
                <h1>Provider and runtime settings</h1>
                <p className="config-page-lede">Store access keys and local inference defaults for your current workspace.</p>
            </header>

            <div className="config-page-layout">
                <div className="config-page-left-column">
                    <section className="config-panel">
                        <div className="config-panel-header">
                            <div>
                                <h2>Ollama configuration</h2>
                                <p>Set the local Ollama base URL used by runtime nodes.</p>
                            </div>
                            <div className="config-panel-actions">
                                <button type="button" onClick={() => void handlePingOllama()} disabled={isPingingOllama || isLoading}>
                                    {isPingingOllama ? 'Checking...' : 'Check Status'}
                                </button>
                            </div>
                        </div>

                        <div className="config-panel-fields">
                            <label>
                                <span>Base URL</span>
                                <input
                                    type="text"
                                    value={ollamaBaseUrl}
                                    onChange={(event) => setOllamaBaseUrl(event.target.value)}
                                    placeholder="http://127.0.0.1:11434"
                                />
                            </label>
                        </div>

                        {ollamaStatus && <p className="config-panel-note">{ollamaStatus}</p>}
                    </section>

                    <section className="config-panel">
                        <div className="config-panel-header">
                            <div>
                                <h2>Access Keys</h2>
                                <p>Cloud provider and Hugging Face credentials.</p>
                            </div>
                            <div className="config-panel-actions">
                                <button type="button" onClick={() => void openLoadModal()} disabled={isLoading || isLoadingProfiles}>
                                    Load
                                </button>
                                <button
                                    type="button"
                                    onClick={() => {
                                        setSaveProfileName('')
                                        setIsSaveModalOpen(true)
                                    }}
                                    disabled={isLoading || isSavingProfile}
                                >
                                    Save
                                </button>
                            </div>
                        </div>

                        <div className="config-panel-fields">
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
                                    onChange={(event) => updateCurrentCloudCredential('apiKey', event.target.value)}
                                />
                            </label>

                            <label>
                                <span>Hugging Face API Key</span>
                                <input
                                    type="password"
                                    value={huggingFaceKey}
                                    placeholder="hf_..."
                                    onChange={(event) => setHuggingFaceKey(event.target.value)}
                                />
                            </label>
                        </div>

                        {statusMessage && <p className="config-panel-note">{statusMessage}</p>}
                    </section>
                </div>

                <aside className="config-page-right-column">
                    <section className="config-panel config-panel-empty" aria-hidden="true">
                        <h2>Right Column</h2>
                        <p>Reserved for upcoming configuration modules.</p>
                    </section>
                </aside>
            </div>

            {isLoadModalOpen && (
                <div className="config-modal-backdrop" role="presentation">
                    <div className="config-modal" role="dialog" aria-modal="true" aria-label="Load configuration">
                        <h3>Load configuration</h3>
                        <p>Choose one saved configuration profile.</p>
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
                        <div className="config-modal-actions">
                            <button type="button" onClick={() => setIsLoadModalOpen(false)} disabled={isLoadingProfile}>
                                Cancel
                            </button>
                            <button
                                type="button"
                                onClick={() => void handleLoadSelectedProfile()}
                                disabled={!selectedProfileName || isLoadingProfile || isLoadingProfiles}
                            >
                                {isLoadingProfile ? 'Loading...' : 'Load'}
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {isSaveModalOpen && (
                <div className="config-modal-backdrop" role="presentation">
                    <div className="config-modal" role="dialog" aria-modal="true" aria-label="Save configuration">
                        <h3>Save configuration</h3>
                        <p>Name this configuration profile.</p>
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
                        <div className="config-modal-actions">
                            <button type="button" onClick={() => setIsSaveModalOpen(false)} disabled={isSavingProfile}>
                                Cancel
                            </button>
                            <button type="button" onClick={() => void handleSaveProfile()} disabled={isSavingProfile}>
                                {isSavingProfile ? 'Saving...' : 'Save'}
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </section>
    )
}

