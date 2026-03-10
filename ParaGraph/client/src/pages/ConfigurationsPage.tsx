import { useEffect, useMemo, useState } from 'react'

import { fetchConfigurations, saveConfigurations } from '../app/services/workflowApi'
import { AccessKeyConfiguration, AppConfigurationPayload } from '../workflow/schema/types'
import './ConfigurationsPage.css'

type CloudProvider = 'openai' | 'gemini' | 'anthropic'

type ProviderCredential = {
    apiKey: string
    baseUrl: string
}

const DEFAULT_SESSION_NAME = 'default'
const CLOUD_PROVIDER_OPTIONS: Array<{ value: CloudProvider; label: string }> = [
    { value: 'openai', label: 'OpenAI' },
    { value: 'gemini', label: 'Gemini' },
    { value: 'anthropic', label: 'Anthropic' },
]

const EMPTY_CLOUD_CREDENTIALS: Record<CloudProvider, ProviderCredential> = {
    openai: { apiKey: '', baseUrl: '' },
    gemini: { apiKey: '', baseUrl: '' },
    anthropic: { apiKey: '', baseUrl: '' },
}

function normalizeText(value: string | null | undefined): string {
    return (value || '').trim()
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
        anthropic: { ...EMPTY_CLOUD_CREDENTIALS.anthropic },
    }

    let huggingFaceKey = ''
    let selectedCloudProvider: CloudProvider = 'openai'

    payload.access_keys.forEach((item) => {
        if (item.provider === 'huggingface') {
            huggingFaceKey = normalizeText(item.api_key)
            return
        }
        if (item.provider === 'openai' || item.provider === 'gemini' || item.provider === 'anthropic') {
            cloudCredentials[item.provider] = {
                apiKey: normalizeText(item.api_key),
                baseUrl: normalizeText(item.base_url),
            }
            if (!selectedCloudProvider || normalizeText(item.api_key)) {
                selectedCloudProvider = item.provider
            }
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
    const [isLoading, setIsLoading] = useState(true)
    const [isSaving, setIsSaving] = useState(false)

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

    async function loadConfigurations(): Promise<void> {
        setIsLoading(true)
        try {
            const payload = await fetchConfigurations(DEFAULT_SESSION_NAME)
            applyPayload(payload)
            setStatusMessage('Configurations loaded')
        } catch (error) {
            setStatusMessage(error instanceof Error ? error.message : 'Unable to load configurations')
        } finally {
            setIsLoading(false)
        }
    }

    useEffect(() => {
        void loadConfigurations()
    }, [])

    function buildPayload(): AppConfigurationPayload {
        const accessKeys: AccessKeyConfiguration[] = CLOUD_PROVIDER_OPTIONS.map((option) => ({
            provider: option.value,
            api_key: normalizeText(cloudCredentials[option.value].apiKey) || null,
            base_url: normalizeText(cloudCredentials[option.value].baseUrl) || null,
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

    async function handleSave(): Promise<void> {
        setIsSaving(true)
        try {
            const saved = await saveConfigurations(buildPayload())
            applyPayload(saved)
            setStatusMessage('Configurations saved')
        } catch (error) {
            setStatusMessage(error instanceof Error ? error.message : 'Unable to save configurations')
        } finally {
            setIsSaving(false)
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
                <p className="config-page-eyebrow">Configuration</p>
                <h1>Provider and runtime settings</h1>
                <p className="config-page-lede">Store access keys and local inference defaults for your current workspace.</p>
            </header>

            {statusMessage && <div className="config-page-banner">{statusMessage}</div>}

            <div className="config-page-layout">
                <div className="config-page-left-column">
                    <section className="config-panel">
                        <div className="config-panel-header">
                            <div>
                                <h2>Access Keys</h2>
                                <p>Cloud provider + Hugging Face credentials.</p>
                            </div>
                            <div className="config-panel-actions">
                                <button type="button" onClick={() => void loadConfigurations()} disabled={isLoading || isSaving}>
                                    Load
                                </button>
                                <button type="button" onClick={() => void handleSave()} disabled={isLoading || isSaving}>
                                    {isSaving ? 'Saving...' : 'Save'}
                                </button>
                            </div>
                        </div>

                        <div className="config-panel-fields">
                            <label>
                                <span>Cloud Provider</span>
                                <select
                                    value={selectedCloudProvider}
                                    onChange={(event) => setSelectedCloudProvider(event.target.value as CloudProvider)}
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
                                <span>Base URL (optional)</span>
                                <input
                                    type="text"
                                    value={currentCloudCredentials.baseUrl}
                                    placeholder="https://api.example.com/v1"
                                    onChange={(event) => updateCurrentCloudCredential('baseUrl', event.target.value)}
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
                    </section>

                    <section className="config-panel">
                        <div className="config-panel-header">
                            <div>
                                <h2>Ollama</h2>
                                <p>Local provider defaults used by model nodes.</p>
                            </div>
                        </div>

                        <div className="config-panel-fields">
                            <label>
                                <span>Base URL</span>
                                <input
                                    type="text"
                                    value={ollamaBaseUrl}
                                    onChange={(event) => setOllamaBaseUrl(event.target.value)}
                                />
                            </label>

                            <label>
                                <span>Chat Model</span>
                                <input
                                    type="text"
                                    value={ollamaChatModel}
                                    onChange={(event) => setOllamaChatModel(event.target.value)}
                                />
                            </label>

                            <label>
                                <span>Embedding Model</span>
                                <input
                                    type="text"
                                    value={ollamaEmbeddingModel}
                                    onChange={(event) => setOllamaEmbeddingModel(event.target.value)}
                                />
                            </label>
                        </div>
                    </section>
                </div>

                <aside className="config-page-right-column">
                    <section className="config-panel config-panel-empty" aria-hidden="true">
                        <h2>Right Column</h2>
                        <p>Reserved for upcoming configuration modules.</p>
                    </section>
                </aside>
            </div>
        </section>
    )
}

