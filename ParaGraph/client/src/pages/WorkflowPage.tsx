import {
    type CSSProperties,
    type DragEvent as ReactDragEvent,
    type MouseEvent as ReactMouseEvent,
    type PointerEvent as ReactPointerEvent,
    useEffect,
    useMemo,
    useRef,
    useState,
} from 'react'
import {
    addEdge,
    Background,
    BackgroundVariant,
    Connection,
    ControlButton,
    Controls,
    Edge,
    Handle,
    MarkerType,
    Node,
    NodeProps,
    NodeResizer,
    Position,
    ReactFlow,
    ReactFlowProvider,
    XYPosition,
    useEdgesState,
    useNodesState,
    useReactFlow,
} from '@xyflow/react'

import {
    uploadNodeDirectory,
    checkDatabaseConnection,
    compileWorkflow,
    fetchProviderModels,
    importNodeManifest,
    pollExecution,
    startExecution,
    subscribeExecutionEvents,
} from '../app/services/workflowApi'
import { usePageMetadata } from '../app/hooks/usePageMetadata'
import { useNodeCatalog } from '../workflow/hooks/useNodeCatalog'
import { NODE_CATEGORY_LABELS, NODE_CATEGORY_ORDER } from '../workflow/schema/nodeCategory'
import {
    CompiledExecutionPlan,
    ExecutionRunState,
    NodeCategory,
    NodeManifest,
    NodeParameterDefinition,
    ProviderModelDefinition,
    VisualGraph,
    VisualNodeState,
    WorkflowConnection,
    WorkflowDefinition,
    WorkflowNodeInstance,
    WorkflowShareBundle,
} from '../workflow/schema/types'
import './WorkflowPage.css'

type WorkflowNodeData = {
    manifest: NodeManifest
    parameters: Record<string, unknown>
    collapsed: boolean
    pinged: boolean
    skipped: boolean
    isActive: boolean
    runtimeOutput: Record<string, unknown> | null
    providerModels: ProviderModelDefinition[]
    onParameterChange: (parameterName: string, value: unknown) => void
    onStatusChange: (message: string) => void
    onTogglePing: () => void
    onToggleCollapse: () => void
}

type NodeContextMenuState = {
    nodeId: string
    x: number
    y: number
}

type WorkflowCategoryGroup = {
    category: NodeCategory
    label: string
    nodes: NodeManifest[]
}

type CategoryExpansionState = Record<NodeCategory, boolean>

type NodeAccentStyle = CSSProperties & { '--node-accent': string }

type JsonValidationState = 'idle' | 'valid' | 'invalid'

type WorkflowExecutionErrorModal = {
    title: string
    message: string
}

type PersistedWorkflowNode = {
    id: string
    manifest_id: string
    manifest_version: number
    position: XYPosition
    width?: number
    height?: number
    parameters: Record<string, unknown>
    collapsed: boolean
    pinged: boolean
    skipped: boolean
}

type PersistedWorkflowEdge = {
    id: string
    source: string
    target: string
    source_handle: string | null
    target_handle: string | null
}

type PersistedWorkflowState = {
    nodes: PersistedWorkflowNode[]
    edges: PersistedWorkflowEdge[]
    is_library_visible: boolean
    is_grid_visible: boolean
    search: string
    selected_manifest_key: string | null
}


type CopiedNodeSnapshot = {
    manifest: NodeManifest
    parameters: Record<string, unknown>
    position: XYPosition
    width?: number
    height?: number
    collapsed: boolean
    pinged: boolean
    skipped: boolean
}

type SelectedWorkflowJson = {
    fileName: string
    jsonPayload: string
}
const NODE_MIN_WIDTH = 240
const NODE_MAX_WIDTH = 680
const NODE_MIN_HEIGHT = 140
const NODE_MAX_HEIGHT = 760
const NODE_LIBRARY_MIME = 'application/x-paragraph-node'
const WORKFLOW_TREE_STATE_STORAGE_KEY = 'paragraph.workflow.tree.expansion.v1'
const WORKFLOW_STATE_STORAGE_KEY = 'paragraph.workflow.state.v1'
const WORKFLOW_EDGE_MARKER = { type: MarkerType.ArrowClosed as const, width: 18, height: 18 }
const WORKFLOW_EDGE_STYLE = { stroke: '#5ba7ff', strokeWidth: 2.2 }
const WORKFLOW_BUNDLE_VERSION = 1
const WORKFLOW_BUNDLE_APP = 'ParaGraph'
const BROWSER_PICKER_CANCEL_GUARD_MS = 1200

type HandleKind = 'input' | 'output' | 'controller'
type ParsedHandle = { kind: HandleKind; name: string }

type ControllerScope = 'source' | 'target' | 'both'

function sanitizeWorkflowJsonFileName(value: string): string {
    const cleaned = value.trim().replace(/[<>:"/\\|?*\x00-\x1F]/g, '_')
    const base = cleaned || 'paragraph-workflow.json'
    return base.toLowerCase().endsWith('.json') ? base : `${base}.json`
}

function downloadWorkflowJson(payload: string, suggestedFileName: string): string {
    const fileName = sanitizeWorkflowJsonFileName(suggestedFileName)
    const blob = new Blob([payload], { type: 'application/json;charset=utf-8' })
    const objectUrl = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = objectUrl
    anchor.download = fileName
    anchor.rel = 'noopener'
    anchor.style.display = 'none'
    document.body.appendChild(anchor)
    anchor.click()
    anchor.remove()
    URL.revokeObjectURL(objectUrl)
    return fileName
}

function pickWorkflowJsonFromBrowser(): Promise<SelectedWorkflowJson | null> {
    return new Promise((resolve, reject) => {
        const input = document.createElement('input')
        input.type = 'file'
        input.accept = '.json,application/json'
        let changeHandled = false

        let settled = false
        const settle = (value: SelectedWorkflowJson | null): void => {
            if (settled) {
                return
            }
            settled = true
            window.removeEventListener('focus', handleWindowFocus)
            resolve(value)
        }

        const fail = (error: unknown): void => {
            if (settled) {
                return
            }
            settled = true
            window.removeEventListener('focus', handleWindowFocus)
            reject(error)
        }

        const handleWindowFocus = (): void => {
            window.setTimeout(() => {
                if (!settled && !changeHandled && !input.files?.length) {
                    settle(null)
                }
            }, BROWSER_PICKER_CANCEL_GUARD_MS)
        }

        input.addEventListener('change', () => {
            changeHandled = true
            const file = input.files?.item(0)
            if (!file) {
                settle(null)
                return
            }
            void file
                .text()
                .then((jsonPayload) => {
                    settle({ fileName: file.name, jsonPayload })
                })
                .catch((error) => {
                    fail(error instanceof Error ? error : new Error('Unable to read selected workflow JSON'))
                })
        })

        window.addEventListener('focus', handleWindowFocus, { once: true })
        input.click()
    })
}

function formatParameterLabel(parameterName: string): string {
    return parameterName.replace(/_/g, ' ')
}

type BrowserDirectorySelection = {
    files: File[]
    folderName: string
}

type BrowserFileSelection = {
    files: File[]
}

type SaveFileSelection = {
    fileName: string
}

type SaveFilePickerOptions = {
    suggestedName: string
    extension: string
}

type SaveFilePickerHandle = {
    name: string
}

type WindowWithSaveFilePicker = Window & {
    showSaveFilePicker?: (options?: Record<string, unknown>) => Promise<SaveFilePickerHandle>
}
function registerPickerCancelHandler(
    input: HTMLInputElement,
    wasChangeHandled: () => boolean,
    settleAsCancelled: () => void,
): () => void {
    // Prefer the dedicated "cancel" event when available to avoid race conditions
    // where a file picker focus event arrives before the change event.
    const supportsInputCancelEvent = 'oncancel' in document.createElement('input')
    if (supportsInputCancelEvent) {
        const handleCancel = (): void => settleAsCancelled()
        input.addEventListener('cancel', handleCancel)
        return () => input.removeEventListener('cancel', handleCancel)
    }

    const handleWindowFocus = (): void => {
        window.setTimeout(() => {
            if (!wasChangeHandled() && !input.files?.length) {
                settleAsCancelled()
            }
        }, BROWSER_PICKER_CANCEL_GUARD_MS)
    }
    window.addEventListener('focus', handleWindowFocus, { once: true })
    return () => window.removeEventListener('focus', handleWindowFocus)
}

function inferSelectedFolderName(files: File[]): string {
    const firstRelativePath = files[0]?.webkitRelativePath || files[0]?.name || ''
    const [root] = firstRelativePath.split('/').filter(Boolean)
    return root || 'selected folder'
}

function pickDirectoryFromBrowser(): Promise<BrowserDirectorySelection | null> {
    return new Promise((resolve) => {
        const input = document.createElement('input')
        input.type = 'file'
        input.multiple = true
        input.setAttribute('webkitdirectory', '')
        input.setAttribute('directory', '')
        let changeHandled = false

        let settled = false
        let unregisterCancelHandler = (): void => {}
        const settle = (value: BrowserDirectorySelection | null): void => {
            if (settled) {
                return
            }
            settled = true
            unregisterCancelHandler()
            resolve(value)
        }

        input.addEventListener('change', () => {
            changeHandled = true
            const selectedFiles = Array.from(input.files ?? [])
            if (selectedFiles.length === 0) {
                settle(null)
                return
            }
            settle({
                files: selectedFiles,
                folderName: inferSelectedFolderName(selectedFiles),
            })
        })

        unregisterCancelHandler = registerPickerCancelHandler(input, () => changeHandled, () => settle(null))
        input.click()
    })
}

function pickFilesFromBrowser(options: { multiple: boolean }): Promise<BrowserFileSelection | null> {
    return new Promise((resolve) => {
        const input = document.createElement('input')
        input.type = 'file'
        input.multiple = options.multiple
        let changeHandled = false

        let settled = false
        let unregisterCancelHandler = (): void => {}
        const settle = (value: BrowserFileSelection | null): void => {
            if (settled) {
                return
            }
            settled = true
            unregisterCancelHandler()
            resolve(value)
        }

        input.addEventListener('change', () => {
            changeHandled = true
            const selectedFiles = Array.from(input.files ?? [])
            if (selectedFiles.length === 0) {
                settle(null)
                return
            }
            settle({ files: selectedFiles })
        })

        unregisterCancelHandler = registerPickerCancelHandler(input, () => changeHandled, () => settle(null))
        input.click()
    })
}
function normalizeFileExtension(extension: string): string {
    const trimmed = extension.trim().toLowerCase()
    if (!trimmed) {
        return '.txt'
    }
    return trimmed.startsWith('.') ? trimmed : `.${trimmed}`
}

function ensureFileNameHasExtension(fileName: string, extension: string): string {
    const normalizedName = fileName.trim()
    const normalizedExtension = normalizeFileExtension(extension)
    if (!normalizedName) {
        return `output${normalizedExtension}`
    }
    return normalizedName.toLowerCase().endsWith(normalizedExtension)
        ? normalizedName
        : `${normalizedName}${normalizedExtension}`
}

function readBaseFileNameFromPath(pathValue: string): string {
    const normalized = pathValue.trim().replace(/\\/g, '/')
    const segments = normalized.split('/').filter(Boolean)
    return segments.length > 0 ? segments[segments.length - 1] : ''
}

async function pickSaveFileFromBrowser(options: SaveFilePickerOptions): Promise<SaveFileSelection | null> {
    const browserWindow = window as WindowWithSaveFilePicker
    const picker = browserWindow.showSaveFilePicker
    if (typeof picker !== 'function') {
        throw new Error('Save As is not supported in this browser')
    }
    const extension = normalizeFileExtension(options.extension)
    try {
        const handle = await picker({
            suggestedName: ensureFileNameHasExtension(options.suggestedName, extension),
            types: [
                {
                    description: 'Text document',
                    accept: {
                        'text/plain': [extension],
                    },
                },
            ],
        })
        return { fileName: ensureFileNameHasExtension(handle.name, extension) }
    } catch (error) {
        if (error instanceof DOMException && error.name === 'AbortError') {
            return null
        }
        throw error
    }
}

function isSaveTextOutputPathParameter(manifest: NodeManifest, parameter: NodeParameterDefinition): boolean {
    return manifest.id === 'SAVE_TEXT' && parameter.name === 'output_path'
}

function getSaveTextOutputPathBrowseLabel(pathValue: unknown, extensionValue: unknown): string {
    const normalizedPath = String(pathValue ?? '').trim()
    const normalizedExtension = normalizeFileExtension(String(extensionValue ?? '.txt'))
    const currentFileName = readBaseFileNameFromPath(normalizedPath)
    if (!currentFileName) {
        return `output${normalizedExtension}`
    }
    return ensureFileNameHasExtension(currentFileName, normalizedExtension)
}
function getControllers(manifest: NodeManifest): NonNullable<NodeManifest['controllers']> {
    return manifest.controllers ?? []
}

function getControllerScope(
    manifest: NodeManifest,
    controller: { scope?: ControllerScope },
): ControllerScope {
    if (controller.scope) {
        return controller.scope
    }
    // Backward-compatible fallback for manifests loaded before scope metadata existed.
    if (manifest.id === 'MODEL_PROVIDER') {
        return 'source'
    }
    return 'target'
}

function supportsControllerSource(
    manifest: NodeManifest,
    controller: { scope?: ControllerScope },
): boolean {
    const scope = getControllerScope(manifest, controller)
    return scope === 'source' || scope === 'both'
}

function supportsControllerTarget(
    manifest: NodeManifest,
    controller: { scope?: ControllerScope },
): boolean {
    const scope = getControllerScope(manifest, controller)
    return scope === 'target' || scope === 'both'
}
function toHandleId(kind: HandleKind, name: string): string {
    return `${kind}:${name}`
}

function parseHandleId(handleId: string): ParsedHandle | null {
    const separatorIndex = handleId.indexOf(':')
    if (separatorIndex <= 0) {
        return null
    }
    const kind = handleId.slice(0, separatorIndex)
    const name = handleId.slice(separatorIndex + 1)
    if ((kind !== 'input' && kind !== 'output' && kind !== 'controller') || !name) {
        return null
    }
    return { kind, name }
}

function resolveNodeDimensions(node: Node<WorkflowNodeData>): { width?: number; height?: number } {
    const widthFromStyle = node.style?.width
    const heightFromStyle = node.style?.height
    return {
        width:
            typeof node.width === 'number'
                ? node.width
                : typeof widthFromStyle === 'number'
                    ? widthFromStyle
                    : undefined,
        height:
            typeof node.height === 'number'
                ? node.height
                : typeof heightFromStyle === 'number'
                    ? heightFromStyle
                    : undefined,
    }
}

function cloneNodeParameters(parameters: Record<string, unknown>): Record<string, unknown> {
    if (typeof structuredClone === 'function') {
        return structuredClone(parameters)
    }
    try {
        return JSON.parse(JSON.stringify(parameters)) as Record<string, unknown>
    } catch {
        return { ...parameters }
    }
}

function defaultParameters(manifest: NodeManifest): Record<string, unknown> {
    return Object.fromEntries(manifest.parameters.map((parameter) => [parameter.name, parameter.default ?? '']))
}

function normalizePathParameter(parameters: Record<string, unknown>, canonicalName: 'storage_path' | 'folder_path'): void {
    const current = parameters[canonicalName]
    if (typeof current === 'string') {
        parameters[canonicalName] = current.trim()
    }
}

function normalizeNodePathParameters(manifest: NodeManifest, parameters: Record<string, unknown>): Record<string, unknown> {
    const nextParameters = cloneNodeParameters(parameters)
    if (manifest.id === 'LOAD_TEXT') {
        normalizePathParameter(nextParameters, 'storage_path')
    }
    if (manifest.id === 'LOAD_DOCUMENTS') {
        normalizePathParameter(nextParameters, 'folder_path')
    }
    return nextParameters
}
function normalizeJsonParameterValue(value: unknown): string {
    if (typeof value === 'string') {
        return value
    }
    try {
        return JSON.stringify(value ?? {}, null, 2)
    } catch {
        return String(value ?? '')
    }
}

function normalizeProvider(value: unknown): string {
    const text = String(value ?? '').trim().toLowerCase()
    return text === 'anthropic' ? 'claude' : text
}

function readNumericConstraint(constraints: Record<string, unknown>, key: string): number | undefined {
    const value = constraints[key]
    if (typeof value === 'number' && Number.isFinite(value)) {
        return value
    }
    if (typeof value === 'string' && value.trim()) {
        const parsed = Number(value)
        if (Number.isFinite(parsed)) {
            return parsed
        }
    }
    return undefined
}

function getNumberConstraints(parameter: NodeParameterDefinition): { min?: number; max?: number; step?: number } {
    return {
        min: readNumericConstraint(parameter.constraints, 'min'),
        max: readNumericConstraint(parameter.constraints, 'max'),
        step: readNumericConstraint(parameter.constraints, 'step'),
    }
}

function clampNumberToConstraints(value: number, constraints: { min?: number; max?: number }): number {
    let nextValue = value
    if (typeof constraints.min === 'number' && nextValue < constraints.min) {
        nextValue = constraints.min
    }
    if (typeof constraints.max === 'number' && nextValue > constraints.max) {
        nextValue = constraints.max
    }
    return nextValue
}

function parseValue(parameter: NodeParameterDefinition, rawValue: string | boolean): unknown {
    if (parameter.ui_control === 'toggle') {
        return Boolean(rawValue)
    }
    if (parameter.ui_control === 'number') {
        const constraints = getNumberConstraints(parameter)
        const fallbackValue =
            typeof parameter.default === 'number' && Number.isFinite(parameter.default) ? parameter.default : 0
        const text = String(rawValue)
        if (!text.trim()) {
            return clampNumberToConstraints(fallbackValue, constraints)
        }
        const parsed = Number(text)
        const numericValue = Number.isFinite(parsed) ? parsed : fallbackValue
        return clampNumberToConstraints(numericValue, constraints)
    }
    if (parameter.ui_control === 'json') {
        return String(rawValue)
    }
    if (parameter.ui_control === 'string-list') {
        return normalizeStringList(rawValue)
    }
    return rawValue
}

function isStructuredNode(manifest: NodeManifest): boolean {
    return manifest.id === 'LLM_STRUCTURED' || manifest.id.includes('STRUCTURED')
}

function isSqlConnectionNode(manifest: NodeManifest): manifest is NodeManifest & { id: 'SQL_DATABASE' | 'SQL_FILE_DATABASE' } {
    return manifest.id === 'SQL_DATABASE' || manifest.id === 'SQL_FILE_DATABASE'
}

function formatWorkflowExecutionError(error: unknown, runState: ExecutionRunState | null): string {
    const reason = error instanceof Error ? error.message : 'Execution failed for an unknown reason.'
    const failedStep = runState?.steps.find((step) => step.status === 'failed')
    const stepMessage = failedStep
        ? `Step ${failedStep.step_id} (${failedStep.node_type}) failed on node ${failedStep.node_id}.`
        : null

    return [
        'The workflow execution stopped because an error occurred.',
        '',
        `Reason: ${reason}`,
        stepMessage ? `Failed step: ${stepMessage}` : null,
        '',
        'Suggested checks:',
        '1. Verify required node parameters are set and valid.',
        '2. Verify upstream outputs and downstream input types are compatible.',
        '3. For external resources (DB/API/files), verify connectivity, permissions, and paths.',
    ]
        .filter((line): line is string => Boolean(line))
        .join('\n')
}

const LEGACY_MANIFEST_ID_MAP: Record<string, string> = {
    OLLAMA_LLM_CHAT: 'LLM_CHAT',
    CLOUD_LLM_CHAT: 'LLM_CHAT',
    HUGGINGFACE_LLM_CHAT: 'LLM_CHAT',
    OLLAMA_STRUCTURED_RESPONSE: 'LLM_STRUCTURED',
    CLOUD_STRUCTURED_RESPONSE: 'LLM_STRUCTURED',
    HUGGINGFACE_STRUCTURED_RESPONSE: 'LLM_STRUCTURED',
}

function manifestKey(manifest: NodeManifest): string {
    return `${manifest.id}:${manifest.version}`
}

function resolveManifestId(manifestId: string): string {
    return LEGACY_MANIFEST_ID_MAP[manifestId] ?? manifestId
}

function createDefaultExpandedCategoriesState(): CategoryExpansionState {
    return NODE_CATEGORY_ORDER.reduce<CategoryExpansionState>((accumulator, category) => {
        accumulator[category] = false
        return accumulator
    }, {} as CategoryExpansionState)
}

function createExpandedCategoriesState(): CategoryExpansionState {
    const fallback = createDefaultExpandedCategoriesState()
    if (typeof window === 'undefined') {
        return fallback
    }

    try {
        const raw = window.localStorage.getItem(WORKFLOW_TREE_STATE_STORAGE_KEY)
        if (!raw) {
            return fallback
        }
        const parsed: unknown = JSON.parse(raw)
        if (typeof parsed !== 'object' || parsed === null) {
            return fallback
        }
        const candidate = parsed as Record<string, unknown>
        return NODE_CATEGORY_ORDER.reduce<CategoryExpansionState>((accumulator, category) => {
            const stored = candidate[category]
            accumulator[category] = typeof stored === 'boolean' ? stored : fallback[category]
            return accumulator
        }, {} as CategoryExpansionState)
    } catch {
        return fallback
    }
}

function isRecord(value: unknown): value is Record<string, unknown> {
    return typeof value === 'object' && value !== null
}

function isFiniteNumber(value: unknown): value is number {
    return typeof value === 'number' && Number.isFinite(value)
}

type ImportedWorkflowPayload = {
    name: string
    definition: WorkflowDefinition
    visualGraph: VisualGraph
    requiredNodes: NodeManifest[]
}

function isNodeManifestPayload(value: unknown): value is NodeManifest {
    if (!isRecord(value)) {
        return false
    }
    return (
        typeof value.id === 'string' &&
        isFiniteNumber(value.version) &&
        typeof value.name === 'string' &&
        typeof value.category === 'string' &&
        typeof value.description === 'string' &&
        Array.isArray(value.inputs) &&
        Array.isArray(value.outputs) &&
        Array.isArray(value.parameters) &&
        isRecord(value.ui) &&
        isRecord(value.runtime)
    )
}

function isWorkflowNodeInstancePayload(value: unknown): value is WorkflowNodeInstance {
    if (!isRecord(value)) {
        return false
    }

    return (
        typeof value.node_id === 'string' &&
        typeof value.node_type === 'string' &&
        isFiniteNumber(value.node_version) &&
        isRecord(value.parameters) &&
        (value.skipped === undefined || typeof value.skipped === 'boolean')
    )
}

function isWorkflowConnectionPayload(value: unknown): value is WorkflowConnection {
    if (!isRecord(value)) {
        return false
    }

    const connectionType = value.connection_type
    const isValidConnectionType =
        connectionType === undefined || connectionType === 'data' || connectionType === 'controller'

    return (
        typeof value.from_node === 'string' &&
        typeof value.to_node === 'string' &&
        isValidConnectionType &&
        (value.from_output === undefined || typeof value.from_output === 'string') &&
        (value.to_input === undefined || typeof value.to_input === 'string') &&
        (value.from_controller === undefined || typeof value.from_controller === 'string') &&
        (value.to_controller === undefined || typeof value.to_controller === 'string')
    )
}

function isVisualNodeStatePayload(value: unknown): value is VisualNodeState {
    if (!isRecord(value)) {
        return false
    }

    return (
        typeof value.node_id === 'string' &&
        isFiniteNumber(value.x) &&
        isFiniteNumber(value.y) &&
        isFiniteNumber(value.width) &&
        isFiniteNumber(value.height) &&
        typeof value.collapsed === 'boolean' &&
        (value.pinged === undefined || typeof value.pinged === 'boolean') &&
        (value.skipped === undefined || typeof value.skipped === 'boolean')
    )
}

function isWorkflowDefinitionPayload(value: unknown): value is WorkflowDefinition {
    if (!isRecord(value)) {
        return false
    }

    return (
        isFiniteNumber(value.schema_version) &&
        Array.isArray(value.nodes) &&
        value.nodes.every(isWorkflowNodeInstancePayload) &&
        Array.isArray(value.connections) &&
        value.connections.every(isWorkflowConnectionPayload) &&
        isRecord(value.metadata)
    )
}

function isVisualGraphPayload(value: unknown): value is VisualGraph {
    if (!isRecord(value)) {
        return false
    }

    return (
        isFiniteNumber(value.schema_version) &&
        Array.isArray(value.nodes) &&
        value.nodes.every(isVisualNodeStatePayload) &&
        Array.isArray(value.groups) &&
        value.groups.every(isRecord) &&
        Array.isArray(value.comments) &&
        value.comments.every(isRecord)
    )
}

function isWorkflowShareBundlePayload(value: unknown): value is WorkflowShareBundle {
    if (!isRecord(value) || !isRecord(value.workflow)) {
        return false
    }

    const workflow = value.workflow as Record<string, unknown>
    return (
        isFiniteNumber(value.bundle_version) &&
        typeof value.app === 'string' &&
        typeof value.created_at === 'string' &&
        Array.isArray(value.required_nodes) &&
        value.required_nodes.every(isNodeManifestPayload) &&
        typeof workflow.name === 'string' &&
        isWorkflowDefinitionPayload(workflow.definition) &&
        isVisualGraphPayload(workflow.visual_graph)
    )
}

function readImportedWorkflowPayload(value: unknown): ImportedWorkflowPayload {
    if (isWorkflowShareBundlePayload(value)) {
        return {
            name: value.workflow.name,
            definition: value.workflow.definition,
            visualGraph: value.workflow.visual_graph,
            requiredNodes: value.required_nodes,
        }
    }

    if (
        isRecord(value) &&
        typeof value.name === 'string' &&
        isWorkflowDefinitionPayload(value.definition) &&
        isVisualGraphPayload(value.visual_graph)
    ) {
        return {
            name: value.name,
            definition: value.definition,
            visualGraph: value.visual_graph,
            requiredNodes: [],
        }
    }

    throw new Error('Unsupported workflow JSON. Expected a ParaGraph workflow bundle.')
}

function readPersistedWorkflowState(): PersistedWorkflowState | null {
    if (typeof window === 'undefined') {
        return null
    }

    try {
        const raw = window.localStorage.getItem(WORKFLOW_STATE_STORAGE_KEY)
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
                                : `${value.source}-${String(sourceHandle ?? '')}-${value.target}-${String(targetHandle ?? '')}`,
                        source: value.source,
                        target: value.target,
                        source_handle: typeof sourceHandle === 'string' ? sourceHandle : null,
                        target_handle: typeof targetHandle === 'string' ? targetHandle : null,
                    }
                })
                .filter((value): value is PersistedWorkflowEdge => value !== null)
            : []
        return {
            nodes,
            edges,
            is_library_visible:
                typeof parsed.is_library_visible === 'boolean' ? parsed.is_library_visible : false,
            is_grid_visible: typeof parsed.is_grid_visible === 'boolean' ? parsed.is_grid_visible : true,
            search: typeof parsed.search === 'string' ? parsed.search : '',
            selected_manifest_key:
                typeof parsed.selected_manifest_key === 'string' ? parsed.selected_manifest_key : null,
        }
    } catch {
        return null
    }
}

function persistWorkflowState(state: PersistedWorkflowState): void {
    if (typeof window === 'undefined') {
        return
    }
    window.localStorage.setItem(WORKFLOW_STATE_STORAGE_KEY, JSON.stringify(state))
}

function buildNodeSummary(manifest: NodeManifest): string {
    const text = manifest.description.trim()
    if (!text) {
        return 'Configure inputs and parameters for this node.'
    }

    const segments = text
        .split(/(?<=[.!?])\s+/)
        .map((part) => part.trim())
        .filter(Boolean)

    if (segments.length === 0) {
        return text
    }
    return segments.slice(0, 2).join(' ')
}


function formatParameterValue(parameter: NodeParameterDefinition, value: unknown): string {
    if (parameter.ui_control === 'json') {
        if (typeof value === 'string') {
            return value
        }
        try {
            return JSON.stringify(value ?? {}, null, 2)
        } catch {
            return String(value ?? '')
        }
    }
    if (parameter.ui_control === 'string-list') {
        return formatPathListValue(value)
    }
    return String(value ?? '')
}

function formatRuntimeOutput(value: Record<string, unknown> | null): string {
    if (!value || Object.keys(value).length === 0) {
        return ''
    }
    if (typeof value.text === 'string') {
        return value.text
    }
    try {
        return JSON.stringify(value, null, 2)
    } catch {
        return String(value)
    }
}

function formatJsonOutputRuntime(value: Record<string, unknown> | null): string {
    if (!value || Object.keys(value).length === 0) {
        return ''
    }
    const candidate = Object.prototype.hasOwnProperty.call(value, 'json') ? value.json : value
    if (typeof candidate === 'string') {
        const trimmed = candidate.trim()
        if (!trimmed) {
            return ''
        }
        try {
            const parsed = JSON.parse(trimmed)
            return JSON.stringify(parsed, null, 2)
        } catch {
            return candidate
        }
    }
    try {
        return JSON.stringify(candidate, null, 2)
    } catch {
        return String(candidate)
    }
}
function normalizeStringList(value: unknown): string[] {
    if (Array.isArray(value)) {
        return value
            .filter((item): item is string => typeof item === 'string')
            .map((item) => item.trim())
            .filter(Boolean)
    }
    if (typeof value === 'string') {
        const trimmed = value.trim()
        if (!trimmed) {
            return []
        }
        try {
            const parsed: unknown = JSON.parse(trimmed)
            if (Array.isArray(parsed)) {
                return normalizeStringList(parsed)
            }
        } catch {
            // Fall back to newline-delimited parsing.
        }
        return trimmed
            .split(/\r?\n/)
            .map((item) => item.trim())
            .filter(Boolean)
    }
    return []
}

function formatPathListValue(value: unknown): string {
    return normalizeStringList(value).join('\n')
}

function isMultilineControl(parameter: NodeParameterDefinition): boolean {
    return (
        parameter.ui_control === 'textarea'
        || parameter.ui_control === 'json'
        || parameter.ui_control === 'file-list'
        || parameter.ui_control === 'string-list'
    )

}
function preventNodeInteractionDrag(event: ReactPointerEvent<HTMLElement> | ReactMouseEvent<HTMLElement>): void {
    event.stopPropagation()
}

function isEditableEventTarget(target: EventTarget | null): boolean {
    if (!(target instanceof HTMLElement)) {
        return false
    }
    if (target.isContentEditable) {
        return true
    }
    const tagName = target.tagName.toLowerCase()
    if (tagName === 'input' || tagName === 'textarea' || tagName === 'select') {
        return true
    }
    return Boolean(target.closest('input, textarea, select, [contenteditable="true"]'))
}

function getDynamicModelOptions(
    manifest: NodeManifest,
    parameters: Record<string, unknown>,
    providerModels: ProviderModelDefinition[],
): ProviderModelDefinition[] {
    if (manifest.id === 'MODEL_PROVIDER') {
        const provider = normalizeProvider(parameters.provider ?? 'ollama') || 'ollama'
        return providerModels.filter((item) => item.provider === provider)
    }
    return []
}

function buildInitialNodeParameters(
    manifest: NodeManifest,
    providerModels: ProviderModelDefinition[],
    inputParameters?: Record<string, unknown>,
): Record<string, unknown> {
    const initialParameters = {
        ...defaultParameters(manifest),
        ...(inputParameters ? cloneNodeParameters(inputParameters) : {}),
    }
    const normalizedParameters = normalizeNodePathParameters(manifest, initialParameters)
    const initialModels = getDynamicModelOptions(manifest, normalizedParameters, providerModels)
    if (manifest.id === 'MODEL_PROVIDER' && initialModels.length > 0 && !String(normalizedParameters.model_name ?? '').trim()) {
        normalizedParameters.model_name = initialModels[0].model
    }
    for (const parameter of manifest.parameters) {
        if (parameter.ui_control !== 'json') {
            continue
        }
        const value = normalizedParameters[parameter.name] ?? parameter.default ?? ''
        normalizedParameters[parameter.name] = normalizeJsonParameterValue(value)
    }
    return normalizedParameters
}

function formatWidgetOptionLabel(value: string): string {
    return value.replace(/_/g, ' ')
}

function getParameterOptions(
    parameter: NodeParameterDefinition,
    manifest: NodeManifest,
    parameters: Record<string, unknown>,
    providerModels: ProviderModelDefinition[],
): Array<{ value: string; label: string }> {
    if (parameter.name === 'model_name') {
        return getDynamicModelOptions(manifest, parameters, providerModels).map((item) => ({
            value: item.model,
            label: item.label,
        }))
    }

    const options = parameter.constraints.options
    if (!Array.isArray(options)) {
        return []
    }
    return options
        .filter((option): option is string => typeof option === 'string')
        .map((option) => ({ value: option, label: formatWidgetOptionLabel(option) }))
}

function ManifestNode({ data, selected }: NodeProps<Node<WorkflowNodeData>>) {
    const nodeStyle: NodeAccentStyle = { '--node-accent': data.manifest.ui.accent_color }
    const structured = isStructuredNode(data.manifest)
    const isJsonOutputNode = data.manifest.id === 'JSON_OUTPUT'
    const sqlConnectionNode = isSqlConnectionNode(data.manifest)
    const [browseTarget, setBrowseTarget] = useState<string | null>(null)
    const [jsonDrafts, setJsonDrafts] = useState<Record<string, string>>({})
    const [jsonValidationStates, setJsonValidationStates] = useState<Record<string, JsonValidationState>>({})
    const [runtimeJsonValidation, setRuntimeJsonValidation] = useState<JsonValidationState>('idle')
    const [connectionCheckState, setConnectionCheckState] = useState<'idle' | 'checking' | 'success' | 'error'>('idle')

    const runtimeOutputText = isJsonOutputNode ? formatJsonOutputRuntime(data.runtimeOutput) : formatRuntimeOutput(data.runtimeOutput)
    const shouldShowRuntimeOutput = Boolean(runtimeOutputText) || isJsonOutputNode

    useEffect(() => {
        setJsonDrafts((current) => {
            const nextJsonDrafts: Record<string, string> = {}
            for (const parameter of data.manifest.parameters) {
                if (parameter.ui_control !== 'json') {
                    continue
                }
                const value = data.parameters[parameter.name] ?? parameter.default ?? ''
                nextJsonDrafts[parameter.name] = normalizeJsonParameterValue(value)
            }

            const currentKeys = Object.keys(current)
            const nextKeys = Object.keys(nextJsonDrafts)
            if (currentKeys.length !== nextKeys.length) {
                return nextJsonDrafts
            }
            for (const key of nextKeys) {
                if (current[key] !== nextJsonDrafts[key]) {
                    return nextJsonDrafts
                }
            }
            return current
        })
    }, [data.manifest.parameters, data.parameters])

    useEffect(() => {
        setConnectionCheckState('idle')
    }, [data.manifest.id, data.parameters])

    useEffect(() => {
        setRuntimeJsonValidation('idle')
    }, [runtimeOutputText])

    function validateJsonDraft(parameterName: string, rawValue: string): void {
        const candidate = rawValue.trim()
        try {
            const parsed = JSON.parse(candidate)
            const pretty = JSON.stringify(parsed, null, 2)
            setJsonDrafts((current) => ({ ...current, [parameterName]: pretty }))
            setJsonValidationStates((current) => ({ ...current, [parameterName]: 'valid' }))
            data.onParameterChange(parameterName, pretty)
            data.onStatusChange('JSON is valid')
        } catch (error) {
            setJsonValidationStates((current) => ({ ...current, [parameterName]: 'invalid' }))
            data.onStatusChange(error instanceof Error ? `Invalid JSON: ${error.message}` : 'Invalid JSON payload')
        }
    }

    function validateRuntimeJsonOutput(): void {
        try {
            JSON.parse(runtimeOutputText)
            setRuntimeJsonValidation('valid')
            data.onStatusChange('JSON output is valid')
        } catch (error) {
            setRuntimeJsonValidation('invalid')
            data.onStatusChange(error instanceof Error ? `Output is not valid JSON: ${error.message}` : 'Output is not valid JSON')
        }
    }

    async function handleConnectionCheck(): Promise<void> {
        if (!sqlConnectionNode) {
            return
        }
        setConnectionCheckState('checking')
        try {
            const response = await checkDatabaseConnection(data.manifest.id as 'SQL_DATABASE' | 'SQL_FILE_DATABASE', data.manifest.version, data.parameters)
            if (response.ok) {
                setConnectionCheckState('success')
                data.onStatusChange(response.message)
            } else {
                setConnectionCheckState('error')
                data.onStatusChange(response.message)
            }
        } catch (error) {
            setConnectionCheckState('error')
            data.onStatusChange(error instanceof Error ? error.message : 'Database connectivity check failed')
        }
    }

    async function handlePathBrowse(parameter: NodeParameterDefinition): Promise<void> {
        setBrowseTarget(parameter.name)
        try {
            if (isSaveTextOutputPathParameter(data.manifest, parameter)) {
                const extension = String(data.parameters.extension ?? '.txt')
                const currentPath = data.parameters[parameter.name]
                const suggestedName = getSaveTextOutputPathBrowseLabel(currentPath, extension)
                const saveSelection = await pickSaveFileFromBrowser({
                    suggestedName,
                    extension,
                })
                if (!saveSelection) {
                    data.onStatusChange('Save As selection cancelled')
                    return
                }
                data.onParameterChange(parameter.name, saveSelection.fileName)
                data.onStatusChange(`Save target set to ${saveSelection.fileName}`)
                return
            }

            if (parameter.ui_control === 'directory') {
                const browserSelection = await pickDirectoryFromBrowser()
                if (!browserSelection) {
                    data.onStatusChange('Directory selection cancelled')
                    return
                }

                const uploaded = await uploadNodeDirectory(browserSelection.files)
                const stagedPath = String(uploaded.path ?? '').trim()
                if (!stagedPath) {
                    throw new Error('Folder upload succeeded but returned an empty path')
                }
                data.onParameterChange(parameter.name, stagedPath)
                const uploadedCountLabel = uploaded.file_count === 1 ? 'file' : 'files'
                data.onStatusChange('Selected ' + browserSelection.folderName + ' (' + uploaded.file_count + ' ' + uploadedCountLabel + ')')
                return
            }

            if (parameter.ui_control === 'file' || parameter.ui_control === 'file-list') {
                const browserSelection = await pickFilesFromBrowser({ multiple: parameter.ui_control === 'file-list' })
                if (!browserSelection) {
                    data.onStatusChange('File selection cancelled')
                    return
                }

                const uploaded = await uploadNodeDirectory(browserSelection.files)
                const normalizedFiles = uploaded.files
                    .map((pathValue) => String(pathValue).trim())
                    .filter((pathValue) => Boolean(pathValue))
                if (parameter.ui_control === 'file-list') {
                    if (normalizedFiles.length === 0) {
                        throw new Error('File upload succeeded but returned no files')
                    }
                    data.onParameterChange(parameter.name, normalizedFiles)
                    data.onStatusChange(`Selected ${normalizedFiles.length} file${normalizedFiles.length === 1 ? '' : 's'}`)
                    return
                }

                const firstPath = normalizedFiles[0]
                if (!firstPath) {
                    throw new Error('File upload succeeded but returned no file path')
                }
                data.onParameterChange(parameter.name, firstPath)
                data.onStatusChange(`Selected ${firstPath}`)
                return
            }
        } catch (error) {
            data.onStatusChange(error instanceof Error ? error.message : 'Unable to browse for a path')
        } finally {
            setBrowseTarget(null)
        }
    }
    const controllers = getControllers(data.manifest)
    const sourceControllers = controllers.filter((controller) => supportsControllerSource(data.manifest, controller))
    const targetControllers = controllers.filter((controller) => supportsControllerTarget(data.manifest, controller))
    return (
        <div
            className="workflow-node"
            style={nodeStyle}
            data-selected={selected || undefined}
            data-active={data.isActive || undefined}
            data-collapsed={data.collapsed || undefined}
            data-pinged={data.pinged || undefined}
            data-skipped={data.skipped || undefined}
            data-structured={structured || undefined}
            data-json-output={isJsonOutputNode || undefined}
        >
            <NodeResizer
                isVisible={selected}
                minWidth={NODE_MIN_WIDTH}
                maxWidth={NODE_MAX_WIDTH}
                minHeight={NODE_MIN_HEIGHT}
                maxHeight={NODE_MAX_HEIGHT}
                lineClassName="workflow-node-resize-line"
                handleClassName="workflow-node-resize-handle"
            />
            <div className="workflow-node-header">
                <div className="workflow-node-title-block">
                    <strong>{data.manifest.name}</strong>
                    <p className="workflow-node-subtitle">{buildNodeSummary(data.manifest)}</p>
                </div>
                <div className="workflow-node-header-actions">
                    {data.isActive && <span className="workflow-node-badge workflow-node-badge-running">Running</span>}
                    {data.skipped && <span className="workflow-node-badge workflow-node-badge-skipped">Skipped</span>}
                    {structured && <span className="workflow-node-badge">Structured</span>}
                    {sqlConnectionNode && (
                        <button
                            type="button"
                            className={`workflow-node-db-check workflow-node-db-check-${connectionCheckState} nodrag nopan`}
                            aria-label="Check database connection"
                            title="Check database connection"
                            onPointerDown={preventNodeInteractionDrag}
                            onMouseDown={preventNodeInteractionDrag}
                            onClick={() => void handleConnectionCheck()}
                        >
                            {connectionCheckState === 'checking' ? '...' : 'DB'}
                        </button>
                    )}
                    <button
                        type="button"
                        className="workflow-node-ping nodrag nopan"
                        aria-label={data.pinged ? 'Unping node' : 'Ping node'}
                        title={data.pinged ? 'Unping node' : 'Ping node'}
                        onPointerDown={preventNodeInteractionDrag}
                        onMouseDown={preventNodeInteractionDrag}
                        onClick={(event) => {
                            event.stopPropagation()
                            data.onTogglePing()
                        }}
                    >
                        {data.pinged ? '◎' : '○'}
                    </button>
                    <button
                        type="button"
                        className="workflow-node-toggle nodrag nopan"
                        aria-label={data.collapsed ? 'Expand node' : 'Collapse node'}
                        title={data.collapsed ? 'Expand node' : 'Collapse node'}
                        onPointerDown={preventNodeInteractionDrag}
                        onMouseDown={preventNodeInteractionDrag}
                        onClick={(event) => {
                            event.stopPropagation()
                            data.onToggleCollapse()
                        }}
                    >
                        {data.collapsed ? '+' : '-'}
                    </button>
                </div>
            </div>

            <div className="workflow-node-ports">
                <div className="workflow-node-port-column">
                    {data.manifest.inputs.map((port) => (
                        <div key={port.name} className="workflow-node-port workflow-node-port-input">
                            <Handle type="target" position={Position.Left} id={toHandleId('input', port.name)} />
                            <span>{port.name}</span>
                        </div>
                    ))}
                    {targetControllers.map((port) => (
                        <div key={`target-${port.name}`} className="workflow-node-port workflow-node-port-input workflow-node-port-controller-target">
                            <Handle
                                type="target"
                                position={Position.Left}
                                id={toHandleId('controller', port.name)}
                                className="workflow-node-handle workflow-node-handle-controller workflow-node-handle-controller-target"
                            />
                            <span>{port.name}</span>
                        </div>
                    ))}
                </div>
                <div className="workflow-node-port-column workflow-node-port-column-right">
                    {data.manifest.outputs.map((port) => (
                        <div key={port.name} className="workflow-node-port workflow-node-port-output">
                            <span>{port.name}</span>
                            <Handle type="source" position={Position.Right} id={toHandleId('output', port.name)} />
                        </div>
                    ))}
                    {sourceControllers.map((port) => (
                        <div key={`source-${port.name}`} className="workflow-node-port workflow-node-port-output workflow-node-port-controller-source">
                            <span>{port.name}</span>
                            <Handle
                                type="source"
                                position={Position.Right}
                                id={toHandleId('controller', port.name)}
                                className="workflow-node-handle workflow-node-handle-controller workflow-node-handle-controller-source"
                            />
                        </div>
                    ))}
                </div>
            </div>

            {!data.collapsed && data.manifest.parameters.length > 0 && (
                <div className="workflow-node-parameters">
                    <div className="workflow-node-parameters-grid">
                        {data.manifest.parameters.map((parameter) => {
                            const value = data.parameters[parameter.name] ?? parameter.default ?? ''
                            const options = getParameterOptions(parameter, data.manifest, data.parameters, data.providerModels)
                            const multiline = isMultilineControl(parameter)
                            const showParameterLabel = parameter.ui_control !== 'textarea'
                            const showHeader = showParameterLabel || parameter.ui_control === 'file-list'
                            const isBrowsing = browseTarget === parameter.name
                            const selectedPaths = parameter.ui_control === 'file-list' ? normalizeStringList(value) : []
                            const numberConstraints = parameter.ui_control === 'number' ? getNumberConstraints(parameter) : null
                            return (
                                <label
                                    key={parameter.name}
                                    className={
                                        multiline
                                            ? 'workflow-node-parameter-field workflow-node-parameter-field-multiline'
                                            : 'workflow-node-parameter-field'
                                    }
                                >
                                    {showHeader && (
                                        <div className="workflow-node-parameter-header">
                                            {showParameterLabel && <span className="workflow-node-parameter-label">{formatParameterLabel(parameter.name)}</span>}
                                            {parameter.ui_control === 'file-list' && (
                                                <div className="workflow-node-parameter-actions">
                                                    <button
                                                        type="button"
                                                        className="workflow-node-picker-button"
                                                        disabled={isBrowsing}
                                                        onClick={() => void handlePathBrowse(parameter)}
                                                    >
                                                        {isBrowsing ? '...' : 'Browse'}
                                                    </button>
                                                    {selectedPaths.length > 0 && (
                                                        <button
                                                            type="button"
                                                            className="workflow-node-picker-clear"
                                                            onClick={() => data.onParameterChange(parameter.name, [])}
                                                        >
                                                            Clear
                                                        </button>
                                                    )}
                                                </div>
                                            )}
                                        </div>
                                    )}
                                    <div className="workflow-node-parameter-value">
                                        {parameter.ui_control === 'textarea' ? (
                                            <textarea
                                                rows={2}
                                                className="workflow-node-parameter-textbox nodrag nopan"
                                                value={formatParameterValue(parameter, value)}
                                                onPointerDown={preventNodeInteractionDrag}
                                                onMouseDown={preventNodeInteractionDrag}
                                                onChange={(event) => data.onParameterChange(parameter.name, parseValue(parameter, event.target.value))}
                                            />
                                        ) : parameter.ui_control === 'json' ? (
                                            <div className="workflow-node-json-widget">
                                                <button
                                                    type="button"
                                                    className="workflow-node-json-validate nodrag nopan"
                                                    onPointerDown={preventNodeInteractionDrag}
                                                    onMouseDown={preventNodeInteractionDrag}
                                                    onClick={() =>
                                                        validateJsonDraft(
                                                            parameter.name,
                                                            jsonDrafts[parameter.name] ?? normalizeJsonParameterValue(value),
                                                        )
                                                    }
                                                >
                                                    Validate
                                                </button>
                                                <textarea
                                                    rows={10}
                                                    className={`workflow-node-json-input workflow-node-json-input-${jsonValidationStates[parameter.name] ?? 'idle'} nodrag nopan`}
                                                    value={jsonDrafts[parameter.name] ?? normalizeJsonParameterValue(value)}
                                                    onPointerDown={preventNodeInteractionDrag}
                                                    onMouseDown={preventNodeInteractionDrag}
                                                    onChange={(event) => {
                                                        const nextValue = event.target.value
                                                        setJsonDrafts((current) => ({ ...current, [parameter.name]: nextValue }))
                                                        setJsonValidationStates((current) => ({ ...current, [parameter.name]: 'idle' }))
                                                        data.onParameterChange(parameter.name, parseValue(parameter, nextValue))
                                                    }}
                                                />
                                            </div>
                                        ) : parameter.ui_control === 'string-list' ? (
                                            <textarea
                                                rows={4}
                                                className="workflow-node-path-list-input nodrag nopan"
                                                value={formatPathListValue(value)}
                                                onPointerDown={preventNodeInteractionDrag}
                                                onMouseDown={preventNodeInteractionDrag}
                                                onChange={(event) => data.onParameterChange(parameter.name, normalizeStringList(event.target.value))}
                                            />
                                        ) : parameter.ui_control === 'file-list' ? (
                                            <textarea
                                                rows={4}
                                                className="workflow-node-path-list-input nodrag nopan"
                                                value={formatPathListValue(value)}
                                                onPointerDown={preventNodeInteractionDrag}
                                                onMouseDown={preventNodeInteractionDrag}
                                                onChange={(event) => data.onParameterChange(parameter.name, normalizeStringList(event.target.value))}
                                            />
                                        ) : parameter.ui_control === 'toggle' ? (
                                            <input
                                                className="workflow-node-toggle-input"
                                                type="checkbox"
                                                checked={Boolean(value)}
                                                onChange={(event) => data.onParameterChange(parameter.name, parseValue(parameter, event.target.checked))}
                                            />
                                        ) : parameter.ui_control === 'select' && options.length > 0 ? (
                                            <select
                                                className="nodrag nopan"
                                                value={String(value ?? '')}
                                                onPointerDown={preventNodeInteractionDrag}
                                                onMouseDown={preventNodeInteractionDrag}
                                                onChange={(event) => data.onParameterChange(parameter.name, parseValue(parameter, event.target.value))}
                                            >
                                                {!String(value ?? '') && <option value="">Select...</option>}
                                                {options.map((option) => (
                                                    <option key={option.value} value={option.value}>
                                                        {option.label}
                                                    </option>
                                                ))}
                                            </select>
                                        ) : parameter.ui_control === 'file'
                                            || parameter.ui_control === 'directory'
                                            || isSaveTextOutputPathParameter(data.manifest, parameter) ? (
                                            <div className="workflow-node-inline-input">
                                                <input
                                                    className="nodrag nopan"
                                                    type="text"
                                                    value={formatParameterValue(parameter, value)}
                                                    onPointerDown={preventNodeInteractionDrag}
                                                    onMouseDown={preventNodeInteractionDrag}
                                                    onChange={(event) => data.onParameterChange(parameter.name, event.target.value)}
                                                />
                                                <div className="workflow-node-parameter-actions">
                                                    <button
                                                        type="button"
                                                        className="workflow-node-picker-button"
                                                        disabled={isBrowsing}
                                                        onClick={() => void handlePathBrowse(parameter)}
                                                    >
                                                        {isBrowsing ? '...' : 'Browse'}
                                                    </button>
                                                    {String(value ?? '').trim() && (
                                                        <button
                                                            type="button"
                                                            className="workflow-node-picker-clear"
                                                            onClick={() => data.onParameterChange(parameter.name, '')}
                                                        >
                                                            Clear
                                                        </button>
                                                    )}
                                                </div>
                                            </div>
                                        ) : (
                                            <input
                                                className="nodrag nopan"
                                                type={parameter.ui_control === 'number' ? 'number' : parameter.ui_control === 'password' ? 'password' : 'text'}
                                                value={formatParameterValue(parameter, value)}
                                                onPointerDown={preventNodeInteractionDrag}
                                                onMouseDown={preventNodeInteractionDrag}
                                                min={parameter.ui_control === 'number' ? numberConstraints?.min : undefined}
                                                max={parameter.ui_control === 'number' ? numberConstraints?.max : undefined}
                                                step={parameter.ui_control === 'number' ? numberConstraints?.step : undefined}
                                                onChange={(event) => data.onParameterChange(parameter.name, parseValue(parameter, event.target.value))}
                                            />
                                        )}
                                    </div>
                                </label>
                            )
                        })}
                    </div>
                </div>
            )}

            {shouldShowRuntimeOutput && (
                <div className="workflow-node-runtime">
                    {isJsonOutputNode && (
                        <button
                            type="button"
                            className="workflow-node-json-validate workflow-node-json-validate-runtime nodrag nopan"
                            onPointerDown={preventNodeInteractionDrag}
                            onMouseDown={preventNodeInteractionDrag}
                            onClick={() => validateRuntimeJsonOutput()}
                        >
                            Validate
                        </button>
                    )}
                    <pre
                        className={
                            isJsonOutputNode
                                ? `workflow-node-runtime-output workflow-node-runtime-output-json workflow-node-runtime-output-${runtimeJsonValidation}`
                                : 'workflow-node-runtime-output'
                        }
                    >
                        {runtimeOutputText}
                    </pre>
                </div>
            )}

            <div className="workflow-node-footer">
                <span>{NODE_CATEGORY_LABELS[data.manifest.category]}</span>
            </div>
        </div>
    )
}

const nodeTypes = { manifest: ManifestNode }

function WorkflowEditor() {
    const { catalog, loading, error, reload } = useNodeCatalog()
    const [providerModels, setProviderModels] = useState<ProviderModelDefinition[]>([])
    const [statusText, setStatusText] = useState('Ready')
    const [executionErrorModal, setExecutionErrorModal] = useState<WorkflowExecutionErrorModal | null>(null)
    const [isRunning, setIsRunning] = useState(false)
    const [search, setSearch] = useState('')
    const [isLibraryVisible, setIsLibraryVisible] = useState(false)
    const [selectedManifestKey, setSelectedManifestKey] = useState<string | null>(null)
    const [expandedCategories, setExpandedCategories] = useState<CategoryExpansionState>(() => createExpandedCategoriesState())
    const [activeNodeId, setActiveNodeId] = useState<string | null>(null)
    const [nodeContextMenu, setNodeContextMenu] = useState<NodeContextMenuState | null>(null)
    const [nodes, setNodes, onNodesChange] = useNodesState<Node<WorkflowNodeData>>([])
    const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([])
    const [isGridVisible, setIsGridVisible] = useState(true)
    const stopEventsRef = useRef<(() => void) | null>(null)
    const activePlanRef = useRef<CompiledExecutionPlan | null>(null)
    const hasHydratedWorkflowRef = useRef(false)
    const draggedManifestKeyRef = useRef<string | null>(null)
    const copiedNodeRef = useRef<CopiedNodeSnapshot | null>(null)
    const pasteCountRef = useRef(0)
    const canvasPanelRef = useRef<HTMLDivElement | null>(null)
    const { fitView, getZoom, screenToFlowPosition, zoomIn, zoomTo } = useReactFlow<Node<WorkflowNodeData>, Edge>()

    useEffect(() => {
        return () => {
            stopEventsRef.current?.()
        }
    }, [])

    useEffect(() => {
        void fetchProviderModels()
            .then((payload) => setProviderModels(payload.models))
            .catch((loadError) => {
                setStatusText(loadError instanceof Error ? loadError.message : 'Failed to load provider models')
            })
    }, [])

    useEffect(() => {
        setSelectedManifestKey((current) => {
            if (catalog.length === 0) {
                return null
            }
            if (current && catalog.some((manifest) => manifestKey(manifest) === current)) {
                return current
            }
            return manifestKey(catalog[0])
        })
    }, [catalog])

    useEffect(() => {
        setNodes((current) =>
            current.map((node) => ({
                ...node,
                data: {
                    ...node.data,
                    isActive: node.id === activeNodeId,
                    providerModels,
                },
            })),
        )
    }, [activeNodeId, providerModels, setNodes])

    useEffect(() => {
        if (providerModels.length === 0) {
            return
        }

        setNodes((current) =>
            current.map((node) => {
                const modelParameter = node.data.manifest.parameters.find((item) => item.name === 'model_name')
                if (!modelParameter || node.data.manifest.id !== 'MODEL_PROVIDER') {
                    return node
                }
                const options = getDynamicModelOptions(node.data.manifest, node.data.parameters, providerModels)
                const currentValue = String(node.data.parameters.model_name ?? '').trim()
                if (currentValue || options.length === 0) {
                    return {
                        ...node,
                        data: { ...node.data, providerModels },
                    }
                }
                return {
                    ...node,
                    data: {
                        ...node.data,
                        providerModels,
                        parameters: {
                            ...node.data.parameters,
                            model_name: options[0].model,
                        },
                    },
                }
            }),
        )
    }, [providerModels, setNodes])

    useEffect(() => {
        if (!nodeContextMenu) {
            return
        }

        function closeNodeContextMenu(): void {
            setNodeContextMenu(null)
        }

        function handleEscape(event: KeyboardEvent): void {
            if (event.key === 'Escape') {
                closeNodeContextMenu()
            }
        }

        window.addEventListener('pointerdown', closeNodeContextMenu)
        window.addEventListener('keydown', handleEscape)
        return () => {
            window.removeEventListener('pointerdown', closeNodeContextMenu)
            window.removeEventListener('keydown', handleEscape)
        }
    }, [nodeContextMenu])

    useEffect(() => {
        function handleKeyboardShortcuts(event: KeyboardEvent): void {
            if (isEditableEventTarget(event.target)) {
                return
            }

            const normalizedKey = event.key.toLowerCase()
            const withModifier = event.ctrlKey || event.metaKey

            if (withModifier && normalizedKey === 'c') {
                const selectedNodes = nodes.filter((node) => node.selected)
                if (selectedNodes.length === 0) {
                    return
                }

                const source = selectedNodes[selectedNodes.length - 1]
                const dimensions = resolveNodeDimensions(source)
                copiedNodeRef.current = {
                    manifest: source.data.manifest,
                    parameters: cloneNodeParameters(source.data.parameters),
                    position: source.position,
                    width: dimensions.width,
                    height: dimensions.height,
                    collapsed: source.data.collapsed,
                    pinged: source.data.pinged,
                    skipped: source.data.skipped,
                }
                pasteCountRef.current = 0
                setStatusText(`Copied ${source.data.manifest.name}`)
                event.preventDefault()
                return
            }

            if (withModifier && normalizedKey === 'v') {
                const copied = copiedNodeRef.current
                if (!copied) {
                    return
                }

                event.preventDefault()
                pasteCountRef.current += 1
                const offset = 34 + (pasteCountRef.current - 1) * 18
                const nextNode = createWorkflowNode({
                    manifest: copied.manifest,
                    position: {
                        x: copied.position.x + offset,
                        y: copied.position.y + offset,
                    },
                    parameters: cloneNodeParameters(copied.parameters),
                    width: copied.width,
                    height: copied.height,
                    collapsed: copied.collapsed,
                    pinged: copied.pinged,
                    skipped: copied.skipped,
                    selected: true,
                })
                setNodes((current) => [
                    ...current.map((node) => (node.selected ? { ...node, selected: false } : node)),
                    nextNode,
                ])
                setSelectedManifestKey(manifestKey(copied.manifest))
                setStatusText(`Pasted ${copied.manifest.name}`)
                return
            }

            if (event.key !== 'Delete' && event.key !== 'Backspace' && event.key !== 'Del') {
                return
            }

            const selectedNodeIds = nodes.filter((node) => node.selected).map((node) => node.id)
            const selectedEdgeIds = new Set(edges.filter((edge) => edge.selected).map((edge) => edge.id))
            if (selectedNodeIds.length === 0 && selectedEdgeIds.size === 0) {
                return
            }

            event.preventDefault()
            const selectedNodeSet = new Set(selectedNodeIds)
            setNodes((current) => current.filter((node) => !selectedNodeSet.has(node.id)))
            setEdges((current) =>
                current.filter(
                    (edge) =>
                        !selectedEdgeIds.has(edge.id) &&
                        !selectedNodeSet.has(edge.source) &&
                        !selectedNodeSet.has(edge.target),
                ),
            )
            setNodeContextMenu((current) => (current && selectedNodeSet.has(current.nodeId) ? null : current))

            if (selectedNodeIds.length > 0) {
                setStatusText(
                    selectedNodeIds.length === 1
                        ? 'Removed selected node'
                        : `Removed ${selectedNodeIds.length} selected nodes`,
                )
            } else if (selectedEdgeIds.size > 0) {
                setStatusText(selectedEdgeIds.size === 1 ? 'Removed selected link' : `Removed ${selectedEdgeIds.size} selected links`)
            }
        }

        window.addEventListener('keydown', handleKeyboardShortcuts)
        return () => {
            window.removeEventListener('keydown', handleKeyboardShortcuts)
        }
    }, [edges, nodes, setEdges, setNodes])

    useEffect(() => {
        try {
            window.localStorage.setItem(WORKFLOW_TREE_STATE_STORAGE_KEY, JSON.stringify(expandedCategories))
        } catch {
            // Ignore local storage persistence errors.
        }
    }, [expandedCategories])

    useEffect(() => {
        if (hasHydratedWorkflowRef.current || catalog.length === 0) {
            return
        }

        hasHydratedWorkflowRef.current = true
        const persisted = readPersistedWorkflowState()
        if (!persisted) {
            return
        }

        const catalogByKey = new Map(catalog.map((manifest) => [manifestKey(manifest), manifest]))
        const restoredNodes = persisted.nodes.flatMap((snapshot) => {
            const manifest = catalogByKey.get(`${resolveManifestId(snapshot.manifest_id)}:${snapshot.manifest_version}`)
            if (!manifest) {
                return []
            }
            return [
                createWorkflowNode({
                    manifest,
                    nodeId: snapshot.id,
                    position: snapshot.position,
                    parameters: snapshot.parameters,
                    collapsed: snapshot.collapsed,
                    pinged: snapshot.pinged,
                    skipped: snapshot.skipped,
                    width: snapshot.width,
                    height: snapshot.height,
                }),
            ]
        })
        const restoredNodeIds = new Set(restoredNodes.map((node) => node.id))
        const restoredEdges: Edge[] = persisted.edges
            .filter((edge) => restoredNodeIds.has(edge.source) && restoredNodeIds.has(edge.target))
            .flatMap((edge) => {
                if (!edge.source_handle || !edge.target_handle) {
                    return []
                }

                const sourceHandle = parseHandleId(edge.source_handle)
                    ? edge.source_handle
                    : edge.target_handle === 'model'
                        ? toHandleId('controller', edge.source_handle)
                        : toHandleId('output', edge.source_handle)
                const targetHandle = parseHandleId(edge.target_handle)
                    ? edge.target_handle
                    : edge.target_handle === 'model'
                        ? toHandleId('controller', 'model')
                        : toHandleId('input', edge.target_handle)

                return [
                    {
                        id: edge.id,
                        source: edge.source,
                        target: edge.target,
                        sourceHandle,
                        targetHandle,
                        markerEnd: WORKFLOW_EDGE_MARKER,
                        style: WORKFLOW_EDGE_STYLE,
                    },
                ]
            })
        setNodes(restoredNodes)
        setEdges(restoredEdges)
        setIsLibraryVisible(false)
        setIsGridVisible(persisted.is_grid_visible)
        setSearch(persisted.search)
        setSelectedManifestKey(persisted.selected_manifest_key)
        if (restoredNodes.length > 0 || restoredEdges.length > 0) {
            setStatusText('Restored workflow state')
        }
    }, [catalog, providerModels, setEdges, setNodes])

    useEffect(() => {
        if (!hasHydratedWorkflowRef.current) {
            return
        }

        const persistedNodes: PersistedWorkflowNode[] = nodes.map((node) => {
            const dimensions = resolveNodeDimensions(node)
            return {
                id: node.id,
                manifest_id: node.data.manifest.id,
                manifest_version: node.data.manifest.version,
                position: node.position,
                width: dimensions.width,
                height: dimensions.height,
                parameters: normalizeNodePathParameters(node.data.manifest, node.data.parameters),
                collapsed: node.data.collapsed,
                pinged: node.data.pinged,
                skipped: node.data.skipped,
            }
        })
        const persistedEdges: PersistedWorkflowEdge[] = edges.map((edge) => ({
            id: edge.id,
            source: edge.source,
            target: edge.target,
            source_handle: edge.sourceHandle || null,
            target_handle: edge.targetHandle || null,
        }))

        persistWorkflowState({
            nodes: persistedNodes,
            edges: persistedEdges,
            is_library_visible: isLibraryVisible,
            is_grid_visible: isGridVisible,
            search,
            selected_manifest_key: selectedManifestKey,
        })
    }, [edges, isGridVisible, isLibraryVisible, nodes, search, selectedManifestKey])

    const filteredCatalog = useMemo(() => {
        const normalized = search.trim().toLowerCase()
        return catalog.filter((manifest) => !normalized || manifest.name.toLowerCase().includes(normalized))
    }, [catalog, search])

    const groupedCatalog = useMemo<WorkflowCategoryGroup[]>(() => {
        return NODE_CATEGORY_ORDER.map((category) => ({
            category,
            label: NODE_CATEGORY_LABELS[category],
            nodes: filteredCatalog.filter((manifest) => manifest.category === category),
        })).filter((group) => group.nodes.length > 0)
    }, [filteredCatalog])

    const selectedManifest = useMemo(() => {
        if (selectedManifestKey) {
            const currentMatch = catalog.find((manifest) => manifestKey(manifest) === selectedManifestKey)
            if (currentMatch) {
                return currentMatch
            }
        }
        return filteredCatalog[0] ?? catalog[0] ?? null
    }, [catalog, filteredCatalog, selectedManifestKey])

    const effectiveSelectedManifestKey = selectedManifest ? manifestKey(selectedManifest) : null
    const contextMenuNode = useMemo(() => {
        if (!nodeContextMenu) {
            return null
        }
        return nodes.find((node) => node.id === nodeContextMenu.nodeId) ?? null
    }, [nodeContextMenu, nodes])

    function updateNode(nodeId: string, updater: (node: Node<WorkflowNodeData>) => Node<WorkflowNodeData>): void {
        setNodes((current) => current.map((node) => (node.id === nodeId ? updater(node) : node)))
    }

    function removeNode(nodeId: string): void {
        setNodes((current) => current.filter((node) => node.id !== nodeId))
        setEdges((current) => current.filter((edge) => edge.source !== nodeId && edge.target !== nodeId))
        setNodeContextMenu((current) => (current?.nodeId === nodeId ? null : current))
    }

    function handleAggressiveZoomOut(): void {
        const nextZoom = Math.max(getZoom() * 0.72, 0.05)
        void zoomTo(nextZoom, { duration: 110 })
    }

    function createWorkflowNode(input: {
        manifest: NodeManifest
        nodeId?: string
        position?: XYPosition
        parameters?: Record<string, unknown>
        collapsed?: boolean
        pinged?: boolean
        skipped?: boolean
        selected?: boolean
        width?: number
        height?: number
    }): Node<WorkflowNodeData> {
        const nodeId =
            input.nodeId ||
            `${input.manifest.id.toLowerCase()}_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 6)}`
        const resolvedPosition = input.position ?? { x: 80 + nodes.length * 28, y: 80 + nodes.length * 22 }
        const defaultWidth = Math.min(Math.max(input.manifest.ui.default_width, NODE_MIN_WIDTH), NODE_MAX_WIDTH)
        const initialParameters = buildInitialNodeParameters(input.manifest, providerModels, input.parameters)
        const isPinged = input.pinged ?? false

        const style: CSSProperties = {
            width: input.width ?? defaultWidth,
        }
        if (typeof input.height === 'number') {
            style.height = input.height
        }

        return {
            id: nodeId,
            type: 'manifest',
            position: resolvedPosition,
            draggable: !isPinged,
            selected: input.selected,
            data: {
                manifest: input.manifest,
                parameters: initialParameters,
                providerModels,
                collapsed: input.collapsed ?? input.manifest.ui.collapsed_by_default,
                pinged: isPinged,
                skipped: input.skipped ?? false,
                isActive: nodeId === activeNodeId,
                runtimeOutput: null,
                onParameterChange: (parameterName, value) => {
                    updateNode(nodeId, (current) => {
                        const nextParameters = { ...current.data.parameters, [parameterName]: value }
                        if (parameterName === 'provider') {
                            nextParameters.provider = normalizeProvider(value)
                            nextParameters.model_name = ''
                            const nextOptions = getDynamicModelOptions(current.data.manifest, nextParameters, providerModels)
                            if (nextOptions.length > 0) {
                                nextParameters.model_name = nextOptions[0].model
                            }
                        }
                        return {
                            ...current,
                            data: {
                                ...current.data,
                                parameters: nextParameters,
                            },
                        }
                    })
                },
                onStatusChange: (message) => {
                    setStatusText(message)
                },
                onTogglePing: () => {
                    toggleNodePing(nodeId)
                },
                onToggleCollapse: () => {
                    updateNode(nodeId, (current) => ({
                        ...current,
                        data: { ...current.data, collapsed: !current.data.collapsed },
                        style: { ...current.style, width: current.style?.width ?? defaultWidth },
                    }))
                },
            },
            style,
        }
    }

    function addManifestNode(manifest: NodeManifest, position?: XYPosition, options?: { select?: boolean }): void {
        const node = createWorkflowNode({ manifest, position, selected: options?.select })
        if (options?.select) {
            setNodes((current) => [...current.map((item) => (item.selected ? { ...item, selected: false } : item)), node])
            return
        }
        setNodes((current) => [...current, node])
    }

    function toggleNodePing(nodeId: string): void {
        let statusMessage: string | null = null
        setNodes((current) =>
            current.map((node) => {
                if (node.id !== nodeId) {
                    return node
                }
                const nextPinged = !node.data.pinged
                statusMessage = (nextPinged ? 'Pinged' : 'Unpinged') + ' ' + node.data.manifest.name
                return {
                    ...node,
                    draggable: !nextPinged,
                    data: { ...node.data, pinged: nextPinged },
                }
            }),
        )
        if (statusMessage) {
            setStatusText(statusMessage)
        }
    }

    function toggleNodeSkipped(nodeId: string): void {
        const node = nodes.find((item) => item.id === nodeId)
        if (!node) {
            return
        }
        const nextSkipped = !node.data.skipped
        updateNode(nodeId, (current) => ({
            ...current,
            data: { ...current.data, skipped: nextSkipped },
        }))
        setStatusText(`${nextSkipped ? 'Skipped' : 'Unskipped'} ${node.data.manifest.name}`)
    }

    function addSiblingNode(nodeId: string, mode: 'default' | 'clone'): void {
        const sourceNode = nodes.find((item) => item.id === nodeId)
        if (!sourceNode) {
            return
        }

        const dimensions = resolveNodeDimensions(sourceNode)
        const sibling = createWorkflowNode({
            manifest: sourceNode.data.manifest,
            position: {
                x: sourceNode.position.x + 44,
                y: sourceNode.position.y + 34,
            },
            parameters: mode === 'clone' ? sourceNode.data.parameters : undefined,
            collapsed: mode === 'clone' ? sourceNode.data.collapsed : sourceNode.data.manifest.ui.collapsed_by_default,
            pinged: mode === 'clone' ? sourceNode.data.pinged : false,
            skipped: mode === 'clone' ? sourceNode.data.skipped : false,
            width: mode === 'clone' ? dimensions.width : undefined,
            height: mode === 'clone' ? dimensions.height : undefined,
            selected: true,
        })

        setNodes((current) => [...current.map((item) => (item.selected ? { ...item, selected: false } : item)), sibling])
        setSelectedManifestKey(manifestKey(sourceNode.data.manifest))
        if (mode === 'clone') {
            setStatusText(`Cloned ${sourceNode.data.manifest.name}`)
        } else {
            setStatusText(`Added ${sourceNode.data.manifest.name}`)
        }
    }

    function resetNodeConfiguration(nodeId: string): void {
        const node = nodes.find((item) => item.id === nodeId)
        if (!node) {
            return
        }
        updateNode(nodeId, (current) => ({
            ...current,
            data: {
                ...current.data,
                parameters: buildInitialNodeParameters(current.data.manifest, providerModels),
            },
        }))
        setStatusText(`Reset ${node.data.manifest.name} configuration`)
    }

    function applyRunOutputs(outputs: Record<string, Record<string, unknown>>): void {
        setNodes((current) =>
            current.map((node) => ({
                ...node,
                data: {
                    ...node.data,
                    runtimeOutput: outputs[node.id] ?? null,
                },
            })),
        )
    }
    function buildDefinition(): WorkflowDefinition {
        const definitionNodes = nodes.map((node) => ({
            node_id: node.id,
            node_type: node.data.manifest.id,
            node_version: node.data.manifest.version,
            parameters: normalizeNodePathParameters(node.data.manifest, node.data.parameters),
            skipped: node.data.skipped,
        }))
        const definitionConnections = edges.reduce<WorkflowConnection[]>((accumulator, edge) => {
            const source = typeof edge.sourceHandle === 'string' ? parseHandleId(edge.sourceHandle) : null
            const target = typeof edge.targetHandle === 'string' ? parseHandleId(edge.targetHandle) : null
            if (!source || !target) {
                return accumulator
            }
            if (source.kind === 'output' && target.kind === 'input') {
                accumulator.push({
                    from_node: edge.source,
                    connection_type: 'data',
                    from_output: source.name,
                    to_node: edge.target,
                    to_input: target.name,
                })
                return accumulator
            }
            if (source.kind === 'controller' && target.kind === 'controller') {
                accumulator.push({
                    from_node: edge.source,
                    connection_type: 'controller',
                    from_controller: source.name,
                    to_node: edge.target,
                    to_controller: target.name,
                })
            }
            return accumulator
        }, [])
        return {
            schema_version: 2,
            nodes: definitionNodes,
            connections: definitionConnections,
            metadata: {},
        }
    }
    function buildVisualGraph(): VisualGraph {
        return {
            schema_version: 2,
            nodes: nodes.map((node) => {
                const dimensions = resolveNodeDimensions(node)
                return {
                    node_id: node.id,
                    x: node.position.x,
                    y: node.position.y,
                    width: dimensions.width ?? node.data.manifest.ui.default_width,
                    height: dimensions.height ?? NODE_MIN_HEIGHT,
                    collapsed: node.data.collapsed,
                    pinged: node.data.pinged,
                    skipped: node.data.skipped,
                }
            }),
            groups: [],
            comments: [],
        }
    }

    function buildWorkflowBundle(): WorkflowShareBundle {
        const workflowName = 'Shared Workflow'
        const requiredNodesMap = new Map<string, NodeManifest>()
        for (const node of nodes) {
            requiredNodesMap.set(manifestKey(node.data.manifest), node.data.manifest)
        }

        return {
            bundle_version: WORKFLOW_BUNDLE_VERSION,
            app: WORKFLOW_BUNDLE_APP,
            created_at: new Date().toISOString(),
            workflow: {
                name: workflowName,
                definition: buildDefinition(),
                visual_graph: buildVisualGraph(),
            },
            required_nodes: Array.from(requiredNodesMap.values()),
        }
    }

    function hydrateWorkflowFromPayload(payload: ImportedWorkflowPayload, manifests: NodeManifest[]): void {
        const manifestByKey = new Map(manifests.map((manifest) => [manifestKey(manifest), manifest]))
        const visualGraphNodes = Array.isArray(payload.visualGraph.nodes) ? payload.visualGraph.nodes : []
        const visualByNodeId = new Map<string, Record<string, unknown>>()
        for (const visualNode of visualGraphNodes) {
            if (isRecord(visualNode) && typeof visualNode.node_id === 'string') {
                visualByNodeId.set(visualNode.node_id, visualNode)
            }
        }

        const definitionNodes: unknown[] = Array.isArray(payload.definition.nodes) ? payload.definition.nodes : []
        const restoredNodes: Node<WorkflowNodeData>[] = definitionNodes.map((rawNode, index) => {
            if (!isRecord(rawNode) || typeof rawNode.node_id !== 'string' || typeof rawNode.node_type !== 'string') {
                throw new Error('Workflow JSON includes an invalid node entry')
            }

            const nodeVersion = isFiniteNumber(rawNode.node_version) ? rawNode.node_version : 1
            const manifestId = resolveManifestId(rawNode.node_type)
            const manifest = manifestByKey.get(`${manifestId}:${nodeVersion}`)
            if (!manifest) {
                throw new Error(`Missing node manifest: ${manifestId} v${nodeVersion}`)
            }

            const visualNode = visualByNodeId.get(rawNode.node_id)
            const fallbackPosition = { x: 80 + index * 34, y: 80 + index * 26 }
            const position =
                visualNode && isFiniteNumber(visualNode.x) && isFiniteNumber(visualNode.y)
                    ? { x: visualNode.x, y: visualNode.y }
                    : fallbackPosition
            const width = visualNode && isFiniteNumber(visualNode.width) ? visualNode.width : undefined
            const height = visualNode && isFiniteNumber(visualNode.height) ? visualNode.height : undefined
            const collapsed = visualNode ? Boolean(visualNode.collapsed) : manifest.ui.collapsed_by_default
            const pinged = visualNode ? Boolean(visualNode.pinged) : false
            const skipped = typeof rawNode.skipped === 'boolean' ? rawNode.skipped : visualNode ? Boolean(visualNode.skipped) : false
            const parameters = isRecord(rawNode.parameters) ? rawNode.parameters : {}

            return createWorkflowNode({
                manifest,
                nodeId: rawNode.node_id,
                position,
                parameters,
                collapsed,
                pinged,
                skipped,
                width,
                height,
            })
        })

        const restoredNodeIds = new Set(restoredNodes.map((node) => node.id))
        const definitionConnections: unknown[] = Array.isArray(payload.definition.connections) ? payload.definition.connections : []
        const restoredEdges: Edge[] = definitionConnections
            .filter((connection): connection is Record<string, unknown> => isRecord(connection))
            .flatMap((connection) => {
                const connectionType = connection.connection_type === 'controller' ? 'controller' : 'data'

                if (connectionType === 'controller') {
                    if (
                        typeof connection.from_node !== 'string' ||
                        typeof connection.from_controller !== 'string' ||
                        typeof connection.to_node !== 'string' ||
                        typeof connection.to_controller !== 'string'
                    ) {
                        return []
                    }
                    if (!restoredNodeIds.has(connection.from_node) || !restoredNodeIds.has(connection.to_node)) {
                        return []
                    }
                    const sourceHandle = toHandleId('controller', connection.from_controller)
                    const targetHandle = toHandleId('controller', connection.to_controller)
                    return [
                        {
                            id: `${connection.from_node}-${sourceHandle}-${connection.to_node}-${targetHandle}`,
                            source: connection.from_node,
                            target: connection.to_node,
                            sourceHandle,
                            targetHandle,
                            markerEnd: WORKFLOW_EDGE_MARKER,
                            style: WORKFLOW_EDGE_STYLE,
                        },
                    ]
                }

                if (
                    typeof connection.from_node !== 'string' ||
                    typeof connection.from_output !== 'string' ||
                    typeof connection.to_node !== 'string' ||
                    typeof connection.to_input !== 'string'
                ) {
                    return []
                }
                if (!restoredNodeIds.has(connection.from_node) || !restoredNodeIds.has(connection.to_node)) {
                    return []
                }

                const sourceHandle =
                    connection.to_input === 'model'
                        ? toHandleId('controller', connection.from_output)
                        : toHandleId('output', connection.from_output)
                const targetHandle =
                    connection.to_input === 'model'
                        ? toHandleId('controller', 'model')
                        : toHandleId('input', connection.to_input)

                return [
                    {
                        id: `${connection.from_node}-${sourceHandle}-${connection.to_node}-${targetHandle}`,
                        source: connection.from_node,
                        target: connection.to_node,
                        sourceHandle,
                        targetHandle,
                        markerEnd: WORKFLOW_EDGE_MARKER,
                        style: WORKFLOW_EDGE_STYLE,
                    },
                ]
            })
        setNodes(restoredNodes)
        setEdges(restoredEdges)
        setNodeContextMenu(null)
        setActiveNodeId(null)
        if (restoredNodes[0]) {
            setSelectedManifestKey(manifestKey(restoredNodes[0].data.manifest))
        }
    }

    async function exportWorkflowBundle(): Promise<void> {
        try {
            const bundle = buildWorkflowBundle()
            const payload = JSON.stringify(bundle, null, 2)
            const stamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19)
            const fileName = downloadWorkflowJson(payload, `paragraph-workflow-${stamp}.json`)
            setStatusText(
                `Exported workflow JSON as ${fileName} (${bundle.workflow.definition.nodes.length} nodes)`,
            )
        } catch (error) {
            setStatusText(error instanceof Error ? error.message : 'Unable to export workflow JSON')
        }
    }

    async function importWorkflowBundle(): Promise<void> {
        try {
            const selection = await pickWorkflowJsonFromBrowser()
            if (!selection) {
                setStatusText('Workflow import cancelled')
                return
            }

            const parsed: unknown = JSON.parse(selection.jsonPayload)
            const payload = readImportedWorkflowPayload(parsed)

            const existingManifestMap = new Map(catalog.map((manifest) => [manifestKey(manifest), manifest]))
            const importedManifests: NodeManifest[] = []
            for (const manifest of payload.requiredNodes) {
                const key = manifestKey(manifest)
                if (existingManifestMap.has(key)) {
                    continue
                }
                const created = await importNodeManifest(manifest)
                existingManifestMap.set(key, created)
                importedManifests.push(created)
            }

            if (importedManifests.length > 0) {
                await reload()
            }

            const mergedManifestMap = new Map<string, NodeManifest>()
            for (const manifest of catalog) {
                mergedManifestMap.set(manifestKey(manifest), manifest)
            }
            for (const manifest of importedManifests) {
                mergedManifestMap.set(manifestKey(manifest), manifest)
            }

            hydrateWorkflowFromPayload(payload, Array.from(mergedManifestMap.values()))
            const importedLabel =
                importedManifests.length > 0
                    ? ` and installed ${importedManifests.length} custom node${importedManifests.length === 1 ? '' : 's'}`
                    : ''
            const pathLabel = selection.fileName ? ` from ${selection.fileName}` : ''
            setStatusText(`Imported workflow "${payload.name}"${importedLabel}${pathLabel}`)
        } catch (error) {
            setStatusText(error instanceof Error ? error.message : 'Unable to import workflow JSON')
        }
    }

    function isValidConnection(connection: Connection): boolean {
        if (!connection.source || !connection.target || !connection.sourceHandle || !connection.targetHandle) {
            return false
        }
        if (connection.source === connection.target) {
            return false
        }

        const sourceParsed = parseHandleId(connection.sourceHandle)
        const targetParsed = parseHandleId(connection.targetHandle)
        if (!sourceParsed || !targetParsed) {
            return false
        }

        const sourceNode = nodes.find((node) => node.id === connection.source)
        const targetNode = nodes.find((node) => node.id === connection.target)
        if (!sourceNode || !targetNode) {
            return false
        }

        if (sourceParsed.kind === 'output' && targetParsed.kind === 'input') {
            const sourcePort = sourceNode.data.manifest.outputs.find((port) => port.name === sourceParsed.name)
            const targetPort = targetNode.data.manifest.inputs.find((port) => port.name === targetParsed.name)
            if (!sourcePort || !targetPort) {
                return false
            }

            const compatible =
                sourcePort.data_type === targetPort.data_type ||
                sourcePort.data_type === 'ANY' ||
                targetPort.data_type === 'ANY'
            if (!compatible) {
                return false
            }

            const targetAlreadyConnected = edges.some(
                (edge) =>
                    edge.target === connection.target &&
                    edge.targetHandle === connection.targetHandle &&
                    !targetPort.accepts_multiple,
            )
            return !targetAlreadyConnected
        }

        if (sourceParsed.kind === 'controller' && targetParsed.kind === 'controller') {
            const sourceController = getControllers(sourceNode.data.manifest).find((port) => port.name === sourceParsed.name)
            const targetController = getControllers(targetNode.data.manifest).find((port) => port.name === targetParsed.name)
            if (!sourceController || !targetController) {
                return false
            }

            const compatible =
                sourceController.data_type === targetController.data_type ||
                sourceController.data_type === 'ANY' ||
                targetController.data_type === 'ANY'
            if (!compatible) {
                return false
            }

            const targetAlreadyConnected = edges.some(
                (edge) =>
                    edge.target === connection.target &&
                    edge.targetHandle === connection.targetHandle &&
                    !targetController.accepts_multiple,
            )
            return !targetAlreadyConnected
        }

        return false
    }
    function handleTreeDragStart(event: ReactDragEvent<HTMLButtonElement>, manifest: NodeManifest): void {
        const key = manifestKey(manifest)
        draggedManifestKeyRef.current = key
        event.dataTransfer.effectAllowed = 'copy'
        event.dataTransfer.setData(NODE_LIBRARY_MIME, key)
        setSelectedManifestKey(key)
    }

    function handleCanvasDragOver(event: ReactDragEvent<HTMLDivElement>): void {
        event.preventDefault()
        event.dataTransfer.dropEffect = 'copy'
    }

    function handleCanvasDrop(event: ReactDragEvent<HTMLDivElement>): void {
        event.preventDefault()
        const droppedManifestKey = event.dataTransfer.getData(NODE_LIBRARY_MIME) || draggedManifestKeyRef.current
        draggedManifestKeyRef.current = null
        if (!droppedManifestKey) {
            return
        }

        const manifest = catalog.find((item) => manifestKey(item) === droppedManifestKey)
        if (!manifest) {
            setStatusText('Unable to resolve the dragged node')
            return
        }

        addManifestNode(manifest, screenToFlowPosition({ x: event.clientX, y: event.clientY }))
        setSelectedManifestKey(droppedManifestKey)
        setStatusText(`Added ${manifest.name}`)
    }

    async function runWorkflow(): Promise<void> {
        if (isRunning) {
            return
        }
        setExecutionErrorModal(null)
        setIsRunning(true)
        setActiveNodeId(null)
        setNodes((current) =>
            current.map((node) => ({
                ...node,
                data: { ...node.data, runtimeOutput: null },
            })),
        )
        setStatusText('Compiling workflow...')

        let latestRunState: ExecutionRunState | null = null
        try {
            const compileResponse = await compileWorkflow(buildDefinition())
            if (!compileResponse.valid || !compileResponse.plan) {
                throw new Error(compileResponse.diagnostics.map((item) => item.message).join('; ') || 'Compilation failed')
            }

            activePlanRef.current = compileResponse.plan
            const execution = await startExecution(compileResponse.plan)
            setStatusText('Running workflow...')
            stopEventsRef.current?.()
            stopEventsRef.current = subscribeExecutionEvents(execution.run_id, {
                onEvent(event) {
                    if (event.event_type === 'execution.step.started') {
                        const fromPayload = typeof event.payload.node_id === 'string' ? event.payload.node_id : null
                        const fromPlan =
                            event.step_id
                                ? activePlanRef.current?.steps.find((step) => step.step_id === event.step_id)?.node_id ?? null
                                : null
                        setActiveNodeId(fromPayload || fromPlan)
                        setStatusText(`Running ${event.step_id || 'step'}...`)
                    }
                },
                onError(streamError) {
                    setStatusText(streamError)
                },
            })

            const finalState = await pollExecution(execution.run_id, execution.poll_interval, (run) => {
                setActiveNodeId(run.steps.find((step) => step.status === 'running')?.node_id ?? null)
                setStatusText(`Run ${run.status} (${Math.round(run.progress)}%)`)
                if (run.outputs && Object.keys(run.outputs).length > 0) {
                    applyRunOutputs(run.outputs)
                }
            })

            latestRunState = finalState
            setActiveNodeId(null)
            applyRunOutputs(finalState.outputs)
            if (finalState.status === 'completed') {
                setStatusText('Workflow completed')
            } else if (finalState.status === 'failed') {
                throw new Error(finalState.error || 'Workflow failed')
            } else {
                setStatusText(`Workflow ${finalState.status}`)
            }
        } catch (runError) {
            setActiveNodeId(null)
            const message = runError instanceof Error ? runError.message : 'Execution failed'
            setStatusText(message)
            setExecutionErrorModal({
                title: 'Workflow execution failed',
                message: formatWorkflowExecutionError(runError, latestRunState),
            })
        } finally {
            setIsRunning(false)
            activePlanRef.current = null
        }
    }

    return (
        <section className="workflow-shell">
            <div className="workflow-toolbar" role="navigation" aria-label="Workflow actions">
                <div className="workflow-toolbar-status">
                    <span className="workflow-toolbar-status-label">Status</span>
                    <strong title={statusText}>{statusText}</strong>
                </div>
                <div className="workflow-toolbar-actions">
                    <button type="button" onClick={() => void fitView({ padding: 0.2, duration: 180 })}>
                        Fit View
                    </button>
                    <button type="button" onClick={() => setIsGridVisible((visible) => !visible)}>
                        {isGridVisible ? 'Hide Grid' : 'Show Grid'}
                    </button>
                    <button type="button" onClick={() => void exportWorkflowBundle()}>
                        Export JSON
                    </button>
                    <button type="button" onClick={() => void importWorkflowBundle()}>
                        Import JSON
                    </button>
                    <button
                        type="button"
                        onClick={() => {
                            setNodes([])
                            setEdges([])
                            setActiveNodeId(null)
                            setNodeContextMenu(null)
                        }}
                    >
                        Clear Nodes
                    </button>
                    <button type="button" onClick={() => setEdges([])}>
                        Clear Links
                    </button>
                    <button type="button" className="workflow-run" onClick={() => void runWorkflow()} disabled={isRunning}>
                        {isRunning ? 'Running...' : 'Run Workflow'}
                    </button>
                </div>
            </div>

            {executionErrorModal && (
                <div className="workflow-error-modal-backdrop" role="presentation">
                    <div className="workflow-error-modal" role="dialog" aria-modal="true" aria-label="Workflow execution error">
                        <button
                            type="button"
                            className="workflow-error-modal-close"
                            aria-label="Close error dialog"
                            onClick={() => setExecutionErrorModal(null)}
                        >
                            X
                        </button>
                        <h3>{executionErrorModal.title}</h3>
                        <pre>{executionErrorModal.message}</pre>
                    </div>
                </div>
            )}

            {error && <div className="workflow-error">{error}</div>}

            <div className="workflow-layout" data-library-hidden={!isLibraryVisible || undefined}>
                {isLibraryVisible && (
                    <aside className="workflow-library-shell" aria-label="Node tree viewer">
                        <div className="workflow-tree-header">
                            <div>
                                <h2>Node tree</h2>
                                <p className="workflow-tree-caption">Expand categories, then drag nodes onto the canvas.</p>
                            </div>
                            <button
                                type="button"
                                className="workflow-tree-hide-button"
                                aria-label="Hide node tree"
                                onClick={() => setIsLibraryVisible(false)}
                            >
                                Hide
                            </button>
                        </div>

                        <div className="workflow-tree-toolbar">
                            <div className="workflow-tree-search">
                                <input
                                    type="search"
                                    value={search}
                                    placeholder="Search nodes"
                                    onChange={(event) => setSearch(event.target.value)}
                                />
                            </div>
                            <span className="workflow-tree-count">{filteredCatalog.length} visible</span>
                        </div>

                        <div className="workflow-tree-body" role="tree" aria-label="Node catalog tree">
                            {loading && <p className="workflow-tree-empty">Loading node catalog...</p>}
                            {!loading && groupedCatalog.length === 0 && (
                                <p className="workflow-tree-empty">No nodes match the current search.</p>
                            )}
                            {!loading &&
                                groupedCatalog.map((group) => {
                                    const isExpanded = expandedCategories[group.category]
                                    return (
                                        <section key={group.category} className="workflow-tree-group">
                                            <button
                                                type="button"
                                                className="workflow-tree-group-toggle"
                                                aria-expanded={isExpanded}
                                                onClick={() =>
                                                    setExpandedCategories((current) => ({
                                                        ...current,
                                                        [group.category]: !current[group.category],
                                                    }))
                                                }
                                            >
                                                <span className="workflow-tree-group-indicator" aria-hidden="true">
                                                    {isExpanded ? '-' : '+'}
                                                </span>
                                                <span className="workflow-tree-group-name">{group.label}</span>
                                                <span className="workflow-tree-group-count">{group.nodes.length}</span>
                                            </button>
                                            {isExpanded && (
                                                <div className="workflow-tree-children">
                                                    {group.nodes.map((manifest) => {
                                                        const key = manifestKey(manifest)
                                                        return (
                                                            <button
                                                                key={key}
                                                                type="button"
                                                                className="workflow-tree-node"
                                                                draggable
                                                                data-selected={key === effectiveSelectedManifestKey || undefined}
                                                                onClick={() => setSelectedManifestKey(key)}
                                                                onDragStart={(event) => handleTreeDragStart(event, manifest)}
                                                                onDragEnd={() => {
                                                                    draggedManifestKeyRef.current = null
                                                                }}
                                                            >
                                                                <span className="workflow-tree-node-branch" aria-hidden="true" />
                                                                <span className="workflow-tree-node-content">
                                                                    <strong>{manifest.name}</strong>
                                                                    <small>{manifest.inputs.length} in / {manifest.outputs.length} out / {(getControllers(manifest)).length} ctrl</small>
                                                                </span>
                                                            </button>
                                                        )
                                                    })}
                                                </div>
                                            )}
                                        </section>
                                    )
                                })}
                        </div>

                        <div className="workflow-tree-preview">
                            {selectedManifest ? (
                                <div className="workflow-tree-preview-card">
                                    <strong>{selectedManifest.name}</strong>
                                    <p>{buildNodeSummary(selectedManifest)}</p>
                                </div>
                            ) : (
                                <p className="workflow-tree-preview-empty">Select a node to review its summary before adding it to the canvas.</p>
                            )}
                        </div>
                    </aside>
                )}

                <div className="workflow-canvas-panel" ref={canvasPanelRef} onDragOver={handleCanvasDragOver} onDrop={handleCanvasDrop}>
                    {!isLibraryVisible && (
                        <button
                            type="button"
                            className="workflow-canvas-tree-toggle"
                            onClick={() => setIsLibraryVisible(true)}
                        >
                            Show node tree
                        </button>
                    )}
                    <ReactFlow
                        nodes={nodes}
                        edges={edges}
                        nodeTypes={nodeTypes}
                        onNodesChange={onNodesChange}
                        onEdgesChange={onEdgesChange}
                        onConnect={(connection) => {
                            if (!isValidConnection(connection)) {
                                setStatusText('Invalid connection')
                                return
                            }
                            setEdges((current) =>
                                addEdge(
                                    {
                                        ...connection,
                                        id: `${connection.source}-${connection.sourceHandle}-${connection.target}-${connection.targetHandle}`,
                                        markerEnd: WORKFLOW_EDGE_MARKER,
                                        style: WORKFLOW_EDGE_STYLE,
                                    },
                                    current,
                                ),
                            )
                        }}
                        snapToGrid={isGridVisible}
                        snapGrid={[24, 24]}
                        fitView
                        fitViewOptions={{ padding: 0.18 }}
                        minZoom={0.05}
                        maxZoom={1.8}
                        multiSelectionKeyCode={['Control', 'Meta']}
                        deleteKeyCode={null}
                        onPaneClick={() => setNodeContextMenu(null)}
                        onNodeContextMenu={(event, node) => {
                            event.preventDefault()
                            const panelBounds = canvasPanelRef.current?.getBoundingClientRect()
                            const x = panelBounds ? event.clientX - panelBounds.left : event.clientX
                            const y = panelBounds ? event.clientY - panelBounds.top : event.clientY
                            setNodeContextMenu({
                                nodeId: node.id,
                                x: Math.max(10, x),
                                y: Math.max(10, y),
                            })
                        }}
                        onNodesDelete={() => {
                            setNodeContextMenu(null)
                        }}
                        proOptions={{ hideAttribution: true }}
                    >
                        <Controls position="bottom-left" showInteractive={false} showZoom={false}>
                            <ControlButton title="Zoom out" aria-label="Zoom out" onClick={handleAggressiveZoomOut}>
                                -
                            </ControlButton>
                            <ControlButton title="Zoom in" aria-label="Zoom in" onClick={() => void zoomIn({ duration: 110 })}>
                                +
                            </ControlButton>
                        </Controls>
                        {isGridVisible && (
                            <Background variant={BackgroundVariant.Lines} gap={24} size={1} color="rgba(87, 112, 152, 0.42)" />
                        )}
                    </ReactFlow>
                    <a className="workflow-reactflow-credit" href="https://reactflow.dev/" target="_blank" rel="noreferrer">
                        Built with React Flow
                    </a>
                    {nodeContextMenu && contextMenuNode && (
                        <div
                            className="workflow-node-context-menu"
                            style={{ left: `${nodeContextMenu.x}px`, top: `${nodeContextMenu.y}px` }}
                            role="menu"
                            onPointerDown={(event) => event.stopPropagation()}
                        >
                            <button
                                type="button"
                                className="workflow-node-context-menu-item"
                                onClick={() => {
                                    toggleNodePing(contextMenuNode.id)
                                    setNodeContextMenu(null)
                                }}
                            >
                                {contextMenuNode.data.pinged ? 'Unping' : 'Ping'}
                            </button>
                            <button
                                type="button"
                                className="workflow-node-context-menu-item"
                                onClick={() => {
                                    addSiblingNode(contextMenuNode.id, 'default')
                                    setNodeContextMenu(null)
                                }}
                            >
                                Add same node
                            </button>
                            <button
                                type="button"
                                className="workflow-node-context-menu-item"
                                onClick={() => {
                                    addSiblingNode(contextMenuNode.id, 'clone')
                                    setNodeContextMenu(null)
                                }}
                            >
                                Clone
                            </button>
                            <button
                                type="button"
                                className="workflow-node-context-menu-item"
                                onClick={() => {
                                    resetNodeConfiguration(contextMenuNode.id)
                                    setNodeContextMenu(null)
                                }}
                            >
                                Reset config
                            </button>
                            <button
                                type="button"
                                className="workflow-node-context-menu-item"
                                onClick={() => {
                                    toggleNodeSkipped(contextMenuNode.id)
                                    setNodeContextMenu(null)
                                }}
                            >
                                {contextMenuNode.data.skipped ? 'Unskip' : 'Skip'}
                            </button>
                            <div className="workflow-node-context-menu-separator" role="separator" />
                            <button
                                type="button"
                                className="workflow-node-context-menu-item workflow-node-context-menu-item-danger"
                                onClick={() => {
                                    removeNode(contextMenuNode.id)
                                    setStatusText(`Removed ${contextMenuNode.data.manifest.name}`)
                                    setNodeContextMenu(null)
                                }}
                            >
                                Remove node
                            </button>
                        </div>
                    )}
                    {loading && <div className="workflow-loading">Loading node catalog...</div>}
                </div>
            </div>
        </section>
    )
}

export default function WorkflowPage() {
    usePageMetadata({
        title: 'Workflow Builder',
        description:
            'Build, connect, and execute ParaGraph workflows with a visual node canvas and import/export support.',
    })

    return (
        <ReactFlowProvider>
            <WorkflowEditor />
        </ReactFlowProvider>
    )
}

