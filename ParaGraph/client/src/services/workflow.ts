import {
    CatalogResponse,
    ExecuteWorkflowResponse,
    JobStatusResponse,
    ValidateWorkflowResponse,
    WorkflowGraph,
} from '../types'

const API_BASE = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/$/, '')

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
    const response = await fetch(`${API_BASE}${path}`, {
        headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
        ...init,
    })

    if (!response.ok) {
        let detail = `${response.status} ${response.statusText}`
        try {
            const payload = (await response.json()) as { detail?: string | string[] }
            if (Array.isArray(payload.detail)) {
                detail = payload.detail.join('; ')
            } else if (payload.detail) {
                detail = payload.detail
            }
        } catch {
            // fallback keeps status text
        }
        throw new Error(detail)
    }

    return (await response.json()) as T
}

export function fetchWorkflowCatalog(): Promise<CatalogResponse> {
    return requestJson<CatalogResponse>('/workflow/catalog')
}

export function validateWorkflow(graph: WorkflowGraph): Promise<ValidateWorkflowResponse> {
    return requestJson<ValidateWorkflowResponse>('/workflow/validate', {
        method: 'POST',
        body: JSON.stringify(graph),
    })
}

export function executeWorkflow(graph: WorkflowGraph): Promise<ExecuteWorkflowResponse> {
    return requestJson<ExecuteWorkflowResponse>('/workflow/execute', {
        method: 'POST',
        body: JSON.stringify(graph),
    })
}

export function getWorkflowJob(jobId: string): Promise<JobStatusResponse> {
    return requestJson<JobStatusResponse>(`/workflow/jobs/${jobId}`)
}

export function cancelWorkflowJob(jobId: string): Promise<{ success: boolean }> {
    return requestJson<{ success: boolean }>(`/workflow/jobs/${jobId}`, { method: 'DELETE' })
}

function sleep(durationMs: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, durationMs))
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
