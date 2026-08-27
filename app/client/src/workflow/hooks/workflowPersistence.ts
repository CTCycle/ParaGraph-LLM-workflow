import type { XYPosition } from '@xyflow/react'

const WORKFLOW_STATE_STORAGE_KEY = 'paragraph.workflow.state.v1'

export type PersistedWorkflowNode = {
    id: string
    manifest_id: string
    manifest_version: number
    position: XYPosition
    width?: number
    height?: number
    parameters: Record<string, unknown>
    collapsed: boolean
    items_expanded?: boolean
    pinged: boolean
    skipped: boolean
}

export type PersistedWorkflowEdge = {
    id: string
    source: string
    target: string
    source_handle: string | null
    target_handle: string | null
}

export type PersistedActiveExecution = {
    run_id: string
    poll_interval: number
}

export type PersistedWorkflowState = {
    nodes: PersistedWorkflowNode[]
    edges: PersistedWorkflowEdge[]
    is_library_visible: boolean
    is_grid_visible: boolean
    search: string
    selected_manifest_key: string | null
    execution_session_id: string
    active_run: PersistedActiveExecution | null
}

function isRecord(value: unknown): value is Record<string, unknown> {
    return typeof value === 'object' && value !== null
}

function isFiniteNumber(value: unknown): value is number {
    return typeof value === 'number' && Number.isFinite(value)
}

function coerceTextPayload(value: unknown): string {
    if (typeof value === 'string') {
        return value
    }
    if (typeof value === 'number' || typeof value === 'boolean') {
        return String(value)
    }
    return ''
}

export function readPersistedWorkflowState(): PersistedWorkflowState | null {
    if (typeof globalThis.localStorage === 'undefined') {
        return null
    }

    try {
        const raw = globalThis.localStorage.getItem(WORKFLOW_STATE_STORAGE_KEY)
        if (!raw) {
            return null
        }
        const parsed: unknown = JSON.parse(raw)
        if (!isRecord(parsed)) {
            return null
        }

        const nodes = Array.isArray(parsed.nodes)
            ? parsed.nodes
                .filter((value): value is Record<string, unknown> => isRecord(value))
                .map<PersistedWorkflowNode | null>((value) => {
                    const position = value.position
                    if (
                        typeof value.id !== 'string' ||
                        typeof value.manifest_id !== 'string' ||
                        !isFiniteNumber(value.manifest_version) ||
                        !isRecord(position) ||
                        !isFiniteNumber(position.x) ||
                        !isFiniteNumber(position.y)
                    ) {
                        return null
                    }
                    return {
                        id: value.id,
                        manifest_id: value.manifest_id,
                        manifest_version: value.manifest_version,
                        position: { x: position.x, y: position.y },
                        width: isFiniteNumber(value.width) ? value.width : undefined,
                        height: isFiniteNumber(value.height) ? value.height : undefined,
                        parameters: isRecord(value.parameters) ? value.parameters : {},
                        collapsed: Boolean(value.collapsed),
                        items_expanded: Boolean(value.items_expanded),
                        pinged: Boolean(value.pinged),
                        skipped: Boolean(value.skipped),
                    }
                })
                .filter((value): value is PersistedWorkflowNode => value !== null)
            : []

        const edges = Array.isArray(parsed.edges)
            ? parsed.edges
                .filter((value): value is Record<string, unknown> => isRecord(value))
                .map<PersistedWorkflowEdge | null>((value) => {
                    if (typeof value.source !== 'string' || typeof value.target !== 'string') {
                        return null
                    }
                    const sourceHandle = value.source_handle
                    const targetHandle = value.target_handle
                    return {
                        id:
                            typeof value.id === 'string' && value.id.trim()
                                ? value.id
                                : `${value.source}-${coerceTextPayload(sourceHandle)}-${value.target}-${coerceTextPayload(targetHandle)}`,
                        source: value.source,
                        target: value.target,
                        source_handle: typeof sourceHandle === 'string' ? sourceHandle : null,
                        target_handle: typeof targetHandle === 'string' ? targetHandle : null,
                    }
                })
                .filter((value): value is PersistedWorkflowEdge => value !== null)
            : []

        const activeRun = isRecord(parsed.active_run)
            && typeof parsed.active_run.run_id === 'string'
            && parsed.active_run.run_id.trim().length > 0
            && isFiniteNumber(parsed.active_run.poll_interval)
            && parsed.active_run.poll_interval > 0
            ? {
                run_id: parsed.active_run.run_id,
                poll_interval: parsed.active_run.poll_interval,
            }
            : null

        return {
            nodes,
            edges,
            is_library_visible:
                typeof parsed.is_library_visible === 'boolean' ? parsed.is_library_visible : false,
            is_grid_visible: typeof parsed.is_grid_visible === 'boolean' ? parsed.is_grid_visible : true,
            search: typeof parsed.search === 'string' ? parsed.search : '',
            selected_manifest_key:
                typeof parsed.selected_manifest_key === 'string' ? parsed.selected_manifest_key : null,
            execution_session_id:
                typeof parsed.execution_session_id === 'string'
                    ? parsed.execution_session_id.trim()
                    : '',
            active_run: activeRun,
        }
    } catch {
        return null
    }
}

export function persistWorkflowState(state: PersistedWorkflowState): void {
    if (typeof globalThis.localStorage === 'undefined') {
        return
    }
    globalThis.localStorage.setItem(WORKFLOW_STATE_STORAGE_KEY, JSON.stringify(state))
}
