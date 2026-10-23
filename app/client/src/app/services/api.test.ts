import { afterEach, describe, expect, it, vi } from 'vitest'

import { ApiError, getApiBase, requestJson } from './api'
import { pollExecution } from './executionsApi'

function createJsonResponse(body: unknown, init: ResponseInit): Response {
    return new Response(JSON.stringify(body), {
        ...init,
        headers: {
            'Content-Type': 'application/json',
            ...(init.headers || {}),
        },
    })
}

describe('api requestJson', () => {
    afterEach(() => {
        vi.restoreAllMocks()
        vi.unstubAllGlobals()
    })

    it('extracts array detail messages from error payloads', async () => {
        const fetchMock = vi.fn().mockResolvedValue(
            createJsonResponse({ detail: ['first', 'second'] }, { status: 400, statusText: 'Bad Request' }),
        )
        vi.stubGlobal('fetch', fetchMock)

        await expect(requestJson('/demo')).rejects.toThrow('first; second')
        expect(fetchMock).toHaveBeenCalledWith(
            `${getApiBase()}/demo`,
            expect.objectContaining({
                headers: expect.objectContaining({ 'Content-Type': 'application/json' }),
            }),
        )
    })

    it('falls back to HTTP status when error payload is not JSON', async () => {
        const fetchMock = vi.fn().mockResolvedValue(new Response('not-json', { status: 502, statusText: 'Bad Gateway' }))
        vi.stubGlobal('fetch', fetchMock)

        await expect(requestJson('/demo')).rejects.toThrow('502 Bad Gateway')
    })

    it('preserves structured FastAPI validation issues', async () => {
        const fetchMock = vi.fn().mockResolvedValue(
            createJsonResponse(
                {
                    detail: [
                        { loc: ['body', 'name'], msg: 'Field required', type: 'missing' },
                        { loc: ['body', 'count'], msg: 'Input should be a valid integer', type: 'int_parsing' },
                    ],
                },
                { status: 422, statusText: 'Unprocessable Entity' },
            ),
        )
        vi.stubGlobal('fetch', fetchMock)

        try {
            await requestJson('/demo')
        } catch (error) {
            expect(error).toBeInstanceOf(ApiError)
            expect(error).toMatchObject({
                status: 422,
                validationIssues: [
                    { loc: ['body', 'name'], msg: 'Field required', type: 'missing' },
                    { loc: ['body', 'count'], msg: 'Input should be a valid integer', type: 'int_parsing' },
                ],
            })
            expect((error as Error).message).toContain('body.name: Field required')
            expect((error as Error).message).toContain('body.count: Input should be a valid integer')
        }
    })

    it('returns parsed JSON payload for successful responses', async () => {
        const fetchMock = vi.fn().mockResolvedValue(createJsonResponse({ ok: true }, { status: 200, statusText: 'OK' }))
        vi.stubGlobal('fetch', fetchMock)

        await expect(requestJson<{ ok: boolean }>('/demo')).resolves.toEqual({ ok: true })
    })
})

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
