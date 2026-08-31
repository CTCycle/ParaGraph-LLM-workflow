import {
  ExecutionActionResponse,
  ExecutionEventEnvelope,
  ExecutionRunState,
  StartExecutionResponse,
  CompiledExecutionPlan,
} from '../../workflow/schema/types'
import { getApiBase, requestJson } from './api'

export const DEFAULT_EXECUTION_POLL_INTERVAL_SECONDS = 1

export function startExecution(
  plan: CompiledExecutionPlan,
  workflowId?: string,
  executionSessionId?: string,
): Promise<StartExecutionResponse> {
  return requestJson<StartExecutionResponse>('/executions', {
    method: 'POST',
    body: JSON.stringify({
      workflow_id: workflowId ?? null,
      execution_session_id: executionSessionId ?? null,
      plan,
    }),
  })
}

export function getExecution(runId: string): Promise<ExecutionRunState> {
  return requestJson<ExecutionRunState>(`/executions/${encodeURIComponent(runId)}`)
}

export function cancelExecution(runId: string): Promise<ExecutionActionResponse> {
  return requestJson<ExecutionActionResponse>(`/executions/${encodeURIComponent(runId)}/cancel`, { method: 'POST' })
}

export function resumeExecution(
  runId: string,
  resumeToken: string,
  reviewedPayload?: Record<string, unknown>,
): Promise<ExecutionActionResponse> {
  return requestJson<ExecutionActionResponse>(`/executions/${encodeURIComponent(runId)}/resume`, {
    method: 'POST',
    body: JSON.stringify({
      resume_token: resumeToken,
      reviewed_payload: reviewedPayload ?? null,
    }),
  })
}

function createAbortError(): Error {
  const error = new Error('Execution polling aborted')
  error.name = 'AbortError'
  return error
}

function sleep(ms: number, signal?: AbortSignal): Promise<void> {
  if (!signal) return new Promise((resolve) => setTimeout(resolve, ms))
  if (signal.aborted) return Promise.reject(createAbortError())
  return new Promise((resolve, reject) => {
    const timer = window.setTimeout(() => {
      cleanup()
      resolve()
    }, ms)
    const handleAbort = (): void => {
      cleanup()
      reject(createAbortError())
    }
    const cleanup = (): void => {
      window.clearTimeout(timer)
      signal.removeEventListener('abort', handleAbort)
    }
    signal.addEventListener('abort', handleAbort, { once: true })
  })
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

function isExecutionEventEnvelope(value: unknown): value is ExecutionEventEnvelope {
  if (!isRecord(value)) return false
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
  options?: { signal?: AbortSignal },
): Promise<ExecutionRunState> {
  const waitMs = Math.max(250, Math.round(pollSeconds * 1000))
  const signal = options?.signal

  for (;;) {
    if (signal?.aborted) throw createAbortError()
    const run = await getExecution(runId)
    onTick?.(run)
    if (run.status !== 'queued' && run.status !== 'running') {
      return run
    }
    await sleep(waitMs, signal)
  }
}

function resolveWsBase(): string {
  const apiBase = getApiBase()
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
  const ws = new WebSocket(`${resolveWsBase()}/executions/ws/runs/${encodeURIComponent(runId)}`)
  let closedByClient = false

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

  ws.onerror = () => {
    if (!closedByClient) {
      handlers.onError?.('Execution event stream disconnected')
    }
  }
  return () => {
    closedByClient = true
    ws.close()
  }
}
