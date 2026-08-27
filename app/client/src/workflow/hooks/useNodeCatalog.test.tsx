import { act, renderHook, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { createNodeManifest } from '../../test/fixtures'
import * as workflowApi from '../../app/services/nodesApi'
import { useNodeCatalog } from './useNodeCatalog'
import type { NodeManifest, VectorStoreCapabilities } from '../schema/types'

import chatHistoryMemoryManifestJson from '../../../../resources/nodes/chat_history_memory_v1.json'
import chatHistoryPersistedManifestJson from '../../../../resources/nodes/chat_history_persisted_v1.json'

vi.mock('../../app/services/nodesApi', () => ({
    fetchNodeCatalog: vi.fn(),
}))

describe('useNodeCatalog', () => {
    it('loads catalog on mount and supports deterministic reload transitions', async () => {
        const fetchNodeCatalogMock = vi.mocked(workflowApi.fetchNodeCatalog)
        fetchNodeCatalogMock
            .mockRejectedValueOnce(new Error('catalog temporarily unavailable'))
            .mockResolvedValueOnce({
                nodes: [createNodeManifest()],
                vector_store_capabilities: [
                    {
                        backend: 'faiss',
                        supported_metrics: ['cosine', 'l2', 'dot'],
                        supported_search_modes: ['vector'],
                        supported_search_engines: ['native', 'faiss_augmented'],
                        supports_namespaces: false,
                        supports_metadata_filtering: true,
                        supported_filter_operators: ['eq'],
                        supports_filter_groups: true,
                        supports_minimum_should_match: true,
                        supports_keyword_index: false,
                        supported_operations: ['search'],
                        score_semantics_by_metric: {
                            cosine: 'normalized_similarity',
                            l2: 'normalized_similarity',
                            dot: 'native_similarity',
                        },
                    },
                ] as VectorStoreCapabilities[],
            })

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
        expect(result.current.vectorStoreCapabilities[0].backend).toBe('faiss')
        expect(fetchNodeCatalogMock).toHaveBeenCalledTimes(2)
    })

    it('exposes new chat history nodes from catalog', async () => {
        const fetchNodeCatalogMock = vi.mocked(workflowApi.fetchNodeCatalog)
        fetchNodeCatalogMock.mockResolvedValueOnce({
            nodes: [
                chatHistoryMemoryManifestJson as NodeManifest,
                chatHistoryPersistedManifestJson as NodeManifest,
            ],
        })

        const { result } = renderHook(() => useNodeCatalog())
        await waitFor(() => {
            expect(result.current.loading).toBe(false)
        })

        const ids = result.current.catalog.map((item) => item.id)
        expect(ids).toContain('CHAT_HISTORY_MEMORY')
        expect(ids).toContain('CHAT_HISTORY_PERSISTED')
    })
})

