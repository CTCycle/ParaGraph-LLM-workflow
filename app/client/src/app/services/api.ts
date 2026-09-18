const ABSOLUTE_URL_PATTERN = /^[a-zA-Z][a-zA-Z\d+\-.]*:\/\//

function normalizeApiBase(rawValue: string | undefined): string {
    const candidate = rawValue?.trim()
    if (!candidate) {
        throw new Error('VITE_API_BASE_URL must be set in settings/.env.')
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

export type ApiValidationIssue = {
    loc?: unknown[]
    msg?: string
    type?: string
    [key: string]: unknown
}

export class ApiError extends Error {
    readonly status: number
    readonly statusText: string
    readonly detail: unknown
    readonly validationIssues: ApiValidationIssue[]

    constructor(
        message: string,
        response: Response,
        detail: unknown,
        validationIssues: ApiValidationIssue[] = [],
    ) {
        super(message)
        this.name = 'ApiError'
        this.status = response.status
        this.statusText = response.statusText
        this.detail = detail
        this.validationIssues = validationIssues
    }
}

function formatValidationIssue(issue: ApiValidationIssue): string {
    const message = typeof issue.msg === 'string' ? issue.msg : 'Invalid value'
    const location = Array.isArray(issue.loc) && issue.loc.length > 0
        ? `${issue.loc.join('.')}: `
        : ''
    return `${location}${message}`
}

function normalizeApiDetail(detail: unknown): {
    message: string
    validationIssues: ApiValidationIssue[]
} {
    if (typeof detail === 'string' && detail.trim()) {
        return { message: detail, validationIssues: [] }
    }
    if (Array.isArray(detail)) {
        const strings = detail.filter((item): item is string => typeof item === 'string')
        const issues = detail.filter((item): item is ApiValidationIssue => (
            typeof item === 'object' && item !== null && !Array.isArray(item)
        ))
        const messages = [
            ...strings,
            ...issues.map(formatValidationIssue),
        ].filter(Boolean)
        if (messages.length > 0) {
            return { message: messages.join('; '), validationIssues: issues }
        }
    }
    return { message: '', validationIssues: [] }
}

export async function createApiError(response: Response): Promise<ApiError> {
    const fallback = `${response.status} ${response.statusText}`
    let detail: unknown
    try {
        const payload = (await response.json()) as { detail?: unknown }
        detail = payload.detail
    } catch {
        // Use the HTTP status when the response body is not JSON.
    }
    const normalized = normalizeApiDetail(detail)
    return new ApiError(
        normalized.message || fallback,
        response,
        detail,
        normalized.validationIssues,
    )
}

export async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
    const response = await fetch(`${API_BASE}${path}`, {
        headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
        ...init,
    })

    if (!response.ok) {
        throw await createApiError(response)
    }

    return (await response.json()) as T
}

export function getApiBase(): string {
    return API_BASE
}
