import { act, renderHook, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { createNodeManifest } from '../../test/fixtures'
import * as workflowApi from '../../app/services/workflowApi'
import { useNodeCatalog } from './useNodeCatalog'

vi.mock('../../app/services/workflowApi', () => ({
    fetchNodeCatalog: vi.fn(),
}))

describe('useNodeCatalog', () => {
    it('loads catalog on mount and supports deterministic reload transitions', async () => {
        const fetchNodeCatalogMock = vi.mocked(workflowApi.fetchNodeCatalog)
        fetchNodeCatalogMock
            .mockRejectedValueOnce(new Error('catalog temporarily unavailable'))
            .mockResolvedValueOnce({ nodes: [createNodeManifest()] })

        const { result } = renderHook(() => useNodeCatalog())

        await waitFor(() => {
            expect(result.current.loading).toBe(false)
        })
        expect(result.current.error).toBe('catalog temporarily unavailable')
        expect(result.current.catalog).toEqual([])

        await act(async () => {
            await result.current.reload()
        })

        expect(result.current.loading).toBe(false)
        expect(result.current.error).toBeNull()
        expect(result.current.catalog).toHaveLength(1)
        expect(result.current.catalog[0].id).toBe('PROMPT')
        expect(fetchNodeCatalogMock).toHaveBeenCalledTimes(2)
    })
})
