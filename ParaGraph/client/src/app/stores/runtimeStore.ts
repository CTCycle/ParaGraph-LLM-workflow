import { ExecutionEventEnvelope, JobStatusResponse } from '../../workflow/schema/types'
import { createStore, useStore } from './store'

export interface RuntimeState {
    runId: string | null
    status: 'idle' | 'queued' | 'running' | 'completed' | 'failed' | 'cancelled'
    progress: number
    error: string | null
    stepStatus: Record<string, string>
    outputs: Record<string, string>
    events: ExecutionEventEnvelope[]
}

const runtimeStore = createStore<RuntimeState>({
    runId: null,
    status: 'idle',
    progress: 0,
    error: null,
    stepStatus: {},
    outputs: {},
    events: [],
})

export const runtimeActions = {
    reset() {
        runtimeStore.setState({
            runId: null,
            status: 'idle',
            progress: 0,
            error: null,
            stepStatus: {},
            outputs: {},
            events: [],
        })
    },

    startRun(runId: string) {
        runtimeStore.setState({
            runId,
            status: 'queued',
            progress: 0,
            error: null,
            stepStatus: {},
            outputs: {},
            events: [],
        })
    },

    applyEvent(event: ExecutionEventEnvelope) {
        runtimeStore.setState((current) => {
            const nextEvents = [...current.events, event].slice(-300)
            const stepStatus = { ...current.stepStatus }
            let status = current.status
            let error = current.error
            let progress = current.progress
            let outputs = { ...current.outputs }

            if (event.step_id) {
                if (event.event_type === 'execution.step.started') {
                    stepStatus[event.step_id] = 'running'
                }
                if (event.event_type === 'execution.step.completed') {
                    stepStatus[event.step_id] = 'completed'
                }
                if (event.event_type === 'execution.step.failed') {
                    stepStatus[event.step_id] = 'failed'
                    error = String(event.payload.error ?? 'Step failed')
                }
            }

            if (event.event_type === 'execution.started') {
                status = 'running'
            }
            if (event.event_type === 'execution.completed') {
                status = 'completed'
                progress = 100
                const eventOutputs = event.payload.outputs
                if (eventOutputs && typeof eventOutputs === 'object') {
                    outputs = Object.fromEntries(
                        Object.entries(eventOutputs as Record<string, { text?: string }>).map(([key, value]) => [
                            key,
                            String(value?.text ?? ''),
                        ]),
                    )
                }
            }
            if (event.event_type === 'execution.failed') {
                status = 'failed'
                error = String(event.payload.error ?? 'Execution failed')
            }

            return {
                ...current,
                status,
                error,
                progress,
                outputs,
                stepStatus,
                events: nextEvents,
            }
        })
    },

    applyJobStatus(status: JobStatusResponse) {
        runtimeStore.setState((current) => {
            const normalizedStatus = status.status === 'pending' ? 'queued' : status.status
            const outputs = status.result?.outputs
                ? Object.fromEntries(
                      Object.entries(status.result.outputs).map(([key, value]) => [key, String(value.text ?? '')]),
                  )
                : current.outputs

            return {
                ...current,
                runId: status.job_id,
                status: normalizedStatus,
                progress: status.progress,
                outputs,
                error: status.error ?? current.error,
            }
        })
    },
}

export function useRuntimeStore<R>(selector: (state: RuntimeState) => R): R {
    return useStore(runtimeStore, selector)
}

