import { useSyncExternalStore } from 'react'

type Listener = () => void

export interface StoreApi<T> {
    getState: () => T
    setState: (updater: T | ((current: T) => T)) => void
    subscribe: (listener: Listener) => () => void
}

export function createStore<T>(initialState: T): StoreApi<T> {
    let state = initialState
    const listeners = new Set<Listener>()

    const setState: StoreApi<T>['setState'] = (updater) => {
        const nextState = typeof updater === 'function' ? (updater as (current: T) => T)(state) : updater
        state = nextState
        listeners.forEach((listener) => listener())
    }

    const subscribe: StoreApi<T>['subscribe'] = (listener) => {
        listeners.add(listener)
        return () => listeners.delete(listener)
    }

    return {
        getState: () => state,
        setState,
        subscribe,
    }
}

export function useStore<T, R>(store: StoreApi<T>, selector: (state: T) => R): R {
    return useSyncExternalStore(store.subscribe, () => selector(store.getState()), () => selector(store.getState()))
}