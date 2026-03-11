import {
    type CSSProperties,
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
    useEdgesState,
    useNodesState,
    useReactFlow,
} from '@xyflow/react'

import {
    compileWorkflow,
    fetchProviderModels,
    pollExecution,
    startExecution,
    subscribeExecutionEvents,
} from '../app/services/workflowApi'
import {
    ExecutionRunState,
    NodeManifest,
    NodeParameterDefinition,
    ProviderModelDefinition,
    WorkflowConnection,
    WorkflowDefinition,
} from '../workflow/schema/types'
import { useNodeCatalog } from '../workflow/hooks/useNodeCatalog'
import { NODE_CATEGORY_LABELS, NodeCategoryFilter, toNodeCategoryFilter } from '../workflow/schema/nodeCategory'
import './WorkflowPage.css'

type WorkflowNodeData = {
    manifest: NodeManifest
    parameters: Record<string, unknown>
    collapsed: boolean
    runtimeOutput: Record<string, unknown> | null
    providerModels: ProviderModelDefinition[]
    onParameterChange: (parameterName: string, value: unknown) => void
    onToggleCollapse: () => void
}

type NodeContextMenuState = {
    nodeId: string
    nodeName: string
    x: number
    y: number
}

const NODE_MIN_WIDTH = 240
const NODE_MAX_WIDTH = 680
const NODE_MIN_HEIGHT = 140
const NODE_MAX_HEIGHT = 760

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

type NodeAccentStyle = CSSProperties & { '--node-accent': string }

function isStructuredNode(manifest: NodeManifest): boolean {
    return manifest.id.includes('STRUCTURED_RESPONSE')
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

function getDynamicModelOptions(
    manifest: NodeManifest,
    parameters: Record<string, unknown>,
    providerModels: ProviderModelDefinition[],
): ProviderModelDefinition[] {
    if (manifest.id.startsWith('OLLAMA_')) {
        return providerModels.filter((item) => item.provider === 'ollama')
    }
    if (manifest.id.startsWith('HUGGINGFACE_')) {
        return providerModels.filter((item) => item.provider === 'huggingface')
    }
    if (manifest.id.startsWith('CLOUD_')) {
        const provider = normalizeProvider(parameters.provider ?? 'openai') || 'openai'
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

function buildRuntimeOutputs(run: ExecutionRunState): Record<string, Record<string, unknown>> {
    return run.steps.reduce<Record<string, Record<string, unknown>>>((accumulator, step) => {
        const outputPorts = step.output?.ports
        if (outputPorts && typeof outputPorts === 'object') {
            accumulator[step.node_id] = outputPorts as Record<string, unknown>
        }
        return accumulator
    }, {})
}

function renderRuntimeOutput(runtimeOutput: Record<string, unknown> | null): string {
    if (!runtimeOutput) {
        return ''
    }
    if (typeof runtimeOutput.response === 'string') {
        return runtimeOutput.response
    }
    if ('result' in runtimeOutput) {
        try {
            return JSON.stringify(runtimeOutput.result, null, 2)
        } catch {
            return String(runtimeOutput.result)
        }
    }
    if (typeof runtimeOutput.text === 'string') {
        return runtimeOutput.text
    }
    return JSON.stringify(runtimeOutput, null, 2)
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

function preventNodeInteractionDrag(event: ReactPointerEvent<HTMLElement> | ReactMouseEvent<HTMLElement>): void {
    event.stopPropagation()
}

function ManifestNode({ data, selected }: NodeProps<Node<WorkflowNodeData>>) {
    const nodeStyle: NodeAccentStyle = { '--node-accent': data.manifest.ui.accent_color }
    const structured = isStructuredNode(data.manifest)

    return (
        <div
            className="workflow-node"
            style={nodeStyle}
            data-selected={selected || undefined}
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
                    <span>{data.manifest.id}</span>
                    <p className="workflow-node-subtitle">{buildNodeSummary(data.manifest)}</p>
                </div>
                <div className="workflow-node-header-actions">
                    {structured && <span className="workflow-node-badge">Structured</span>}
                    <button
                        type="button"
                        className="workflow-node-toggle"
                        aria-label={data.collapsed ? 'Expand node' : 'Collapse node'}
                        title={data.collapsed ? 'Expand node' : 'Collapse node'}
                        onClick={data.onToggleCollapse}
                    >
                        {data.collapsed ? '▸' : '▾'}
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
                            return (
                                <label
                                    key={parameter.name}
                                    className={parameter.ui_control === 'textarea' || parameter.ui_control === 'json' ? 'workflow-node-parameter-field workflow-node-parameter-field-multiline' : 'workflow-node-parameter-field'}
                                >
                                    <span className="workflow-node-parameter-label">{parameter.name}</span>
                                    <div className="workflow-node-parameter-value">
                                        {parameter.ui_control === 'textarea' ? (
                                            <textarea
                                                rows={2}
                                                className="workflow-node-parameter-textbox nodrag nopan"
                                                value={formatParameterValue(parameter, value)}
                                                onPointerDown={preventNodeInteractionDrag}
                                                onMouseDown={preventNodeInteractionDrag}
                                                onChange={(event) =>
                                                    data.onParameterChange(parameter.name, parseValue(parameter, event.target.value))
                                                }
                                            />
                                        ) : parameter.ui_control === 'json' ? (
                                            <textarea
                                                rows={6}
                                                className="workflow-node-json-input nodrag nopan"
                                                value={formatParameterValue(parameter, value)}
                                                onPointerDown={preventNodeInteractionDrag}
                                                onMouseDown={preventNodeInteractionDrag}
                                                onChange={(event) =>
                                                    data.onParameterChange(parameter.name, parseValue(parameter, event.target.value))
                                                }
                                            />
                                        ) : parameter.ui_control === 'toggle' ? (
                                            <input
                                                className="workflow-node-toggle-input"
                                                type="checkbox"
                                                checked={Boolean(value)}
                                                onChange={(event) =>
                                                    data.onParameterChange(parameter.name, parseValue(parameter, event.target.checked))
                                                }
                                            />
                                        ) : parameter.ui_control === 'select' && options.length > 0 ? (
                                            <select
                                                value={String(value ?? '')}
                                                onChange={(event) =>
                                                    data.onParameterChange(parameter.name, parseValue(parameter, event.target.value))
                                                }
                                            >
                                                {!String(value ?? '') && <option value="">Select...</option>}
                                                {options.map((option) => (
                                                    <option key={option.value} value={option.value}>
                                                        {option.label}
                                                    </option>
                                                ))}
                                            </select>
                                        ) : (
                                            <input
                                                className="nodrag nopan"
                                                type={parameter.ui_control === 'number' ? 'number' : 'text'}
                                                value={formatParameterValue(parameter, value)}
                                                onPointerDown={preventNodeInteractionDrag}
                                                onMouseDown={preventNodeInteractionDrag}
                                                onChange={(event) =>
                                                    data.onParameterChange(parameter.name, parseValue(parameter, event.target.value))
                                                }
                                            />
                                        )}
                                    </div>
                                </label>
                            )
                        })}
                    </div>
                </div>
            )}

            {data.runtimeOutput && !data.collapsed && (
                <div className="workflow-node-runtime">
                    <span className="workflow-node-runtime-label">{structured ? 'Structured Output' : 'Runtime Output'}</span>
                    <textarea
                        className="workflow-node-runtime-output nodrag nopan"
                        readOnly
                        rows={structured ? 6 : 4}
                        value={renderRuntimeOutput(data.runtimeOutput)}
                        onPointerDown={preventNodeInteractionDrag}
                        onMouseDown={preventNodeInteractionDrag}
                    />
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
    const { catalog, loading, error } = useNodeCatalog()
    const [providerModels, setProviderModels] = useState<ProviderModelDefinition[]>([])
    const [statusText, setStatusText] = useState('Ready')
    const [isRunning, setIsRunning] = useState(false)
    const [search, setSearch] = useState('')
    const [category, setCategory] = useState<NodeCategoryFilter>('all')
    const [runtimeOutputs, setRuntimeOutputs] = useState<Record<string, Record<string, unknown>>>({})
    const [nodeContextMenu, setNodeContextMenu] = useState<NodeContextMenuState | null>(null)
    const [nodes, setNodes, onNodesChange] = useNodesState<Node<WorkflowNodeData>>([])
    const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([])
    const [isGridVisible, setIsGridVisible] = useState(true)
    const stopEventsRef = useRef<(() => void) | null>(null)
    const canvasPanelRef = useRef<HTMLDivElement | null>(null)
    const { fitView, zoomIn, zoomTo, getZoom } = useReactFlow<Node<WorkflowNodeData>, Edge>()

    useEffect(() => {
        return () => {
            stopEventsRef.current?.()
        }
    }, [])

    useEffect(() => {
        void fetchProviderModels()
            .then((payload) => {
                setProviderModels(payload.models)
            })
            .catch((loadError) => {
                setStatusText(loadError instanceof Error ? loadError.message : 'Failed to load provider models')
            })
    }, [])

    useEffect(() => {
        setNodes((current) =>
            current.map((node) => ({
                ...node,
                data: {
                    ...node.data,
                    runtimeOutput: runtimeOutputs[node.id] ?? null,
                    providerModels,
                },
            })),
        )
    }, [providerModels, runtimeOutputs, setNodes])

    useEffect(() => {
        if (providerModels.length === 0) {
            return
        }

        setNodes((current) =>
            current.map((node) => {
                const modelParameter = node.data.manifest.parameters.find((item) => item.name === 'model_name')
                if (!modelParameter) {
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

    const filteredCatalog = useMemo(() => {
        const normalized = search.trim().toLowerCase()
        return catalog.filter((manifest) => {
            if (category !== 'all' && manifest.category !== category) {
                return false
            }
            if (!normalized) {
                return true
            }
            return `${manifest.name} ${manifest.id}`.toLowerCase().includes(normalized)
        })
    }, [catalog, category, search])

    function updateNode(nodeId: string, updater: (node: Node<WorkflowNodeData>) => Node<WorkflowNodeData>): void {
        setNodes((current) => current.map((node) => (node.id === nodeId ? updater(node) : node)))
    }

    function removeNode(nodeId: string): void {
        setNodes((current) => current.filter((node) => node.id !== nodeId))
        setEdges((current) => current.filter((edge) => edge.source !== nodeId && edge.target !== nodeId))
        setRuntimeOutputs((current) => {
            const next = { ...current }
            delete next[nodeId]
            return next
        })
        setNodeContextMenu((current) => (current?.nodeId === nodeId ? null : current))
    }

    function handleAggressiveZoomOut(): void {
        const nextZoom = Math.max(getZoom() * 0.72, 0.05)
        void zoomTo(nextZoom, { duration: 110 })
    }

    function addManifestNode(manifest: NodeManifest): void {
        const nodeId = `${manifest.id.toLowerCase()}_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 6)}`
        const position = { x: 80 + nodes.length * 28, y: 80 + nodes.length * 22 }
        const collapsed = manifest.ui.collapsed_by_default
        const defaultWidth = Math.min(Math.max(manifest.ui.default_width, NODE_MIN_WIDTH), NODE_MAX_WIDTH)
        const initialParameters = defaultParameters(manifest)
        const initialModels = getDynamicModelOptions(manifest, initialParameters, providerModels)
        if (initialModels.length > 0 && !String(initialParameters.model_name ?? '').trim()) {
            initialParameters.model_name = initialModels[0].model
        }
        const node: Node<WorkflowNodeData> = {
            id: nodeId,
            type: 'manifest',
            position,
            draggable: true,
            data: {
                manifest,
                parameters: initialParameters,
                providerModels,
                collapsed,
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
                onToggleCollapse: () => {
                    updateNode(nodeId, (current) => ({
                        ...current,
                        data: { ...current.data, collapsed: !current.data.collapsed },
                        style: {
                            ...current.style,
                            width: current.style?.width ?? defaultWidth,
                        },
                    }))
                },
            },
            style: {
                width: defaultWidth,
            },
        }
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

    async function runWorkflow(): Promise<void> {
        if (isRunning) {
            return
        }
        setIsRunning(true)
        setRuntimeOutputs({})
        setStatusText('Compiling workflow...')

        try {
            const compileResponse = await compileWorkflow(buildDefinition())
            if (!compileResponse.valid || !compileResponse.plan) {
                throw new Error(compileResponse.diagnostics.map((item) => item.message).join('; ') || 'Compilation failed')
            }

            const execution = await startExecution(compileResponse.plan)
            setStatusText('Running workflow...')
            stopEventsRef.current?.()
            stopEventsRef.current = subscribeExecutionEvents(execution.run_id, {
                onEvent(event) {
                    if (event.event_type === 'execution.step.started') {
                        setStatusText(`Running ${event.step_id || 'step'}...`)
                    }
                },
                onError(streamError) {
                    setStatusText(streamError)
                },
            })

            const finalState = await pollExecution(execution.run_id, execution.poll_interval, (run) => {
                setStatusText(`Run ${run.status} (${Math.round(run.progress)}%)`)
            })

            setRuntimeOutputs(buildRuntimeOutputs(finalState))
            if (finalState.status === 'completed') {
                setStatusText('Workflow completed')
            } else if (finalState.status === 'failed') {
                throw new Error(finalState.error || 'Workflow failed')
            } else {
                setStatusText(`Workflow ${finalState.status}`)
            }
        } catch (runError) {
            setStatusText(runError instanceof Error ? runError.message : 'Execution failed')
        } finally {
            setIsRunning(false)
        }
    }

    return (
        <section className="workflow-shell">
            <div className="workflow-toolbar" role="navigation" aria-label="Workflow actions">
                <div className="workflow-toolbar-status">
                    <span className="workflow-toolbar-status-label">Status</span>
                    <strong>{statusText}</strong>
                </div>
                <div className="workflow-toolbar-actions">
                    <button type="button" onClick={() => void fitView({ padding: 0.2, duration: 180 })}>
                        Fit View
                    </button>
                    <button type="button" onClick={() => setIsGridVisible((visible) => !visible)}>
                        {isGridVisible ? 'Hide Grid' : 'Show Grid'}
                    </button>
                    <button
                        type="button"
                        onClick={() => {
                            setNodes([])
                            setEdges([])
                            setRuntimeOutputs({})
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

            <div className="workflow-layout">
                <div className="workflow-canvas-panel" ref={canvasPanelRef}>
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
                                        markerEnd: { type: MarkerType.ArrowClosed, width: 18, height: 18 },
                                        style: { stroke: '#5ba7ff', strokeWidth: 2.2 },
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
                        onNodesDelete={(deletedNodes) => {
                            setRuntimeOutputs((current) => {
                                if (deletedNodes.length === 0) {
                                    return current
                                }
                                const next = { ...current }
                                deletedNodes.forEach((node) => {
                                    delete next[node.id]
                                })
                                return next
                            })
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
                            <Background
                                variant={BackgroundVariant.Lines}
                                gap={24}
                                size={1}
                                color="rgba(87, 112, 152, 0.42)"
                            />
                        )}
                    </ReactFlow>
                    <a
                        className="workflow-reactflow-credit"
                        href="https://reactflow.dev/"
                        target="_blank"
                        rel="noreferrer"
                    >
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

                <aside className="workflow-sidepanel">
                    <section className="workflow-panel workflow-node-library">
                        <div className="workflow-panel-header">
                            <h2>Node Library</h2>
                            <p>{filteredCatalog.length} visible</p>
                        </div>
                        <div className="workflow-node-library-controls">
                            <input
                                type="search"
                                value={search}
                                placeholder="Search by name"
                                onChange={(event) => setSearch(event.target.value)}
                            />
                            <select
                                aria-label="Filter node category"
                                value={category}
                                onChange={(event) => setCategory(toNodeCategoryFilter(event.target.value))}
                            >
                                <option value="all">All categories</option>
                                {Object.entries(NODE_CATEGORY_LABELS).map(([value, label]) => (
                                    <option key={value} value={value}>
                                        {label}
                                    </option>
                                ))}
                            </select>
                        </div>
                        <div className="workflow-node-list">
                            {filteredCatalog.map((manifest) => (
                                <button key={manifest.id} type="button" onClick={() => addManifestNode(manifest)}>
                                    <strong>{manifest.name}</strong>
                                    <span>{manifest.description}</span>
                                </button>
                            ))}
                            {!loading && filteredCatalog.length === 0 && (
                                <p className="workflow-node-empty">No nodes match the current filter.</p>
                            )}
                        </div>
                    </section>
                </aside>
            </div>
        </section>
    )
}

export default function WorkflowPage() {
    return (
        <ReactFlowProvider>
            <WorkflowEditor />
        </ReactFlowProvider>
    )
}

