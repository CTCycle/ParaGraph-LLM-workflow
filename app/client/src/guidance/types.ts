export type GuidanceId = 'editor-onboarding' | 'editor-tour' | 'config-setup'

export type GuidanceTourId = 'editor'

export type GuidanceStatus = 'seen' | 'dismissed' | 'skipped' | 'completed'

export type GuidanceRecord = {
    contentVersion: number
    status: GuidanceStatus
}

export type GuidanceState = {
    schemaVersion: 1
    items: Record<string, GuidanceRecord>
}

export type TourPlacement = 'top' | 'right' | 'bottom' | 'left'

export type TourStepDefinition = {
    id: string
    target: string
    title: string
    body: string
    placement: TourPlacement
    media?: 'connect-ports'
}

export type GuidanceContextValue = {
    state: GuidanceState
    shouldShow: (id: GuidanceId, contentVersion: number) => boolean
    markSeen: (id: GuidanceId, contentVersion: number) => void
    markDismissed: (id: GuidanceId, contentVersion: number) => void
    markSkipped: (id: GuidanceId, contentVersion: number) => void
    markCompleted: (id: GuidanceId, contentVersion: number) => void
    requestedTour: GuidanceTourId | null
    requestTour: (tourId: GuidanceTourId) => void
    clearRequestedTour: () => void
}
