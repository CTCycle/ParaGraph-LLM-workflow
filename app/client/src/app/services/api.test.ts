import { afterEach, describe, expect, it, vi } from 'vitest'

import { ApiError, getApiBase, requestJson } from './api'

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

