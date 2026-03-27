import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
    Check,
    HelpCircle,
    Download,
    ExternalLink,
    Globe,
    Lock,
    RefreshCw,
    Search,
    ShieldAlert,
    type LucideIcon,
} from 'lucide-react'

import { useDebouncedValue } from '../app/hooks/useDebouncedValue'
import { useKeyedFlags } from '../app/hooks/useKeyedFlags'
import { usePageMetadata } from '../app/hooks/usePageMetadata'
import {
    cancelHuggingFaceDownload,
    downloadHuggingFaceModel,
    fetchHuggingFaceModels,
    fetchOllamaLibraryModels,
    getHuggingFaceDownloadStatus,
    pullOllamaModel,
    type HuggingFaceModelQueryOptions,
} from '../app/services/workflowApi'
import {
    HuggingFaceDownloadJobStatus,
    HuggingFaceModelCatalogResponse,
    HuggingFaceModelDefinition,
    HuggingFaceModelDownloadStatusResponse,
    HuggingFaceSortBy,
    ModelVisibilityFilter,
    OllamaLibraryModelDefinition,
} from '../workflow/schema/types'
import CatalogColumnHeader from '../components/CatalogColumnHeader'
import RetryErrorNotice from '../components/RetryErrorNotice'
import './ModelsPage.css'

const HUGGINGFACE_PAGE_SIZE = 25
const SEARCH_DEBOUNCE_MS = 350

type OllamaModelFilter = 'all' | 'pulled' | 'unpulled'

const OLLAMA_MODEL_FILTERS: readonly OllamaModelFilter[] = ['all', 'pulled', 'unpulled']
const HUGGINGFACE_VISIBILITY_FILTERS: readonly ModelVisibilityFilter[] = ['all', 'public', 'private', 'gated']
const HUGGINGFACE_SORT_OPTIONS: readonly HuggingFaceSortBy[] = ['relevance', 'downloads', 'likes', 'updated']
const HF_DOWNLOAD_POLL_MS = 1000

type HuggingFaceDownloadState = {
    jobId: string
    status: HuggingFaceDownloadJobStatus
    progress: number
    downloadedBytes: number
    totalBytes: number | null
    message: string | null
}

function isOllamaModelFilter(value: string): value is OllamaModelFilter {
    return OLLAMA_MODEL_FILTERS.some((candidate) => candidate === value)
}

function parseOllamaModelFilter(value: string): OllamaModelFilter {
    return isOllamaModelFilter(value) ? value : 'all'
}

function isVisibilityFilter(value: string): value is ModelVisibilityFilter {
    return HUGGINGFACE_VISIBILITY_FILTERS.some((candidate) => candidate === value)
}

function parseVisibilityFilter(value: string): ModelVisibilityFilter {
    return isVisibilityFilter(value) ? value : 'all'
}

function isHuggingFaceSortBy(value: string): value is HuggingFaceSortBy {
    return HUGGINGFACE_SORT_OPTIONS.some((candidate) => candidate === value)
}

function parseHuggingFaceSortBy(value: string): HuggingFaceSortBy {
    return isHuggingFaceSortBy(value) ? value : 'relevance'
}

type VisibilityIconConfig = {
    icon: LucideIcon
    label: string
    className: string
}

const VISIBILITY_ICON_MAP: Record<HuggingFaceModelDefinition['visibility'], VisibilityIconConfig> = {
    public: { icon: Globe, label: 'Public', className: 'models-visibility-public' },
    private: { icon: Lock, label: 'Private', className: 'models-visibility-private' },
    gated: { icon: ShieldAlert, label: 'Gated', className: 'models-visibility-gated' },
    unknown: { icon: HelpCircle, label: 'Unknown', className: 'models-visibility-unknown' },
}

function formatMetric(value: number | null): string {
    if (typeof value !== 'number' || Number.isNaN(value)) {
        return 'N/A'
    }
    return new Intl.NumberFormat().format(value)
}

function formatBytes(value: number | null): string {
    if (typeof value !== 'number' || !Number.isFinite(value) || value < 0) {
        return 'Unknown'
    }

    if (value < 1024) {
        return `${value} B`
    }

    const units = ['KB', 'MB', 'GB', 'TB']
    let size = value / 1024
    let unitIndex = 0
    while (size >= 1024 && unitIndex < units.length - 1) {
        size /= 1024
        unitIndex += 1
    }

    return `${size.toFixed(size >= 100 ? 0 : size >= 10 ? 1 : 2)} ${units[unitIndex]}`
}

function formatModelSize(value: number | null): string {
    if (typeof value !== 'number' || !Number.isFinite(value) || value < 0) {
        return 'Size: N/A'
    }
    return `Size: ${formatBytes(value)}`
}

function escapeRegex(text: string): string {
    return text.replace(/[\\^$.*+?()[\]{}|]/g, '\\$&')
}

function trimOllamaDescription(modelName: string, description: string | null): string | null {
    if (!description) {
        return null
    }

    const cleanedDescription = description.trim()
    if (!cleanedDescription) {
        return null
    }

    const normalizedModelName = modelName.trim()
    if (!normalizedModelName) {
        return cleanedDescription
    }

    const prefixPattern = new RegExp(`^${escapeRegex(normalizedModelName)}(?:\\s*[-–—:|,]\\s*|\\s+)`, 'i')
    const withoutPrefix = cleanedDescription.replace(prefixPattern, '').trim()
    return withoutPrefix || cleanedDescription
}

function mergeFilterOptions(options: string[], selected: string): string[] {
    const values = new Set(options.map((item) => item.trim()).filter((item) => item.length > 0))
    const normalizedSelected = selected.trim()
    if (normalizedSelected) {
        values.add(normalizedSelected)
    }
    return Array.from(values).sort((left, right) => left.localeCompare(right))
}

function formatCatalogError(error: unknown, catalogName: string): string {
    const fallback = `Unable to load ${catalogName} models`
    if (!(error instanceof Error)) {
        return fallback
    }

    const detail = error.message || fallback
    if (detail.includes('404')) {
        return `${catalogName} endpoints are unavailable on the running backend. Restart ParaGraph backend and refresh this page.`
    }
    return detail
}

function buildHuggingFaceQueryKey(query: HuggingFaceModelQueryOptions): string {
    return JSON.stringify({
        search: query.search ?? '',
        task: query.task ?? '',
        library: query.library ?? '',
        author: query.author ?? '',
        visibility: query.visibility ?? 'all',
        sort: query.sort ?? 'relevance',
        pageSize: query.pageSize ?? HUGGINGFACE_PAGE_SIZE,
    })
}

function flattenCachedRows(
    pages: Map<number, HuggingFaceModelCatalogResponse> | undefined,
    targetPage: number,
): HuggingFaceModelDefinition[] {
    if (!pages || pages.size === 0) {
        return []
    }

    const rows: HuggingFaceModelDefinition[] = []
    for (let page = 1; page <= targetPage; page += 1) {
        const pagePayload = pages.get(page)
        if (!pagePayload) {
            break
        }
        rows.push(...pagePayload.models)
    }
    return rows
}

export default function ModelsPage() {
    usePageMetadata({
        title: 'Models Explorer',
        description:
            'Browse Ollama and Hugging Face model catalogs with search, filters, and fast refresh for ParaGraph workflows.',
    })

    const [ollamaModels, setOllamaModels] = useState<OllamaLibraryModelDefinition[]>([])
    const [ollamaLoading, setOllamaLoading] = useState(true)
    const [ollamaError, setOllamaError] = useState<string | null>(null)
    const [ollamaMessage, setOllamaMessage] = useState<string | null>(null)
    const [ollamaSearch, setOllamaSearch] = useState('')
    const [ollamaFilter, setOllamaFilter] = useState<OllamaModelFilter>('all')
    const { mark: markPullingModel, clear: clearPullingModel, has: hasPullingModel } = useKeyedFlags()

    const [hfSearchInput, setHfSearchInput] = useState('')
    const [hfTask, setHfTask] = useState('')
    const [hfLibrary, setHfLibrary] = useState('')
    const [hfAuthor, setHfAuthor] = useState('')
    const [hfVisibility, setHfVisibility] = useState<ModelVisibilityFilter>('all')
    const [hfSort, setHfSort] = useState<HuggingFaceSortBy>('relevance')

    const [hfModels, setHfModels] = useState<HuggingFaceModelDefinition[]>([])
    const [hfPage, setHfPage] = useState(1)
    const [hfHasMore, setHfHasMore] = useState(false)
    const [hfUsingToken, setHfUsingToken] = useState(false)
    const [hfWarning, setHfWarning] = useState<string | null>(null)
    const [hfTaskOptions, setHfTaskOptions] = useState<string[]>([])
    const [hfLibraryOptions, setHfLibraryOptions] = useState<string[]>([])
    const [hfLoading, setHfLoading] = useState(true)
    const [hfLoadingMore, setHfLoadingMore] = useState(false)
    const [hfError, setHfError] = useState<string | null>(null)
    const [hfMessage, setHfMessage] = useState<string | null>(null)
    const [hfDownloads, setHfDownloads] = useState<Record<string, HuggingFaceDownloadState>>({})
    const { mark: markCancellingHfJob, clear: clearCancellingHfJob, has: hasCancellingHfJob } = useKeyedFlags()

    const hfAbortRef = useRef<AbortController | null>(null)
    const hfCacheRef = useRef<Map<string, Map<number, HuggingFaceModelCatalogResponse>>>(new Map())
    const hfDownloadTimersRef = useRef<Record<string, ReturnType<typeof setTimeout>>>({})
    const hfDownloadPollGenerationRef = useRef<Record<string, number>>({})

    const debouncedHfSearch = useDebouncedValue(hfSearchInput.trim(), SEARCH_DEBOUNCE_MS)

    const hfQuery = useMemo<HuggingFaceModelQueryOptions>(
        () => ({
            search: debouncedHfSearch || undefined,
            task: hfTask || undefined,
            library: hfLibrary || undefined,
            author: hfAuthor.trim() || undefined,
            visibility: hfVisibility,
            sort: hfSort,
            pageSize: HUGGINGFACE_PAGE_SIZE,
        }),
        [debouncedHfSearch, hfAuthor, hfLibrary, hfSort, hfTask, hfVisibility],
    )

    const hfQueryKey = useMemo(() => buildHuggingFaceQueryKey(hfQuery), [hfQuery])

    const filteredOllamaModels = useMemo(() => {
        const normalizedSearch = ollamaSearch.trim().toLowerCase()
        return ollamaModels.filter((model) => {
            if (ollamaFilter === 'pulled' && !model.pulled) {
                return false
            }
            if (ollamaFilter === 'unpulled' && model.pulled) {
                return false
            }
            if (!normalizedSearch) {
                return true
            }
            return `${model.model} ${model.description ?? ''}`.toLowerCase().includes(normalizedSearch)
        })
    }, [ollamaFilter, ollamaModels, ollamaSearch])

    const loadOllamaModels = useCallback(async (refresh = false): Promise<void> => {
        setOllamaLoading(true)
        if (refresh) {
            setOllamaMessage(null)
        }
        try {
            const payload = await fetchOllamaLibraryModels({ refresh })
            setOllamaModels(payload.models)
            setOllamaError(null)
            if (refresh) {
                setOllamaMessage(`Updated ${payload.total_count} Ollama models.`)
            }
        } catch (error) {
            setOllamaError(formatCatalogError(error, 'Ollama'))
        } finally {
            setOllamaLoading(false)
        }
    }, [])

    const loadHuggingFacePage = useCallback(
        async (targetPage: number, refresh = false): Promise<void> => {
            const queryCache = hfCacheRef.current.get(hfQueryKey)
            const cachedPage = !refresh ? queryCache?.get(targetPage) : undefined

            if (cachedPage) {
                const merged = flattenCachedRows(queryCache, targetPage)
                setHfModels(merged)
                setHfHasMore(cachedPage.has_more)
                setHfUsingToken(cachedPage.using_token)
                setHfWarning(cachedPage.warning)
                setHfTaskOptions(mergeFilterOptions(cachedPage.available_tasks, hfTask))
                setHfLibraryOptions(mergeFilterOptions(cachedPage.available_libraries, hfLibrary))
                setHfPage(targetPage)
                setHfLoading(false)
                setHfLoadingMore(false)
                setHfError(null)
                return
            }

            if (targetPage === 1) {
                setHfLoading(true)
            } else {
                setHfLoadingMore(true)
            }
            setHfError(null)

            hfAbortRef.current?.abort()
            const controller = new AbortController()
            hfAbortRef.current = controller

            try {
                const payload = await fetchHuggingFaceModels(
                    {
                        ...hfQuery,
                        page: targetPage,
                        refresh,
                    },
                    { signal: controller.signal },
                )

                const nextQueryCache = refresh ? new Map<number, HuggingFaceModelCatalogResponse>() : queryCache || new Map()
                nextQueryCache.set(targetPage, payload)
                hfCacheRef.current.set(hfQueryKey, nextQueryCache)

                const merged = flattenCachedRows(nextQueryCache, targetPage)
                setHfModels(merged)
                setHfHasMore(payload.has_more)
                setHfUsingToken(payload.using_token)
                setHfWarning(payload.warning)
                setHfTaskOptions(mergeFilterOptions(payload.available_tasks, hfTask))
                setHfLibraryOptions(mergeFilterOptions(payload.available_libraries, hfLibrary))
                setHfPage(targetPage)
            } catch (error) {
                if (error instanceof DOMException && error.name === 'AbortError') {
                    return
                }
                setHfError(formatCatalogError(error, 'Hugging Face'))
            } finally {
                if (hfAbortRef.current === controller) {
                    hfAbortRef.current = null
                }
                setHfLoading(false)
                setHfLoadingMore(false)
            }
        },
        [hfLibrary, hfQuery, hfQueryKey, hfTask],
    )

    const refreshHuggingFace = useCallback(async (): Promise<void> => {
        hfCacheRef.current.delete(hfQueryKey)
        setHfModels([])
        setHfPage(1)
        await loadHuggingFacePage(1, true)
    }, [hfQueryKey, loadHuggingFacePage])

    useEffect(() => {
        void loadOllamaModels(false)
    }, [loadOllamaModels])

    useEffect(() => {
        setHfModels([])
        setHfPage(1)
        setHfHasMore(false)
        setHfWarning(null)
        void loadHuggingFacePage(1, false)
    }, [hfQueryKey, loadHuggingFacePage])

    useEffect(() => {
        return () => {
            hfAbortRef.current?.abort()
            for (const timer of Object.values(hfDownloadTimersRef.current)) {
                clearTimeout(timer)
            }
            hfDownloadTimersRef.current = {}
            hfDownloadPollGenerationRef.current = {}
        }
    }, [])

    const clearHuggingFaceDownloadTimer = useCallback((repoId: string): void => {
        const timer = hfDownloadTimersRef.current[repoId]
        if (timer) {
            clearTimeout(timer)
            delete hfDownloadTimersRef.current[repoId]
        }
    }, [])

    const clearHuggingFaceDownloadState = useCallback(
        (repoId: string): void => {
            clearHuggingFaceDownloadTimer(repoId)
            delete hfDownloadPollGenerationRef.current[repoId]

            clearCancellingHfJob(repoId)
            setHfDownloads((current) => {
                const next = { ...current }
                delete next[repoId]
                return next
            })
        },
        [clearCancellingHfJob, clearHuggingFaceDownloadTimer],
    )

    const scheduleHuggingFaceDownloadPoll = useCallback(
        (repoId: string, jobId: string, generation: number, delayMs: number): void => {
            clearHuggingFaceDownloadTimer(repoId)
            hfDownloadTimersRef.current[repoId] = setTimeout(() => {
                void (async () => {
                    if (hfDownloadPollGenerationRef.current[repoId] !== generation) {
                        return
                    }

                    try {
                        const payload: HuggingFaceModelDownloadStatusResponse = await getHuggingFaceDownloadStatus(jobId)
                        if (hfDownloadPollGenerationRef.current[repoId] !== generation) {
                            return
                        }

                        setHfDownloads((current) => {
                            const currentState = current[repoId]
                            if (!currentState || currentState.jobId !== jobId) {
                                return current
                            }

                            return {
                                ...current,
                                [repoId]: {
                                    ...currentState,
                                    status: payload.status,
                                    progress: payload.progress,
                                    downloadedBytes: payload.downloaded_bytes,
                                    totalBytes: payload.total_bytes,
                                    message: payload.message,
                                },
                            }
                        })

                        if (payload.status === 'pending' || payload.status === 'running') {
                            scheduleHuggingFaceDownloadPoll(repoId, jobId, generation, HF_DOWNLOAD_POLL_MS)
                            return
                        }

                        clearHuggingFaceDownloadTimer(repoId)
                        clearCancellingHfJob(repoId)

                        if (payload.status === 'completed') {
                            setHfMessage(payload.message ?? `Downloaded Hugging Face model '${repoId}'.`)
                            await refreshHuggingFace()
                        } else if (payload.status === 'cancelled') {
                            setHfMessage(payload.message ?? `Download cancelled for '${repoId}'.`)
                        } else {
                            setHfError(payload.error ?? payload.message ?? `Download failed for '${repoId}'.`)
                        }

                        clearHuggingFaceDownloadState(repoId)
                    } catch (error) {
                        if (hfDownloadPollGenerationRef.current[repoId] !== generation) {
                            return
                        }
                        setHfError(error instanceof Error ? error.message : `Failed to poll download status for '${repoId}'.`)
                        clearHuggingFaceDownloadState(repoId)
                    }
                })()
            }, Math.max(250, delayMs))
        },
        [clearHuggingFaceDownloadState, clearHuggingFaceDownloadTimer, refreshHuggingFace],
    )

    async function handleDownloadHuggingFaceModel(repoId: string): Promise<void> {
        const currentDownload = hfDownloads[repoId]
        const isActiveDownload = currentDownload && (currentDownload.status === 'pending' || currentDownload.status === 'running')

        if (isActiveDownload) {
            markCancellingHfJob(repoId)
            try {
                const payload = await cancelHuggingFaceDownload(currentDownload.jobId)
                setHfMessage(payload.message)

                const generation = hfDownloadPollGenerationRef.current[repoId]
                if (typeof generation === 'number') {
                    scheduleHuggingFaceDownloadPoll(repoId, currentDownload.jobId, generation, 250)
                    return
                }

                clearHuggingFaceDownloadState(repoId)
            } catch (error) {
                setHfError(error instanceof Error ? error.message : `Failed to cancel download for '${repoId}'.`)
                clearCancellingHfJob(repoId)

            }
            return
        }

        setHfError(null)
        setHfMessage(null)

        try {
            const payload = await downloadHuggingFaceModel(repoId)
            const jobId = payload.job_id
            if (payload.already_downloaded || !jobId || payload.status === 'completed') {
                clearHuggingFaceDownloadState(repoId)
                setHfMessage(payload.message)
                await refreshHuggingFace()
                return
            }

            const generation = (hfDownloadPollGenerationRef.current[repoId] ?? 0) + 1
            hfDownloadPollGenerationRef.current[repoId] = generation
            setHfDownloads((current) => ({
                ...current,
                [repoId]: {
                    jobId,
                    status: payload.status,
                    progress: payload.progress,
                    downloadedBytes: payload.downloaded_bytes,
                    totalBytes: payload.total_bytes,
                    message: payload.message,
                },
            }))

            const pollDelayMs = Math.max(250, Math.round(payload.poll_interval * 1000) || HF_DOWNLOAD_POLL_MS)
            scheduleHuggingFaceDownloadPoll(repoId, jobId, generation, pollDelayMs)
        } catch (error) {
            setHfError(error instanceof Error ? error.message : 'Failed to download Hugging Face model')
            clearHuggingFaceDownloadState(repoId)
        }
    }
    async function handlePullModel(modelName: string): Promise<void> {
        markPullingModel(modelName)
        setOllamaError(null)
        setOllamaMessage(null)
        try {
            const payload = await pullOllamaModel(modelName)
            setOllamaMessage(payload.message)
            await loadOllamaModels(true)
        } catch (error) {
            setOllamaError(error instanceof Error ? error.message : 'Failed to pull Ollama model')
        } finally {
            clearPullingModel(modelName)
        }
    }

    return (
        <section className="models-page">
            <header className="models-page-header">
                <h1>Models Explorer</h1>
                <p>Search, filter, and refresh local Ollama and Hugging Face model catalogs for fast workflow setup.</p>
            </header>

            <div className="models-grid">
                <section className="models-column" aria-label="Ollama models">
                    <CatalogColumnHeader
                        title="Ollama Models"
                        description="Available from `ollama.com/library`, with local pull status from your Ollama runtime."
                        actionLabel="Update"
                        busyLabel="Updating..."
                        disabled={ollamaLoading}
                        isBusy={ollamaLoading}
                        actionIcon={<RefreshCw size={15} strokeWidth={2} />}
                        onAction={() => {
                            void loadOllamaModels(true)
                        }}
                    />

                    <div className="models-toolbar">
                        <label className="models-search">
                            <Search size={14} strokeWidth={2.2} />
                            <input
                                type="search"
                                value={ollamaSearch}
                                onChange={(event) => setOllamaSearch(event.target.value)}
                                placeholder="Search by model name"
                                aria-label="Search Ollama models"
                            />
                        </label>
                        <select
                            aria-label="Filter Ollama models by pull state"
                            value={ollamaFilter}
                            onChange={(event) => setOllamaFilter(parseOllamaModelFilter(event.target.value))}
                        >
                            <option value="all">All states</option>
                            <option value="pulled">Pulled only</option>
                            <option value="unpulled">Unpulled only</option>
                        </select>
                    </div>

                    {ollamaError && <RetryErrorNotice message={ollamaError} onRetry={() => void loadOllamaModels(true)} />}
                    {ollamaMessage && <p className="models-note">{ollamaMessage}</p>}

                    <div className="models-list" role="list" aria-label="Ollama model list">
                        {ollamaLoading && <div className="models-empty">Loading Ollama models...</div>}
                        {!ollamaLoading && filteredOllamaModels.length === 0 && (
                            <div className="models-empty">No Ollama models match the active filters.</div>
                        )}
                        {!ollamaLoading &&
                            filteredOllamaModels.map((model) => {
                                const isPulling = hasPullingModel(model.model)
                                const trimmedDescription = trimOllamaDescription(model.model, model.description)
                                return (
                                    <article
                                        key={model.model}
                                        role="listitem"
                                        className={`models-row ${model.pulled ? 'models-row-pulled' : 'models-row-unpulled'}`}
                                    >
                                        <div className="models-row-main">
                                            <h3>{model.model}</h3>
                                            {trimmedDescription && <p>{trimmedDescription}</p>}
                                        </div>
                                        <div className="models-row-actions">
                                            {model.pulled ? (
                                                <span className="models-pill models-pill-ok">
                                                    <Check size={13} strokeWidth={2.4} />
                                                    Pulled
                                                </span>
                                            ) : (
                                                <button
                                                    type="button"
                                                    className="models-icon-button"
                                                    onClick={() => void handlePullModel(model.model)}
                                                    disabled={isPulling}
                                                    title="Pull model"
                                                    aria-label={`Pull ${model.model}`}
                                                >
                                                    <Download size={14} strokeWidth={2.1} />
                                                    {isPulling ? 'Pulling...' : 'Pull'}
                                                </button>
                                            )}
                                        </div>
                                    </article>
                                )
                            })}
                    </div>
                    <div className="models-footer models-footer-placeholder" aria-hidden="true" />
                </section>

                <section className="models-column" aria-label="Hugging Face models">
                    <CatalogColumnHeader
                        title="Hugging Face Models"
                        description="Live Hub API results with server-backed filters, pagination, and refresh."
                        actionLabel="Update"
                        busyLabel="Updating..."
                        disabled={hfLoading || hfLoadingMore}
                        isBusy={hfLoading}
                        actionIcon={<RefreshCw size={15} strokeWidth={2} />}
                        onAction={() => {
                            void refreshHuggingFace()
                        }}
                    />

                    <div className="models-toolbar models-toolbar-hf">
                        <label className="models-search">
                            <Search size={14} strokeWidth={2.2} />
                            <input
                                type="search"
                                value={hfSearchInput}
                                onChange={(event) => setHfSearchInput(event.target.value)}
                                placeholder="Search by model name or repo id"
                                aria-label="Search Hugging Face models"
                            />
                        </label>
                        <input
                            type="text"
                            value={hfAuthor}
                            onChange={(event) => setHfAuthor(event.target.value)}
                            placeholder="Author or org"
                            aria-label="Filter Hugging Face models by author"
                        />
                        <select aria-label="Filter Hugging Face models by task" value={hfTask} onChange={(event) => setHfTask(event.target.value)}>
                            <option value="">All tasks</option>
                            {hfTaskOptions.map((task) => (
                                <option key={task} value={task}>
                                    {task}
                                </option>
                            ))}
                        </select>
                        <select aria-label="Filter Hugging Face models by library" value={hfLibrary} onChange={(event) => setHfLibrary(event.target.value)}>
                            <option value="">All libraries</option>
                            {hfLibraryOptions.map((library) => (
                                <option key={library} value={library}>
                                    {library}
                                </option>
                            ))}
                        </select>
                        <select
                            aria-label="Filter Hugging Face models by visibility"
                            value={hfVisibility}
                            onChange={(event) => setHfVisibility(parseVisibilityFilter(event.target.value))}
                        >
                            <option value="all">All visibility</option>
                            <option value="public">Public</option>
                            <option value="gated">Gated</option>
                            <option value="private">Private</option>
                        </select>
                        <select
                            aria-label="Sort Hugging Face models"
                            value={hfSort}
                            onChange={(event) => setHfSort(parseHuggingFaceSortBy(event.target.value))}
                        >
                            <option value="relevance">Relevance</option>
                            <option value="downloads">Downloads</option>
                            <option value="likes">Likes</option>
                            <option value="updated">Updated</option>
                        </select>
                    </div>

                    <p className="models-note">{hfUsingToken ? 'Authenticated query mode.' : 'Public query mode (no token detected).'}</p>
                    {hfWarning && <p className="models-warning">{hfWarning}</p>}
                    {hfMessage && <p className="models-note">{hfMessage}</p>}

                    {hfError && <RetryErrorNotice message={hfError} onRetry={() => void loadHuggingFacePage(1, true)} />}

                    <div className="models-list" role="list" aria-label="Hugging Face model list">
                        {hfLoading && <div className="models-empty">Loading Hugging Face models...</div>}
                        {!hfLoading && hfModels.length === 0 && <div className="models-empty">No models match the current query.</div>}
                        {!hfLoading &&
                            hfModels.map((model) => {
                                const visibilityConfig = VISIBILITY_ICON_MAP[model.visibility] ?? VISIBILITY_ICON_MAP.unknown
                                const VisibilityIcon = visibilityConfig.icon
                                const downloadState = hfDownloads[model.repo_id] ?? null
                                const isDownloading =
                                    downloadState !== null && (downloadState.status === 'pending' || downloadState.status === 'running')
                                const isCancelling = hasCancellingHfJob(model.repo_id)
                                const progressValue = downloadState ? Math.min(100, Math.max(0, downloadState.progress)) : 0
                                return (
                                    <article key={model.repo_id} role="listitem" className="models-row models-row-hf">
                                        <div className="models-row-main">
                                            <h3>{model.repo_id}</h3>
                                            <div className="models-meta-line">
                                                <span>{model.author || 'Unknown author'}</span>
                                                <span>{model.task || 'No task'}</span>
                                                <span>{model.library || 'No library tag'}</span>
                                            </div>
                                            <div className="models-meta-line">
                                                <span>Likes: {formatMetric(model.likes)}</span>
                                                <span>Downloads: {formatMetric(model.downloads)}</span>
                                                <span>{formatModelSize(model.size_bytes)}</span>
                                            </div>
                                            {downloadState && (
                                                <div
                                                    className="models-download-progress"
                                                    role="progressbar"
                                                    aria-valuemin={0}
                                                    aria-valuemax={100}
                                                    aria-valuenow={Math.round(progressValue)}
                                                >
                                                    <div className="models-download-progress-track">
                                                        <div className="models-download-progress-fill" style={{ width: `${progressValue}%` }} />
                                                    </div>
                                                    <div className="models-download-progress-meta">
                                                        <span>{downloadState.message ?? 'Downloading...'}</span>
                                                        <span>
                                                            {`${formatBytes(downloadState.downloadedBytes)} / ${
                                                                downloadState.totalBytes !== null ? formatBytes(downloadState.totalBytes) : 'Unknown'
                                                            }`}
                                                        </span>
                                                    </div>
                                                </div>
                                            )}
                                        </div>
                                        <div className="models-row-actions models-row-actions-hf">
                                            <div className="models-row-pills-hf">
                                                <span className={`models-pill ${visibilityConfig.className}`}>
                                                    <VisibilityIcon size={13} strokeWidth={2.2} />
                                                    {visibilityConfig.label}
                                                </span>
                                                {model.downloaded && !isDownloading && (
                                                    <span className="models-pill models-pill-ok">
                                                        <Check size={13} strokeWidth={2.2} />
                                                        Downloaded
                                                    </span>
                                                )}
                                            </div>
                                            <div className="models-row-button-line">
                                                {!model.downloaded && (
                                                    <button
                                                        type="button"
                                                        className={`models-icon-button models-icon-button-compact ${
                                                            isDownloading ? 'models-icon-button-stop' : ''
                                                        }`}
                                                        onClick={() => void handleDownloadHuggingFaceModel(model.repo_id)}
                                                        disabled={isCancelling}
                                                    >
                                                        <Download size={13} strokeWidth={2.2} />
                                                        {isDownloading ? (isCancelling ? 'Stopping...' : 'Stop') : 'Download'}
                                                    </button>
                                                )}
                                                <a
                                                    href={model.url}
                                                    target="_blank"
                                                    rel="noreferrer"
                                                    className="models-icon-button models-icon-button-compact"
                                                >
                                                    <ExternalLink size={13} strokeWidth={2.2} />
                                                    Open
                                                </a>
                                            </div>
                                        </div>
                                    </article>
                                )
                            })}
                    </div>

                    <div className="models-footer">
                        <button
                            type="button"
                            onClick={() => void loadHuggingFacePage(hfPage + 1, false)}
                            disabled={hfLoading || hfLoadingMore || !hfHasMore}
                        >
                            {hfLoadingMore ? 'Loading...' : hfHasMore ? 'Load more' : 'No more results'}
                        </button>
                    </div>
                </section>
            </div>
        </section>
    )
}



