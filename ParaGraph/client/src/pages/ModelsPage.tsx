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

import { usePageMetadata } from '../app/hooks/usePageMetadata'
import {
    fetchHuggingFaceModels,
    fetchOllamaLibraryModels,
    pullOllamaModel,
    type HuggingFaceModelQueryOptions,
} from '../app/services/workflowApi'
import {
    HuggingFaceModelCatalogResponse,
    HuggingFaceModelDefinition,
    HuggingFaceSortBy,
    ModelVisibilityFilter,
    OllamaLibraryModelDefinition,
} from '../workflow/schema/types'
import './ModelsPage.css'

const HUGGINGFACE_PAGE_SIZE = 25
const SEARCH_DEBOUNCE_MS = 350

type OllamaModelFilter = 'all' | 'pulled' | 'unpulled'

type VisibilityIconConfig = {
    icon: LucideIcon
    label: string
    className: string
}

const VISIBILITY_ICON_MAP: Record<string, VisibilityIconConfig> = {
    public: { icon: Globe, label: 'Public', className: 'models-visibility-public' },
    private: { icon: Lock, label: 'Private', className: 'models-visibility-private' },
    gated: { icon: ShieldAlert, label: 'Gated', className: 'models-visibility-gated' },
    unknown: { icon: HelpCircle, label: 'Unknown', className: 'models-visibility-unknown' },
}

function useDebouncedValue<T>(value: T, delayMs: number): T {
    const [debouncedValue, setDebouncedValue] = useState(value)

    useEffect(() => {
        const timeoutId = window.setTimeout(() => {
            setDebouncedValue(value)
        }, delayMs)
        return () => window.clearTimeout(timeoutId)
    }, [delayMs, value])

    return debouncedValue
}

function formatMetric(value: number | null): string {
    if (typeof value !== 'number' || Number.isNaN(value)) {
        return 'N/A'
    }
    return new Intl.NumberFormat().format(value)
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
    const [pullingModels, setPullingModels] = useState<Record<string, boolean>>({})

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

    const hfAbortRef = useRef<AbortController | null>(null)
    const hfCacheRef = useRef<Map<string, Map<number, HuggingFaceModelCatalogResponse>>>(new Map())

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
        }
    }, [])

    async function handlePullModel(modelName: string): Promise<void> {
        setPullingModels((current) => ({ ...current, [modelName]: true }))
        setOllamaError(null)
        setOllamaMessage(null)
        try {
            const payload = await pullOllamaModel(modelName)
            setOllamaMessage(payload.message)
            await loadOllamaModels(true)
        } catch (error) {
            setOllamaError(error instanceof Error ? error.message : 'Failed to pull Ollama model')
        } finally {
            setPullingModels((current) => {
                const next = { ...current }
                delete next[modelName]
                return next
            })
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
                    <div className="models-column-header">
                        <div>
                            <h2>Ollama Models</h2>
                            <p>Available from `ollama.com/library`, with local pull status from your Ollama runtime.</p>
                        </div>
                        <button type="button" onClick={() => void loadOllamaModels(true)} disabled={ollamaLoading}>
                            <RefreshCw size={15} strokeWidth={2} />
                            {ollamaLoading ? 'Updating...' : 'Update'}
                        </button>
                    </div>

                    <div className="models-toolbar">
                        <label className="models-search">
                            <Search size={14} strokeWidth={2.2} />
                            <input
                                type="search"
                                value={ollamaSearch}
                                onChange={(event) => setOllamaSearch(event.target.value)}
                                placeholder="Search by model name"
                            />
                        </label>
                        <select value={ollamaFilter} onChange={(event) => setOllamaFilter(event.target.value as OllamaModelFilter)}>
                            <option value="all">All states</option>
                            <option value="pulled">Pulled only</option>
                            <option value="unpulled">Unpulled only</option>
                        </select>
                    </div>

                    {ollamaError && (
                        <div className="models-error">
                            <span>{ollamaError}</span>
                            <button type="button" onClick={() => void loadOllamaModels(true)}>
                                Retry
                            </button>
                        </div>
                    )}
                    {ollamaMessage && <p className="models-note">{ollamaMessage}</p>}

                    <div className="models-list" role="list" aria-label="Ollama model list">
                        {ollamaLoading && <div className="models-empty">Loading Ollama models...</div>}
                        {!ollamaLoading && filteredOllamaModels.length === 0 && (
                            <div className="models-empty">No Ollama models match the active filters.</div>
                        )}
                        {!ollamaLoading &&
                            filteredOllamaModels.map((model) => {
                                const isPulling = Boolean(pullingModels[model.model])
                                return (
                                    <article
                                        key={model.model}
                                        role="listitem"
                                        className={`models-row ${model.pulled ? 'models-row-pulled' : 'models-row-unpulled'}`}
                                    >
                                        <div className="models-row-main">
                                            <h3>{model.model}</h3>
                                            {model.description && <p>{model.description}</p>}
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
                </section>

                <section className="models-column" aria-label="Hugging Face models">
                    <div className="models-column-header">
                        <div>
                            <h2>Hugging Face Models</h2>
                            <p>Live Hub API results with server-backed filters, pagination, and refresh.</p>
                        </div>
                        <button type="button" onClick={() => void refreshHuggingFace()} disabled={hfLoading || hfLoadingMore}>
                            <RefreshCw size={15} strokeWidth={2} />
                            {hfLoading ? 'Updating...' : 'Update'}
                        </button>
                    </div>

                    <div className="models-toolbar models-toolbar-hf">
                        <label className="models-search">
                            <Search size={14} strokeWidth={2.2} />
                            <input
                                type="search"
                                value={hfSearchInput}
                                onChange={(event) => setHfSearchInput(event.target.value)}
                                placeholder="Search by model name or repo id"
                            />
                        </label>
                        <select value={hfTask} onChange={(event) => setHfTask(event.target.value)}>
                            <option value="">All tasks</option>
                            {hfTaskOptions.map((task) => (
                                <option key={task} value={task}>
                                    {task}
                                </option>
                            ))}
                        </select>
                        <select value={hfLibrary} onChange={(event) => setHfLibrary(event.target.value)}>
                            <option value="">All libraries</option>
                            {hfLibraryOptions.map((library) => (
                                <option key={library} value={library}>
                                    {library}
                                </option>
                            ))}
                        </select>
                        <input
                            type="text"
                            value={hfAuthor}
                            onChange={(event) => setHfAuthor(event.target.value)}
                            placeholder="Author or org"
                        />
                        <select
                            value={hfVisibility}
                            onChange={(event) => setHfVisibility(event.target.value as ModelVisibilityFilter)}
                        >
                            <option value="all">All visibility</option>
                            <option value="public">Public</option>
                            <option value="gated">Gated</option>
                            <option value="private">Private</option>
                        </select>
                        <select value={hfSort} onChange={(event) => setHfSort(event.target.value as HuggingFaceSortBy)}>
                            <option value="relevance">Relevance</option>
                            <option value="downloads">Downloads</option>
                            <option value="likes">Likes</option>
                            <option value="updated">Updated</option>
                        </select>
                    </div>

                    <p className="models-note">{hfUsingToken ? 'Authenticated query mode.' : 'Public query mode (no token detected).'}</p>
                    {hfWarning && <p className="models-warning">{hfWarning}</p>}

                    {hfError && (
                        <div className="models-error">
                            <span>{hfError}</span>
                            <button type="button" onClick={() => void loadHuggingFacePage(1, true)}>
                                Retry
                            </button>
                        </div>
                    )}

                    <div className="models-list" role="list" aria-label="Hugging Face model list">
                        {hfLoading && <div className="models-empty">Loading Hugging Face models...</div>}
                        {!hfLoading && hfModels.length === 0 && <div className="models-empty">No models match the current query.</div>}
                        {!hfLoading &&
                            hfModels.map((model) => {
                                const visibilityConfig = VISIBILITY_ICON_MAP[model.visibility] ?? VISIBILITY_ICON_MAP.unknown
                                const VisibilityIcon = visibilityConfig.icon
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
                                            </div>
                                        </div>
                                        <div className="models-row-actions models-row-actions-hf">
                                            <span className={`models-pill ${visibilityConfig.className}`}>
                                                <VisibilityIcon size={13} strokeWidth={2.2} />
                                                {visibilityConfig.label}
                                            </span>
                                            <a href={model.url} target="_blank" rel="noreferrer" className="models-icon-button">
                                                <ExternalLink size={13} strokeWidth={2.2} />
                                                Open
                                            </a>
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
