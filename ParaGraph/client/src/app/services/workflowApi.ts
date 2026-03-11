import {
    AppConfigurationPayload,
    CompileWorkflowResponse,
    CompiledExecutionPlan,
    ExecutionEventEnvelope,
    ExecutionRunState,
    NodeCatalogResponse,
    NodeManifest,
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
    const apiBase = getApiBase()
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
