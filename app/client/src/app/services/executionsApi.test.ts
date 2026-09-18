import { afterEach, describe, expect, it, vi } from 'vitest'

import { getApiBase } from './api'
import { pollExecution } from './executionsApi'

describe('execution API lifecycle ownership', () => {
    afterEach(() => {
        vi.restoreAllMocks()
        vi.unstubAllGlobals()
    })

    it('passes the monitor AbortSignal through the status request', async () => {
        const fetchMock = vi.fn().mockResolvedValue(
            new Response(JSON.stringify({ run_id: 'run-1', status: 'completed', progress: 100 }), {
                status: 200,
                headers: { 'Content-Type': 'application/json' },
            }),
        )
        vi.stubGlobal('fetch', fetchMock)
        const controller = new AbortController()

        await expect(
            pollExecution('run-1', 1, undefined, { signal: controller.signal }),
        ).resolves.toMatchObject({ status: 'completed' })

        expect(fetchMock).toHaveBeenCalledWith(
            `${getApiBase()}/executions/run-1`,
            expect.objectContaining({ signal: controller.signal }),
        )
    })

    it('aborting an in-flight status request prevents a stale monitor tick', async () => {
        const fetchMock = vi.fn((_input: RequestInfo | URL, init?: RequestInit) => (
            new Promise<Response>((_resolve, reject) => {
                const abort = (): void => {
                    const error = new Error('aborted')
                    error.name = 'AbortError'
                    reject(error)
                }
                init?.signal?.addEventListener('abort', abort, { once: true })
            })
        ))
        vi.stubGlobal('fetch', fetchMock)
        const controller = new AbortController()
        const onTick = vi.fn()
        const polling = pollExecution('run-1', 1, onTick, { signal: controller.signal })

        controller.abort()

        await expect(polling).rejects.toMatchObject({ name: 'AbortError' })
        expect(onTick).not.toHaveBeenCalled()
    })
})
