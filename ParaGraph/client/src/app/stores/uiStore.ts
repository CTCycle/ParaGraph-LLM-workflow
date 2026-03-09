import { createStore, useStore } from './store'

export interface UiState {
    cameraX: number
    cameraY: number
    zoom: number
    showGrid: boolean
    connectingFrom: { nodeId: string; port: string } | null
    pointerWorld: { x: number; y: number } | null
}

const uiStore = createStore<UiState>({
    cameraX: 0,
    cameraY: 0,
    zoom: 1,
    showGrid: true,
    connectingFrom: null,
    pointerWorld: null,
})

export const uiActions = {
    setCamera(cameraX: number, cameraY: number, zoom: number) {
        uiStore.setState((current) => ({
            ...current,
            cameraX,
            cameraY,
            zoom: Math.max(0.25, Math.min(2, zoom)),
        }))
    },

    panBy(dx: number, dy: number) {
        uiStore.setState((current) => ({
            ...current,
            cameraX: current.cameraX + dx,
            cameraY: current.cameraY + dy,
        }))
    },

    setZoom(zoom: number) {
        uiStore.setState((current) => ({ ...current, zoom: Math.max(0.25, Math.min(2, zoom)) }))
    },

    toggleGrid() {
        uiStore.setState((current) => ({ ...current, showGrid: !current.showGrid }))
    },

    startConnection(nodeId: string, port: string) {
        uiStore.setState((current) => ({ ...current, connectingFrom: { nodeId, port } }))
    },

    setPointerWorld(x: number, y: number) {
        uiStore.setState((current) => ({ ...current, pointerWorld: { x, y } }))
    },

    clearConnection() {
        uiStore.setState((current) => ({ ...current, connectingFrom: null, pointerWorld: null }))
    },
}

export function useUiStore<R>(selector: (state: UiState) => R): R {
    return useStore(uiStore, selector)
}

export function getUiState(): UiState {
    return uiStore.getState()
}