import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
    cancelHuggingFaceDownload,
    downloadHuggingFaceModel,
    getExecution,
    getHuggingFaceDownloadStatus,
    pollExecution,
    subscribeExecutionEvents,
    uploadNodeDirectory,
} from './workflowApi'
import { getApiBase } from './api'

function createJsonResponse(body: unknown, init: ResponseInit): Response {
    return new Response(JSON.stringify(body), {
        ...init,
        headers: {
            'Content-Type': 'application/json',
            ...(init.headers || {}),
        },
    })
}

function buildRun(status: 'queued' | 'running' | 'completed') {
    return {
        run_id: 'run-1',
        workflow_id: null,
        plan_id: 'plan-1',
        status,
        created_at: '2026-03-24T00:00:00Z',
        updated_at: '2026-03-24T00:00:00Z',
        progress: status === 'completed' ? 100 : status === 'running' ? 50 : 0,
        steps: [],
        outputs: status === 'completed' ? { output_1: { text: 'done' } } : {},
        error: null,
    }
}

describe('workflowApi service layer', () => {
    beforeEach(() => {
        vi.useRealTimers()
    })

    afterEach(() => {
        vi.useRealTimers()
        vi.restoreAllMocks()
        vi.unstubAllGlobals()
    })

    it('rejects uploadNodeDirectory when no files are selected', async () => {
        await expect(uploadNodeDirectory([])).rejects.toThrow('No files selected')
    })

    it('extracts API error details for uploadNodeDirectory', async () => {
        const fetchMock = vi.fn().mockResolvedValue(
            createJsonResponse({ detail: ['invalid archive', 'missing manifest'] }, { status: 400, statusText: 'Bad Request' }),
        )
        vi.stubGlobal('fetch', fetchMock)

        const file = new File(['hello'], 'manifest.json', { type: 'application/json' })
        await expect(uploadNodeDirectory([file])).rejects.toThrow('invalid archive; missing manifest')
    })

    it('polls executions deterministically until terminal state', async () => {
        vi.useFakeTimers()
        const fetchMock = vi
            .fn()
            .mockResolvedValueOnce(createJsonResponse(buildRun('queued'), { status: 200, statusText: 'OK' }))
            .mockResolvedValueOnce(createJsonResponse(buildRun('running'), { status: 200, statusText: 'OK' }))
            .mockResolvedValueOnce(createJsonResponse(buildRun('completed'), { status: 200, statusText: 'OK' }))
        vi.stubGlobal('fetch', fetchMock)

        const seenStatuses: string[] = []
        const pending = pollExecution('run-1', 0.01, (run) => {
            seenStatuses.push(run.status)
        })
        await vi.advanceTimersByTimeAsync(1000)
        const finalState = await pending

        expect(finalState.status).toBe('completed')
        expect(seenStatuses).toEqual(['queued', 'running', 'completed'])
        expect(fetchMock).toHaveBeenCalledTimes(3)
        expect(fetchMock).toHaveBeenNthCalledWith(1, `${getApiBase()}/executions/run-1`, expect.any(Object))
    })

    it('validates websocket payloads and forwards parse/stream errors', () => {
        class MockWebSocket {
            static instances: MockWebSocket[] = []

            public onmessage: ((event: MessageEvent<string>) => void) | null = null
            public onerror: ((event: Event) => void) | null = null
            public close = vi.fn()

            constructor(public readonly url: string) {
                MockWebSocket.instances.push(this)
            }

            emitMessage(data: string): void {
                this.onmessage?.({ data } as MessageEvent<string>)
            }

            emitError(): void {
                this.onerror?.(new Event('error'))
            }
        }

        vi.stubGlobal('WebSocket', MockWebSocket as unknown as typeof WebSocket)

        const events: Array<{ run_id: string; event_type: string }> = []
        const errors: string[] = []
        const unsubscribe = subscribeExecutionEvents('run-1', {
            onEvent(event) {
                events.push({ run_id: event.run_id, event_type: event.event_type })
            },
            onError(error) {
                errors.push(error)
            },
        })

        const socket = MockWebSocket.instances[0]
        expect(socket.url).toContain('/executions/ws/runs/run-1')

        socket.emitMessage('not-json')
        socket.emitMessage(JSON.stringify({ event_type: 'execution.started' }))
        socket.emitMessage(
            JSON.stringify({
                event_type: 'execution.started',
                run_id: 'run-1',
                step_id: null,
                sequence: 1,
                timestamp: '2026-03-24T00:00:00Z',
                payload: {},
            }),
        )
        socket.emitError()

        expect(errors.some((item) => item.toLowerCase().includes('unexpected'))).toBe(true)
        expect(errors).toContain('Invalid event payload')
        expect(errors).toContain('Execution event stream disconnected')
        expect(events).toEqual([{ run_id: 'run-1', event_type: 'execution.started' }])

        unsubscribe()
        expect(socket.close).toHaveBeenCalledTimes(1)
    })


    it('does not emit disconnect error after explicit unsubscribe', () => {
        class MockWebSocket {
            static instances: MockWebSocket[] = []

            public onmessage: ((event: MessageEvent<string>) => void) | null = null
            public onerror: ((event: Event) => void) | null = null
            public close = vi.fn()

            constructor(public readonly url: string) {
                MockWebSocket.instances.push(this)
            }

            emitError(): void {
                this.onerror?.(new Event('error'))
            }
        }

        vi.stubGlobal('WebSocket', MockWebSocket as unknown as typeof WebSocket)

        const errors: string[] = []
        const unsubscribe = subscribeExecutionEvents('run-1', {
            onEvent() {
                // No-op for this scenario.
            },
            onError(error) {
                errors.push(error)
            },
        })

        const socket = MockWebSocket.instances[0]
        unsubscribe()
        socket.emitError()

        expect(socket.close).toHaveBeenCalledTimes(1)
        expect(errors).not.toContain('Execution event stream disconnected')
    })
    it('guards Hugging Face download argument preconditions', () => {
        expect(() => downloadHuggingFaceModel('  ')).toThrow('Repository id is required')
        expect(() => getHuggingFaceDownloadStatus('  ')).toThrow('Download job id is required')
        expect(() => cancelHuggingFaceDownload('  ')).toThrow('Download job id is required')
    })

    it('encodes and trims download status requests', async () => {
        const fetchMock = vi
            .fn()
            .mockResolvedValue(createJsonResponse({ job_id: 'job/1', status: 'running' }, { status: 200, statusText: 'OK' }))
        vi.stubGlobal('fetch', fetchMock)

        await getHuggingFaceDownloadStatus(' job/1 ')
        expect(fetchMock).toHaveBeenCalledWith(
            `${getApiBase()}/providers/huggingface/download/job%2F1`,
            expect.any(Object),
        )
    })

    it('keeps getExecution wired through requestJson', async () => {
        const fetchMock = vi.fn().mockResolvedValue(createJsonResponse(buildRun('completed'), { status: 200, statusText: 'OK' }))
        vi.stubGlobal('fetch', fetchMock)

        await expect(getExecution('run-1')).resolves.toMatchObject({ run_id: 'run-1', status: 'completed' })
    })
})
