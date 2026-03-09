import {
    ExecutionEventEnvelope,
    ExecuteWorkflowResponse,
    JobStatusResponse,
    LegacyWorkflowGraph,
    NodeCatalogResponse,
    ProviderCatalogResponse,
    ValidateWorkflowResponse,
} from '../../workflow/schema/types'
import { getApiBase, requestJson } from './api'

export function fetchNodeCatalog(): Promise<NodeCatalogResponse> {
    return requestJson<NodeCatalogResponse>('/nodes/catalog')
}

export function fetchProviderCatalog(): Promise<ProviderCatalogResponse> {
    return requestJson<ProviderCatalogResponse>('/providers/catalog')
}

export function validateWorkflow(graph: LegacyWorkflowGraph): Promise<ValidateWorkflowResponse> {
    return requestJson<ValidateWorkflowResponse>('/workflow/validate', {
        method: 'POST',
        body: JSON.stringify(graph),
    })
}

export function executeWorkflow(graph: LegacyWorkflowGraph): Promise<ExecuteWorkflowResponse> {
    return requestJson<ExecuteWorkflowResponse>('/workflow/execute', {
        method: 'POST',
        body: JSON.stringify(graph),
    })
}

export function getWorkflowJob(jobId: string): Promise<JobStatusResponse> {
    return requestJson<JobStatusResponse>(`/workflow/jobs/${jobId}`)
}

function sleep(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms))
}

export async function pollWorkflowJob(
    jobId: string,
    pollSeconds: number,
    onTick?: (status: JobStatusResponse) => void,
): Promise<JobStatusResponse> {
    const waitMs = Math.max(250, Math.round(pollSeconds * 1000))
    for (;;) {
        const status = await getWorkflowJob(jobId)
        onTick?.(status)
        if (status.status !== 'pending' && status.status !== 'running') {
            return status
        }
        await sleep(waitMs)
    }
}

function resolveWsBase(): string {
    const apiBase = getApiBase()
    if (apiBase.startsWith('http://') || apiBase.startsWith('https://')) {
        return apiBase.replace(/^http/, 'ws')
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    return `${protocol}//${host}${apiBase}`
}

export function subscribeExecutionEvents(
    runId: string,
    handlers: {
        onEvent: (event: ExecutionEventEnvelope) => void
        onError?: (error: string) => void
    },
): () => void {
    const base = resolveWsBase()
    const ws = new WebSocket(`${base}/workflow/ws/runs/${runId}`)

    ws.onmessage = (message) => {
        try {
            const payload = JSON.parse(message.data) as ExecutionEventEnvelope
            handlers.onEvent(payload)
        } catch (error) {
            handlers.onError?.(error instanceof Error ? error.message : 'Invalid event payload')
        }
    }

    ws.onerror = () => {
        handlers.onError?.('Execution event stream disconnected')
    }

    return () => {
        ws.close()
    }
}