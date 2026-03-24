const ABSOLUTE_URL_PATTERN = /^[a-zA-Z][a-zA-Z\d+\-.]*:\/\//

function normalizeApiBase(rawValue: string | undefined): string {
    const candidate = (rawValue || '/api').trim()
    if (!candidate) {
        return '/api'
    }
    if (ABSOLUTE_URL_PATTERN.test(candidate)) {
        throw new Error('VITE_API_BASE_URL must be a relative path (for example /api). Absolute URLs are not allowed.')
    }
    const withLeadingSlash = candidate.startsWith('/') ? candidate : `/${candidate}`
    return withLeadingSlash.length > 1 && withLeadingSlash.endsWith('/')
        ? withLeadingSlash.slice(0, -1)
        : withLeadingSlash
}

const API_BASE = normalizeApiBase(import.meta.env.VITE_API_BASE_URL)

export async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
    const response = await fetch(`${API_BASE}${path}`, {
        headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
        ...init,
    })

    if (!response.ok) {
        let detail = `${response.status} ${response.statusText}`
        try {
            const payload = (await response.json()) as { detail?: string | string[] }
            if (Array.isArray(payload.detail)) {
                detail = payload.detail.join('; ')
            } else if (payload.detail) {
                detail = payload.detail
            }
        } catch {
            // Use default status detail.
        }
        throw new Error(detail)
    }

    return (await response.json()) as T
}

export function getApiBase(): string {
    return API_BASE
}
