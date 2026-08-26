import type { GuidanceRecord, GuidanceState, GuidanceStatus } from './types'

export const GUIDANCE_STORAGE_KEY = 'paragraph.guidance.state.v1'
export const GUIDANCE_SCHEMA_VERSION = 1

const GUIDANCE_STATUSES: GuidanceStatus[] = ['seen', 'dismissed', 'skipped', 'completed']

export function emptyGuidanceState(): GuidanceState {
    return {
        schemaVersion: GUIDANCE_SCHEMA_VERSION,
        items: {},
    }
}

function isRecord(value: unknown): value is Record<string, unknown> {
    return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function isGuidanceStatus(value: unknown): value is GuidanceStatus {
    return typeof value === 'string' && GUIDANCE_STATUSES.includes(value as GuidanceStatus)
}

function parseGuidanceRecord(value: unknown): GuidanceRecord | null {
    if (
        !isRecord(value) ||
        typeof value.contentVersion !== 'number' ||
        !Number.isInteger(value.contentVersion) ||
        value.contentVersion < 1 ||
        !isGuidanceStatus(value.status)
    ) {
        return null
    }
    return {
        contentVersion: value.contentVersion,
        status: value.status,
    }
}

export function readGuidanceState(): GuidanceState {
    try {
        const raw = globalThis.localStorage?.getItem(GUIDANCE_STORAGE_KEY)
        if (!raw) {
            return emptyGuidanceState()
        }

        const parsed: unknown = JSON.parse(raw)
        if (!isRecord(parsed) || parsed.schemaVersion !== GUIDANCE_SCHEMA_VERSION || !isRecord(parsed.items)) {
            return emptyGuidanceState()
        }

        const items: Record<string, GuidanceRecord> = {}
        for (const [id, value] of Object.entries(parsed.items)) {
            const record = parseGuidanceRecord(value)
            if (record) {
                items[id] = record
            }
        }

        return {
            schemaVersion: GUIDANCE_SCHEMA_VERSION,
            items,
        }
    } catch {
        return emptyGuidanceState()
    }
}

export function writeGuidanceState(state: GuidanceState): void {
    try {
        globalThis.localStorage?.setItem(GUIDANCE_STORAGE_KEY, JSON.stringify(state))
    } catch {
        // Guidance is best effort and must not block the application.
    }
}
