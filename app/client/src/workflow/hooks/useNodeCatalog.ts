import { useCallback, useEffect, useRef, useState } from 'react'

import { fetchNodeCatalog } from '../../app/services/nodesApi'
import { NodeManifest, VectorStoreCapabilities } from '../schema/types'

type UseNodeCatalogResult = {
    catalog: NodeManifest[]
    vectorStoreCapabilities: VectorStoreCapabilities[]
    loading: boolean
    error: string | null
    reload: () => Promise<void>
}

export function useNodeCatalog(): UseNodeCatalogResult {
    const [catalog, setCatalog] = useState<NodeManifest[]>([])
    const [vectorStoreCapabilities, setVectorStoreCapabilities] = useState<VectorStoreCapabilities[]>([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)
    const mountedRef = useRef(true)

    useEffect(() => {
        mountedRef.current = true
        return () => {
            mountedRef.current = false
        }
    }, [])

    const reload = useCallback(async (): Promise<void> => {
        setLoading(true)
        try {
            const payload = await fetchNodeCatalog()
            if (!mountedRef.current) {
                return
            }
            setCatalog(payload.nodes)
            setVectorStoreCapabilities(payload.vector_store_capabilities ?? [])
            setError(null)
        } catch (loadError) {
            if (!mountedRef.current) {
                return
            }
            setError(loadError instanceof Error ? loadError.message : 'Failed to load node catalog')
        } finally {
            if (mountedRef.current) {
                setLoading(false)
            }
        }
    }, [])

    useEffect(() => {
        void reload()
    }, [reload])

    return {
        catalog,
        vectorStoreCapabilities,
        loading,
        error,
        reload,
    }
}

