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
    browseNodeDirectory,
    browseNodeFiles,
    compileWorkflow,
    exportWorkflowJsonWithDialog,
    fetchProviderModels,
    importWorkflowJsonWithDialog,
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
    NodeCategory,
    NodeManifest,
    NodeParameterDefinition,
    ProviderModelDefinition,
    VisualGraph,
    WorkflowConnection,
    WorkflowDefinition,
    WorkflowShareBundle,
} from '../workflow/schema/types'
import './WorkflowPage.css'

type WorkflowNodeData = {
    manifest: NodeManifest
    parameters: Record<string, unknown>
    collapsed: boolean
    isActive: boolean
    providerModels: ProviderModelDefinition[]
    onParameterChange: (parameterName: string, value: unknown) => void
    onStatusChange: (message: string) => void
    onToggleCollapse: () => void
}

type NodeContextMenuState = {
    nodeId: string
    nodeName: string
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

type PersistedWorkflowNode = {
    id: string
    manifest_id: string
    manifest_version: number
    position: XYPosition
    width?: number
    height?: number
    parameters: Record<string, unknown>
    collapsed: boolean
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

function defaultParameters(manifest: NodeManifest): Record<string, unknown> {
    return Object.fromEntries(manifest.parameters.map((parameter) => [parameter.name, parameter.default ?? '']))
}

function normalizeProvider(value: unknown): string {
    const text = String(value ?? '').trim().toLowerCase()
    return text === 'anthropic' ? 'claude' : text
}

function parseValue(parameter: NodeParameterDefinition, rawValue: string | boolean): unknown {
    if (parameter.ui_control === 'toggle') {
        return Boolean(rawValue)
    }
    if (parameter.ui_control === 'number') {
        const text = String(rawValue)
        if (!text.trim()) {
            return parameter.default ?? 0
        }
        const parsed = Number(text)
        return Number.isFinite(parsed) ? parsed : parameter.default ?? 0
    }
    if (parameter.ui_control === 'json') {
        return String(rawValue)
    }
    return rawValue
}

function isStructuredNode(manifest: NodeManifest): boolean {
    return manifest.id === 'LLM_STRUCTURED' || manifest.id.includes('STRUCTURED')
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
        typeof workflow.name === 'string' &&
        isRecord(workflow.definition) &&
        isRecord(workflow.visual_graph)
    )
}

function readImportedWorkflowPayload(value: unknown): ImportedWorkflowPayload {
    if (isWorkflowShareBundlePayload(value)) {
        return {
            name: value.workflow.name,
            definition: value.workflow.definition,
            visualGraph: value.workflow.visual_graph,
            requiredNodes: value.required_nodes.filter(isNodeManifestPayload),
        }
    }

    if (
        isRecord(value) &&
        typeof value.name === 'string' &&
        isRecord(value.definition) &&
        isRecord(value.visual_graph)
    ) {
        return {
            name: value.name,
            definition: value.definition as unknown as WorkflowDefinition,
            visualGraph: value.visual_graph as unknown as VisualGraph,
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
                typeof parsed.is_library_visible === 'boolean' ? parsed.is_library_visible : true,
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
    return String(value ?? '')
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
    return parameter.ui_control === 'textarea' || parameter.ui_control === 'json' || parameter.ui_control === 'file-list'
}

function preventNodeInteractionDrag(event: ReactPointerEvent<HTMLElement> | ReactMouseEvent<HTMLElement>): void {
    event.stopPropagation()
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
        .map((option) => ({ value: option, label: option }))
}

function ManifestNode({ data, selected }: NodeProps<Node<WorkflowNodeData>>) {
    const nodeStyle: NodeAccentStyle = { '--node-accent': data.manifest.ui.accent_color }
    const structured = isStructuredNode(data.manifest)
    const [browseTarget, setBrowseTarget] = useState<string | null>(null)

    async function handlePathBrowse(parameter: NodeParameterDefinition): Promise<void> {
        setBrowseTarget(parameter.name)
        try {
            if (parameter.ui_control === 'directory') {
                const selection = await browseNodeDirectory()
                if (selection.path) {
                    data.onParameterChange(parameter.name, selection.path)
                    data.onStatusChange(`Selected ${selection.path}`)
                } else {
                    data.onStatusChange('Directory selection cancelled')
                }
                return
            }

            const selection = await browseNodeFiles(parameter.ui_control === 'file-list')
            if (selection.paths.length === 0) {
                data.onStatusChange('File selection cancelled')
                return
            }

            if (parameter.ui_control === 'file-list') {
                data.onParameterChange(parameter.name, selection.paths)
                data.onStatusChange(`Selected ${selection.paths.length} file${selection.paths.length === 1 ? '' : 's'}`)
                return
            }

            const [firstPath] = selection.paths
            data.onParameterChange(parameter.name, firstPath ?? '')
            if (firstPath) {
                data.onStatusChange(`Selected ${firstPath}`)
            }
        } catch (error) {
            data.onStatusChange(error instanceof Error ? error.message : 'Unable to browse for a path')
        } finally {
            setBrowseTarget(null)
        }
    }

    return (
        <div
            className="workflow-node"
            style={nodeStyle}
            data-selected={selected || undefined}
            data-active={data.isActive || undefined}
            data-collapsed={data.collapsed || undefined}
            data-structured={structured || undefined}
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
                    {structured && <span className="workflow-node-badge">Structured</span>}
                    <button
                        type="button"
                        className="workflow-node-toggle"
                        aria-label={data.collapsed ? 'Expand node' : 'Collapse node'}
                        title={data.collapsed ? 'Expand node' : 'Collapse node'}
                        onClick={data.onToggleCollapse}
                    >
                        {data.collapsed ? '+' : '-'}
                    </button>
                </div>
            </div>

            <div className="workflow-node-ports">
                <div className="workflow-node-port-column">
                    {data.manifest.inputs.map((port) => (
                        <div key={port.name} className="workflow-node-port workflow-node-port-input">
                            <Handle type="target" position={Position.Left} id={port.name} />
                            <span>{port.name}</span>
                        </div>
                    ))}
                </div>
                <div className="workflow-node-port-column workflow-node-port-column-right">
                    {data.manifest.outputs.map((port) => (
                        <div key={port.name} className="workflow-node-port workflow-node-port-output">
                            <span>{port.name}</span>
                            <Handle type="source" position={Position.Right} id={port.name} />
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
                            const isBrowsing = browseTarget === parameter.name
                            const selectedPaths = parameter.ui_control === 'file-list' ? normalizeStringList(value) : []
                            return (
                                <label
                                    key={parameter.name}
                                    className={
                                        multiline
                                            ? 'workflow-node-parameter-field workflow-node-parameter-field-multiline'
                                            : 'workflow-node-parameter-field'
                                    }
                                >
                                    <div className="workflow-node-parameter-header">
                                        <span className="workflow-node-parameter-label">{parameter.name}</span>
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
                                            <textarea
                                                rows={6}
                                                className="workflow-node-json-input nodrag nopan"
                                                value={formatParameterValue(parameter, value)}
                                                onPointerDown={preventNodeInteractionDrag}
                                                onMouseDown={preventNodeInteractionDrag}
                                                onChange={(event) => data.onParameterChange(parameter.name, parseValue(parameter, event.target.value))}
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
                                        ) : parameter.ui_control === 'file' || parameter.ui_control === 'directory' ? (
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
    const [isRunning, setIsRunning] = useState(false)
    const [search, setSearch] = useState('')
    const [isLibraryVisible, setIsLibraryVisible] = useState(true)
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
                    width: snapshot.width,
                    height: snapshot.height,
                }),
            ]
        })
        const restoredNodeIds = new Set(restoredNodes.map((node) => node.id))
        const restoredEdges: Edge[] = persisted.edges
            .filter((edge) => restoredNodeIds.has(edge.source) && restoredNodeIds.has(edge.target))
            .map((edge) => ({
                id: edge.id,
                source: edge.source,
                target: edge.target,
                sourceHandle: edge.source_handle,
                targetHandle: edge.target_handle,
                markerEnd: WORKFLOW_EDGE_MARKER,
                style: WORKFLOW_EDGE_STYLE,
            }))

        setNodes(restoredNodes)
        setEdges(restoredEdges)
        setIsLibraryVisible(persisted.is_library_visible)
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
            const widthFromStyle = node.style?.width
            const heightFromStyle = node.style?.height
            return {
                id: node.id,
                manifest_id: node.data.manifest.id,
                manifest_version: node.data.manifest.version,
                position: node.position,
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
                parameters: node.data.parameters,
                collapsed: node.data.collapsed,
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
        width?: number
        height?: number
    }): Node<WorkflowNodeData> {
        const nodeId =
            input.nodeId ||
            `${input.manifest.id.toLowerCase()}_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 6)}`
        const resolvedPosition = input.position ?? { x: 80 + nodes.length * 28, y: 80 + nodes.length * 22 }
        const defaultWidth = Math.min(Math.max(input.manifest.ui.default_width, NODE_MIN_WIDTH), NODE_MAX_WIDTH)
        const initialParameters = { ...defaultParameters(input.manifest), ...(input.parameters || {}) }
        const initialModels = getDynamicModelOptions(input.manifest, initialParameters, providerModels)
        if (input.manifest.id === 'MODEL_PROVIDER' && initialModels.length > 0 && !String(initialParameters.model_name ?? '').trim()) {
            initialParameters.model_name = initialModels[0].model
        }

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
            draggable: true,
            data: {
                manifest: input.manifest,
                parameters: initialParameters,
                providerModels,
                collapsed: input.collapsed ?? input.manifest.ui.collapsed_by_default,
                isActive: nodeId === activeNodeId,
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

    function addManifestNode(manifest: NodeManifest, position?: XYPosition): void {
        const node = createWorkflowNode({ manifest, position })
        setNodes((current) => [...current, node])
    }

    function buildDefinition(): WorkflowDefinition {
        const definitionNodes = nodes.map((node) => ({
            node_id: node.id,
            node_type: node.data.manifest.id,
            node_version: node.data.manifest.version,
            parameters: node.data.parameters,
        }))
        const definitionConnections: WorkflowConnection[] = edges.map((edge) => ({
            from_node: edge.source,
            from_output: edge.sourceHandle || '',
            to_node: edge.target,
            to_input: edge.targetHandle || '',
        }))
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
                const widthFromStyle = node.style?.width
                const heightFromStyle = node.style?.height
                return {
                    node_id: node.id,
                    x: node.position.x,
                    y: node.position.y,
                    width:
                        typeof node.width === 'number'
                            ? node.width
                            : typeof widthFromStyle === 'number'
                                ? widthFromStyle
                                : node.data.manifest.ui.default_width,
                    height:
                        typeof node.height === 'number'
                            ? node.height
                            : typeof heightFromStyle === 'number'
                                ? heightFromStyle
                                : NODE_MIN_HEIGHT,
                    collapsed: node.data.collapsed,
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
            const parameters = isRecord(rawNode.parameters) ? rawNode.parameters : {}

            return createWorkflowNode({
                manifest,
                nodeId: rawNode.node_id,
                position,
                parameters,
                collapsed,
                width,
                height,
            })
        })

        const restoredNodeIds = new Set(restoredNodes.map((node) => node.id))
        const definitionConnections: unknown[] = Array.isArray(payload.definition.connections) ? payload.definition.connections : []
        const restoredEdges: Edge[] = definitionConnections
            .filter((connection): connection is Record<string, unknown> => isRecord(connection))
            .flatMap((connection) => {
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
                return [
                    {
                        id: `${connection.from_node}-${connection.from_output}-${connection.to_node}-${connection.to_input}`,
                        source: connection.from_node,
                        target: connection.to_node,
                        sourceHandle: connection.from_output,
                        targetHandle: connection.to_input,
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
            const response = await exportWorkflowJsonWithDialog({
                json_payload: payload,
                suggested_filename: `paragraph-workflow-${stamp}.json`,
            })
            if (!response.path) {
                setStatusText('Workflow export cancelled')
                return
            }
            setStatusText(
                `Exported workflow JSON to ${response.path} (${bundle.workflow.definition.nodes.length} nodes)`,
            )
        } catch (error) {
            setStatusText(error instanceof Error ? error.message : 'Unable to export workflow JSON')
        }
    }

    async function importWorkflowBundle(): Promise<void> {
        try {
            const selection = await importWorkflowJsonWithDialog()
            if (!selection.json_payload) {
                setStatusText('Workflow import cancelled')
                return
            }

            const parsed: unknown = JSON.parse(selection.json_payload)
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
            const pathLabel = selection.path ? ` from ${selection.path}` : ''
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

        const sourceNode = nodes.find((node) => node.id === connection.source)
        const targetNode = nodes.find((node) => node.id === connection.target)
        if (!sourceNode || !targetNode) {
            return false
        }

        const sourcePort = sourceNode.data.manifest.outputs.find((port) => port.name === connection.sourceHandle)
        const targetPort = targetNode.data.manifest.inputs.find((port) => port.name === connection.targetHandle)
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
        setIsRunning(true)
        setActiveNodeId(null)
        setStatusText('Compiling workflow...')

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
            })

            setActiveNodeId(null)
            if (finalState.status === 'completed') {
                setStatusText('Workflow completed')
            } else if (finalState.status === 'failed') {
                throw new Error(finalState.error || 'Workflow failed')
            } else {
                setStatusText(`Workflow ${finalState.status}`)
            }
        } catch (runError) {
            setActiveNodeId(null)
            setStatusText(runError instanceof Error ? runError.message : 'Execution failed')
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
                    <strong>{statusText}</strong>
                </div>
                <div className="workflow-toolbar-actions">                    <button type="button" onClick={() => void fitView({ padding: 0.2, duration: 180 })}>
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
                                                                    <small>{manifest.inputs.length} in / {manifest.outputs.length} out</small>
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
                        deleteKeyCode={['Backspace', 'Delete']}
                        onPaneClick={() => setNodeContextMenu(null)}
                        onNodeContextMenu={(event, node) => {
                            event.preventDefault()
                            const panelBounds = canvasPanelRef.current?.getBoundingClientRect()
                            const x = panelBounds ? event.clientX - panelBounds.left : event.clientX
                            const y = panelBounds ? event.clientY - panelBounds.top : event.clientY
                            setNodeContextMenu({
                                nodeId: node.id,
                                nodeName: node.data.manifest.name,
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
                    {nodeContextMenu && (
                        <div
                            className="workflow-node-context-menu"
                            style={{ left: `${nodeContextMenu.x}px`, top: `${nodeContextMenu.y}px` }}
                            role="menu"
                            onPointerDown={(event) => event.stopPropagation()}
                        >
                            <button
                                type="button"
                                onClick={() => {
                                    removeNode(nodeContextMenu.nodeId)
                                    setStatusText(`Removed ${nodeContextMenu.nodeName}`)
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







