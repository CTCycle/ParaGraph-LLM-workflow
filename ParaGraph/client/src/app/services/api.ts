const API_BASE = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/$/, '')

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