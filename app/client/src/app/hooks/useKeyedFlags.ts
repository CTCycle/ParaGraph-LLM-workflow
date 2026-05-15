import { useCallback, useState } from 'react'

type KeyedFlags = Record<string, boolean>

type UseKeyedFlagsResult = {
    flags: KeyedFlags
    mark: (key: string) => void
    clear: (key: string) => void
    has: (key: string) => boolean
}

export function useKeyedFlags(initialState: KeyedFlags = {}): UseKeyedFlagsResult {
    const [flags, setFlags] = useState<KeyedFlags>(initialState)

    const mark = useCallback((key: string) => {
        setFlags((current) => {
            if (current[key]) {
                return current
            }
            return {
                ...current,
                [key]: true,
            }
        })
    }, [])

    const clear = useCallback((key: string) => {
        setFlags((current) => {
            if (!current[key]) {
                return current
            }
            const next = { ...current }
            delete next[key]
            return next
        })
    }, [])

    const has = useCallback(
        (key: string): boolean => {
            return Boolean(flags[key])
        },
        [flags],
    )

    return {
        flags,
        mark,
        clear,
        has,
    }
}

