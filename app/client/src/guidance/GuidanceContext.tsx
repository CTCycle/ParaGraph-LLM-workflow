import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react'

import { emptyGuidanceState, readGuidanceState, writeGuidanceState } from './guidancePersistence'
import type { GuidanceContextValue, GuidanceId, GuidanceState, GuidanceStatus, GuidanceTourId } from './types'
import './Guidance.css'

const defaultGuidanceContext: GuidanceContextValue = {
    state: emptyGuidanceState(),
    shouldShow: () => true,
    markSeen: () => undefined,
    markDismissed: () => undefined,
    markSkipped: () => undefined,
    markCompleted: () => undefined,
    requestedTour: null,
    requestTour: () => undefined,
    clearRequestedTour: () => undefined,
}

const GuidanceContext = createContext<GuidanceContextValue>(defaultGuidanceContext)

type GuidanceProviderProps = {
    children: ReactNode
}

export function GuidanceProvider({ children }: GuidanceProviderProps) {
    const [state, setState] = useState<GuidanceState>(() => readGuidanceState())
    const [requestedTour, setRequestedTour] = useState<GuidanceTourId | null>(null)

    const shouldShow = useCallback(
        (id: GuidanceId, contentVersion: number): boolean => {
            const record = state.items[id]
            return !record || record.contentVersion < contentVersion
        },
        [state],
    )

    const updateStatus = useCallback((id: GuidanceId, contentVersion: number, status: GuidanceStatus): void => {
        setState((current) => {
            const next: GuidanceState = {
                schemaVersion: current.schemaVersion,
                items: {
                    ...current.items,
                    [id]: { contentVersion, status },
                },
            }
            writeGuidanceState(next)
            return next
        })
    }, [])

    const markSeen = useCallback((id: GuidanceId, contentVersion: number) => updateStatus(id, contentVersion, 'seen'), [updateStatus])
    const markDismissed = useCallback((id: GuidanceId, contentVersion: number) => updateStatus(id, contentVersion, 'dismissed'), [updateStatus])
    const markSkipped = useCallback((id: GuidanceId, contentVersion: number) => updateStatus(id, contentVersion, 'skipped'), [updateStatus])
    const markCompleted = useCallback((id: GuidanceId, contentVersion: number) => updateStatus(id, contentVersion, 'completed'), [updateStatus])
    const requestTour = useCallback((tourId: GuidanceTourId) => setRequestedTour(tourId), [])
    const clearRequestedTour = useCallback(() => setRequestedTour(null), [])

    const value = useMemo<GuidanceContextValue>(
        () => ({
            state,
            shouldShow,
            markSeen,
            markDismissed,
            markSkipped,
            markCompleted,
            requestedTour,
            requestTour,
            clearRequestedTour,
        }),
        [clearRequestedTour, markCompleted, markDismissed, markSeen, markSkipped, requestTour, requestedTour, shouldShow, state],
    )

    return <GuidanceContext.Provider value={value}>{children}</GuidanceContext.Provider>
}

export function useGuidance(): GuidanceContextValue {
    return useContext(GuidanceContext)
}
