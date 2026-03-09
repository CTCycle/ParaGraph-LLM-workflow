import { fetchProviderCatalog } from '../services/workflowApi'
import { ProviderCapability } from '../../workflow/schema/types'
import { createStore, useStore } from './store'

interface ProviderCatalogState {
    providers: ProviderCapability[]
    loading: boolean
    error: string | null
}

const providerCatalogStore = createStore<ProviderCatalogState>({
    providers: [],
    loading: false,
    error: null,
})

export const providerCatalogActions = {
    async load() {
        providerCatalogStore.setState((current) => ({ ...current, loading: true, error: null }))
        try {
            const payload = await fetchProviderCatalog()
            providerCatalogStore.setState({
                providers: payload.providers,
                loading: false,
                error: null,
            })
        } catch (error) {
            providerCatalogStore.setState((current) => ({
                ...current,
                loading: false,
                error: error instanceof Error ? error.message : 'Failed to load provider catalog',
            }))
        }
    },
}

export function useProviderCatalogStore<R>(selector: (state: ProviderCatalogState) => R): R {
    return useStore(providerCatalogStore, selector)
}