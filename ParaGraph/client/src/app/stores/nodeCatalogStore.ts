import { fetchNodeCatalog } from '../services/workflowApi'
import { NodeDefinition } from '../../workflow/schema/types'
import { createStore, useStore } from './store'

interface NodeCatalogState {
    nodes: NodeDefinition[]
    loading: boolean
    error: string | null
}

const nodeCatalogStore = createStore<NodeCatalogState>({
    nodes: [],
    loading: false,
    error: null,
})

export const nodeCatalogActions = {
    async load() {
        nodeCatalogStore.setState((current) => ({ ...current, loading: true, error: null }))
        try {
            const payload = await fetchNodeCatalog()
            nodeCatalogStore.setState({
                nodes: payload.nodes,
                loading: false,
                error: null,
            })
        } catch (error) {
            nodeCatalogStore.setState((current) => ({
                ...current,
                loading: false,
                error: error instanceof Error ? error.message : 'Failed to load node catalog',
            }))
        }
    },
}

export function useNodeCatalogStore<R>(selector: (state: NodeCatalogState) => R): R {
    return useStore(nodeCatalogStore, selector)
}

export function getNodeCatalog(): NodeDefinition[] {
    return nodeCatalogStore.getState().nodes
}

export function findNodeDefinition(type: string): NodeDefinition | undefined {
    return nodeCatalogStore.getState().nodes.find((node) => node.type === type)
}