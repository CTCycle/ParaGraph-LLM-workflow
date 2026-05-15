import { afterEach, describe, expect, it, vi } from 'vitest'

import { getApiBase, requestJson } from './api'

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

    it('returns parsed JSON payload for successful responses', async () => {
        const fetchMock = vi.fn().mockResolvedValue(createJsonResponse({ ok: true }, { status: 200, statusText: 'OK' }))
        vi.stubGlobal('fetch', fetchMock)

        await expect(requestJson<{ ok: boolean }>('/demo')).resolves.toEqual({ ok: true })
    })
})

