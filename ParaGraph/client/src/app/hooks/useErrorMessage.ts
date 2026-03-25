import { useCallback } from 'react'

type ErrorMessageResolver = (error: unknown, fallback: string) => string

export function useErrorMessage(): ErrorMessageResolver {
    return useCallback<ErrorMessageResolver>((error, fallback) => {
        return error instanceof Error ? error.message : fallback
    }, [])
}
