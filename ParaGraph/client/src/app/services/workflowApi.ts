import {
    AppConfigurationPayload,
    ConfigurationProfileListResponse,
    CompileWorkflowResponse,
    CompiledExecutionPlan,
    DatabaseConnectionCheckResponse,
    ExecutionEventEnvelope,
    ExecutionRunState,
    HuggingFaceModelCatalogResponse,
    HuggingFaceModelDownloadCancelResponse,
    HuggingFaceModelDownloadResponse,
    HuggingFaceModelDownloadStatusResponse,
    HuggingFaceSortBy,
    ModelVisibilityFilter,
    NodeCatalogResponse,
    NodeManifest,
    OllamaLibraryCatalogResponse,
    OllamaModelPullResponse,
    OllamaStatusResponse,
    ProviderModelCatalogResponse,
    StartExecutionResponse,
    WorkflowDefinition,
} from '../../workflow/schema/types'
import { getApiBase, requestJson } from './api'

export function fetchNodeCatalog(): Promise<NodeCatalogResponse> {
    return requestJson<NodeCatalogResponse>('/nodes/catalog')
}

export function importNodeManifest(manifest: NodeManifest): Promise<NodeManifest> {
    return requestJson<NodeManifest>('/nodes/import', {
        method: 'POST',
        body: JSON.stringify(manifest),
    })
}

export interface PickedPathsResponse {
    paths: string[]
}

export interface PickedDirectoryResponse {
    path: string | null
}

export function browseNodeFiles(multiple = false): Promise<PickedPathsResponse> {
    const params = new URLSearchParams({ multiple: String(multiple) })
    return requestJson<PickedPathsResponse>(`/nodes/dialog/files?${params.toString()}`)
}

export function browseNodeDirectory(): Promise<PickedDirectoryResponse> {
    return requestJson<PickedDirectoryResponse>('/nodes/dialog/directory')
}

export interface UploadedDirectoryResponse {
    path: string
    file_count: number
}

async function extractApiErrorDetail(response: Response): Promise<string> {
    let detail = `${response.status} ${response.statusText}`
    try {
        const payload = (await response.json()) as { detail?: string | string[] }
        if (Array.isArray(payload.detail)) {
            detail = payload.detail.join('; ')
        } else if (payload.detail) {
            detail = payload.detail
        }
    } catch {
        // Use default HTTP status detail.
    }
    return detail
}

export async function uploadNodeDirectory(files: File[]): Promise<UploadedDirectoryResponse> {
    if (files.length === 0) {
        throw new Error('No files selected')
    }

    const formData = new FormData()
    for (const file of files) {
        const relativePath = file.webkitRelativePath || file.name
        formData.append('files', file, relativePath)
    }

    const response = await fetch(`${getApiBase()}/nodes/uploads/directory`, {
        method: 'POST',
        body: formData,
    })

    if (!response.ok) {
        throw new Error(await extractApiErrorDetail(response))
    }

    return (await response.json()) as UploadedDirectoryResponse
}

export function checkDatabaseConnection(
    nodeType: 'SQL_DATABASE' | 'SQL_FILE_DATABASE',
    nodeVersion: number,
    parameters: Record<string, unknown>,
): Promise<DatabaseConnectionCheckResponse> {
    return requestJson<DatabaseConnectionCheckResponse>('/nodes/check-database-connection', {
        method: 'POST',
        body: JSON.stringify({
            node_type: nodeType,
            node_version: nodeVersion,
            parameters,
        }),
    })
}

export function fetchProviderModels(sessionName = 'default'): Promise<ProviderModelCatalogResponse> {
    const params = new URLSearchParams({ session_name: sessionName })
    return requestJson<ProviderModelCatalogResponse>(`/providers/models?${params.toString()}`)
}

export interface OllamaLibraryQueryOptions {
    sessionName?: string
    search?: string
    refresh?: boolean
}

export function fetchOllamaLibraryModels(options: OllamaLibraryQueryOptions = {}): Promise<OllamaLibraryCatalogResponse> {
    const params = new URLSearchParams()
    params.set('session_name', options.sessionName || 'default')
    if (options.search && options.search.trim()) {
        params.set('search', options.search.trim())
    }
    if (options.refresh) {
        params.set('refresh', 'true')
    }
    return requestJson<OllamaLibraryCatalogResponse>(`/providers/ollama/library?${params.toString()}`)
}

export function pullOllamaModel(model: string, sessionName = 'default'): Promise<OllamaModelPullResponse> {
    const params = new URLSearchParams({ session_name: sessionName })
    return requestJson<OllamaModelPullResponse>(`/providers/ollama/pull?${params.toString()}`, {
        method: 'POST',
        body: JSON.stringify({ model }),
    })
}

export interface HuggingFaceModelQueryOptions {
    sessionName?: string
    search?: string
    task?: string
    library?: string
    author?: string
    visibility?: ModelVisibilityFilter
    sort?: HuggingFaceSortBy
    page?: number
    pageSize?: number
    refresh?: boolean
}

export function fetchHuggingFaceModels(
    options: HuggingFaceModelQueryOptions,
    init?: RequestInit,
): Promise<HuggingFaceModelCatalogResponse> {
    const params = new URLSearchParams()
    params.set('session_name', options.sessionName || 'default')

    const search = options.search?.trim()
    const task = options.task?.trim()
    const library = options.library?.trim()
    const author = options.author?.trim()
    if (search) {
        params.set('search', search)
    }
    if (task) {
        params.set('task', task)
    }
    if (library) {
        params.set('library', library)
    }
    if (author) {
        params.set('author', author)
    }

    params.set('visibility', options.visibility || 'all')
    params.set('sort', options.sort || 'relevance')
    params.set('page', String(options.page || 1))
    params.set('page_size', String(options.pageSize || 25))
    if (options.refresh) {
        params.set('refresh', 'true')
    }

    return requestJson<HuggingFaceModelCatalogResponse>(`/providers/huggingface/models?${params.toString()}`, init)
}

export function downloadHuggingFaceModel(repoId: string, sessionName = 'default'): Promise<HuggingFaceModelDownloadResponse> {
    const normalizedRepoId = repoId.trim()
    if (!normalizedRepoId) {
        throw new Error('Repository id is required')
    }

    const params = new URLSearchParams({ session_name: sessionName })
    return requestJson<HuggingFaceModelDownloadResponse>(`/providers/huggingface/download?${params.toString()}`, {
        method: 'POST',
        body: JSON.stringify({ repo_id: normalizedRepoId }),
    })
}

export function getHuggingFaceDownloadStatus(jobId: string): Promise<HuggingFaceModelDownloadStatusResponse> {
    const normalizedJobId = jobId.trim()
    if (!normalizedJobId) {
        throw new Error('Download job id is required')
    }
    return requestJson<HuggingFaceModelDownloadStatusResponse>(`/providers/huggingface/download/${encodeURIComponent(normalizedJobId)}`)
}

export function cancelHuggingFaceDownload(jobId: string): Promise<HuggingFaceModelDownloadCancelResponse> {
    const normalizedJobId = jobId.trim()
    if (!normalizedJobId) {
        throw new Error('Download job id is required')
    }
    return requestJson<HuggingFaceModelDownloadCancelResponse>(`/providers/huggingface/download/${encodeURIComponent(normalizedJobId)}`, {
        method: 'DELETE',
    })
}
export function fetchConfigurations(sessionName = 'default'): Promise<AppConfigurationPayload> {
    const params = new URLSearchParams({ session_name: sessionName })
    return requestJson<AppConfigurationPayload>(`/configurations?${params.toString()}`)
}

export function saveConfigurations(payload: AppConfigurationPayload): Promise<AppConfigurationPayload> {
    return requestJson<AppConfigurationPayload>('/configurations', {
        method: 'PUT',
        body: JSON.stringify(payload),
    })
}


export function listConfigurationProfiles(sessionName = 'default'): Promise<ConfigurationProfileListResponse> {
    const params = new URLSearchParams({ session_name: sessionName })
    return requestJson<ConfigurationProfileListResponse>(`/configurations/profiles?${params.toString()}`)
}

export function loadConfigurationProfile(profileName: string, sessionName = 'default'): Promise<AppConfigurationPayload> {
    const params = new URLSearchParams({ session_name: sessionName })
    return requestJson<AppConfigurationPayload>(`/configurations/profiles/${encodeURIComponent(profileName)}?${params.toString()}`)
}

export function saveConfigurationProfile(profileName: string, payload: AppConfigurationPayload): Promise<AppConfigurationPayload> {
    return requestJson<AppConfigurationPayload>(`/configurations/profiles/${encodeURIComponent(profileName)}`, {
        method: 'PUT',
        body: JSON.stringify(payload),
    })
}

export function pingOllama(baseUrl: string | null): Promise<OllamaStatusResponse> {
    return requestJson<OllamaStatusResponse>('/configurations/ollama/ping', {
        method: 'POST',
        body: JSON.stringify({ base_url: baseUrl }),
    })
}
export function compileWorkflow(definition: WorkflowDefinition): Promise<CompileWorkflowResponse> {
    return requestJson<CompileWorkflowResponse>('/executions/compile', {
        method: 'POST',
        body: JSON.stringify({ definition }),
    })
}

export function startExecution(plan: CompiledExecutionPlan, workflowId?: string): Promise<StartExecutionResponse> {
    return requestJson<StartExecutionResponse>('/executions', {
        method: 'POST',
        body: JSON.stringify({ workflow_id: workflowId ?? null, plan }),
    })
}

export function getExecution(runId: string): Promise<ExecutionRunState> {
    return requestJson<ExecutionRunState>(`/executions/${runId}`)
}

function sleep(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms))
}

function isRecord(value: unknown): value is Record<string, unknown> {
    return typeof value === 'object' && value !== null
}

function isExecutionEventEnvelope(value: unknown): value is ExecutionEventEnvelope {
    if (!isRecord(value)) {
        return false
    }

    return (
        typeof value.event_type === 'string' &&
        typeof value.run_id === 'string' &&
        (typeof value.step_id === 'string' || value.step_id === null) &&
        typeof value.sequence === 'number' &&
        typeof value.timestamp === 'string' &&
        isRecord(value.payload)
    )
}

export async function pollExecution(
    runId: string,
    pollSeconds: number,
    onTick?: (run: ExecutionRunState) => void,
): Promise<ExecutionRunState> {
    const waitMs = Math.max(250, Math.round(pollSeconds * 1000))
    for (;;) {
        const run = await getExecution(runId)
        onTick?.(run)
        if (run.status !== 'queued' && run.status !== 'running') {
            return run
        }
        await sleep(waitMs)
    }
}

function resolveWsBase(): string {
    const apiBase = import.meta.env.VITE_API_BASE_URL || '/api'
    if (apiBase.startsWith('http://') || apiBase.startsWith('https://')) {
        return apiBase.replace(/^http/, 'ws')
    }
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    return `${protocol}//${window.location.host}${apiBase}`
}

export function subscribeExecutionEvents(
    runId: string,
    handlers: {
        onEvent: (event: ExecutionEventEnvelope) => void
        onError?: (error: string) => void
    },
): () => void {
    const ws = new WebSocket(`${resolveWsBase()}/executions/ws/runs/${runId}`)

    ws.onmessage = (message) => {
        try {
            const parsed: unknown = JSON.parse(message.data)
            if (!isExecutionEventEnvelope(parsed)) {
                throw new Error('Invalid event payload')
            }
            handlers.onEvent(parsed)
        } catch (error) {
            handlers.onError?.(error instanceof Error ? error.message : 'Invalid event payload')
        }
    }

    ws.onerror = () => handlers.onError?.('Execution event stream disconnected')
    return () => ws.close()
}

