import { describe, expect, it, vi } from 'vitest'

import {
    GUIDANCE_SCHEMA_VERSION,
    GUIDANCE_STORAGE_KEY,
    emptyGuidanceState,
    readGuidanceState,
    writeGuidanceState,
} from './guidancePersistence'

describe('guidance persistence', () => {
    it('returns an empty state for missing or invalid storage', () => {
        expect(readGuidanceState()).toEqual(emptyGuidanceState())

        window.localStorage.setItem(GUIDANCE_STORAGE_KEY, '{invalid')
        expect(readGuidanceState()).toEqual(emptyGuidanceState())

        window.localStorage.setItem(
            GUIDANCE_STORAGE_KEY,
            JSON.stringify({ schemaVersion: GUIDANCE_SCHEMA_VERSION + 1, items: {} }),
        )
        expect(readGuidanceState()).toEqual(emptyGuidanceState())
    })

    it('keeps valid records and discards malformed entries', () => {
        window.localStorage.setItem(
            GUIDANCE_STORAGE_KEY,
            JSON.stringify({
                schemaVersion: GUIDANCE_SCHEMA_VERSION,
                items: {
                    onboarding: { contentVersion: 2, status: 'dismissed' },
                    malformed: { contentVersion: '2', status: 'seen' },
                    unknown: { contentVersion: 1, status: 'unknown' },
                },
            }),
        )

        expect(readGuidanceState()).toEqual({
            schemaVersion: GUIDANCE_SCHEMA_VERSION,
            items: {
                onboarding: { contentVersion: 2, status: 'dismissed' },
            },
        })
    })

    it('treats storage failures as best effort', () => {
        const setItem = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
            throw new Error('storage unavailable')
        })

        expect(() => writeGuidanceState(emptyGuidanceState())).not.toThrow()
        setItem.mockRestore()
    })
})
