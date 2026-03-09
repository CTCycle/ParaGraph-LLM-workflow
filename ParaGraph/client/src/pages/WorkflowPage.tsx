import { MouseEvent as ReactMouseEvent, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
    addEdge,
    Background,
    BackgroundVariant,
    Connection,
    Edge,
    IsValidConnection,
    MiniMap,
    OnConnect,
    ReactFlow,
    ReactFlowProvider,
    useEdgesState,
    useNodesState,
    useReactFlow,
} from '@xyflow/react'
import { Grid3X3, Minus, Plus } from 'lucide-react'
import '@xyflow/react/dist/style.css'
import WorkflowNodeCard, {
    WorkflowCanvasNode,
    WorkflowNodeData,
} from '../components/workflow/WorkflowNodeCard'
import { usePersistedRecord } from '../hooks/usePersistedRecord'
import { executeWorkflow, fetchWorkflowCatalog, pollWorkflowJob, validateWorkflow } from '../services/workflow'
import {
    AddNodeEventDetail,
    WORKFLOW_ADD_EVENT,
    WORKFLOW_ADDABLE_TYPES,
    WORKFLOW_RUN_EVENT,
    WorkflowGraph,
    WorkflowNode,
    WorkflowNodeDefinition,
} from '../types'
import './WorkflowPage.css'

type CanvasNode = WorkflowCanvasNode
type CanvasEdge = Edge
type PendingNodeRequest = {
    nodeType: string
    x?: number
    y?: number
}

function buildDefaultParams(definition: WorkflowNodeDefinition): Record<string, unknown> {
    return definition.parameters.reduce<Record<string, unknown>>((accumulator, parameter) => {
        accumulator[parameter.key] = parameter.default ?? ''
        return accumulator
    }, {})
}

function finiteOrFallback(value: unknown, fallback: number): number {
    return typeof value === 'number' && Number.isFinite(value) ? value : fallback
}

function WorkflowCanvas() {
    const reactFlowApi = useReactFlow<CanvasNode, CanvasEdge>()
    const canvasRef = useRef<HTMLDivElement | null>(null)
    const [catalog, setCatalog] = useState<WorkflowNodeDefinition[]>([])
    const [catalogError, setCatalogError] = useState<string | null>(null)
    const [statusText, setStatusText] = useState('Ready')
    const [runtimeError, setRuntimeError] = useState<string | null>(null)
    const [isRunning, setIsRunning] = useState(false)
    const [pendingNodeRequests, setPendingNodeRequests] = useState<PendingNodeRequest[]>([])
    const [showGrid, setShowGrid] = useState(true)
    const [contextMenu, setContextMenu] = useState<
        | {
              screenX: number
              screenY: number
              flowX: number
              flowY: number
          }
        | null
    >(null)

    const [storedGraph, setStoredGraph] = usePersistedRecord<WorkflowGraph>('paragraph.workflow.graph', {
        nodes: [],
        edges: [],
    })

    const [nodes, setNodes, onNodesChange] = useNodesState<CanvasNode>([])
    const [edges, setEdges, onEdgesChange] = useEdgesState<CanvasEdge>([])
    const [hydrated, setHydrated] = useState(false)

    const catalogByType = useMemo<Record<string, WorkflowNodeDefinition>>(
        () => Object.fromEntries(catalog.map((definition) => [definition.type, definition])),
        [catalog],
    )

    const applyNodeParamsPatch = useCallback(
        (nodeId: string, patch: Record<string, unknown>) => {
            setNodes((currentNodes) =>
                currentNodes.map((node) => {
                    if (node.id !== nodeId) {
                        return node
                    }
                    return {
                        ...node,
                        data: {
                            ...node.data,
                            params: {
                                ...node.data.params,
                                ...patch,
                            },
                        } as WorkflowNodeData,
                    }
                }),
            )
        },
        [setNodes],
    )

    const removeNode = useCallback(
        (nodeId: string) => {
            setNodes((currentNodes) => currentNodes.filter((node) => node.id !== nodeId))
            setEdges((currentEdges) =>
                currentEdges.filter((edge) => edge.source !== nodeId && edge.target !== nodeId),
            )
        },
        [setEdges, setNodes],
    )

    const createCanvasNode = useCallback(
        (definition: WorkflowNodeDefinition, workflowNode: WorkflowNode): CanvasNode => {
            const nodeParams = {
                ...buildDefaultParams(definition),
                ...workflowNode.params,
            }
            return {
                id: workflowNode.id,
                type: 'workflowNode',
                position: workflowNode.position,
                data: {
                    definition,
                    params: nodeParams,
                    onParamsPatch: applyNodeParamsPatch,
                    onDelete: removeNode,
                },
            }
        },
        [applyNodeParamsPatch, removeNode],
    )

    const focusNodePosition = useCallback(
        (x: number, y: number) => {
            window.requestAnimationFrame(() => {
                reactFlowApi.setCenter(x + 140, y + 90, {
                    duration: 220,
                    zoom: Math.max(reactFlowApi.getZoom(), 0.9),
                })
            })
        },
        [reactFlowApi],
    )

    useEffect(() => {
        let mounted = true
        fetchWorkflowCatalog()
            .then((payload) => {
                if (!mounted) {
                    return
                }
                setCatalog(payload.nodes)
                setCatalogError(null)
            })
            .catch((error: unknown) => {
                if (!mounted) {
                    return
                }
                const message = error instanceof Error ? error.message : 'Failed to load workflow catalog'
                setCatalogError(message)
            })
        return () => {
            mounted = false
        }
    }, [])

    useEffect(() => {
        if (hydrated || catalog.length === 0) {
            return
        }

        const hydratedNodes = storedGraph.nodes
            .map((workflowNode, index) => {
                const definition = catalogByType[workflowNode.type]
                if (!definition) {
                    return null
                }
                return createCanvasNode(definition, {
                    ...workflowNode,
                    position: {
                        x: finiteOrFallback(workflowNode.position?.x, 120 + index * 24),
                        y: finiteOrFallback(workflowNode.position?.y, 120 + index * 16),
                    },
                })
            })
            .filter((node): node is CanvasNode => node !== null)

        const hydratedEdges: CanvasEdge[] = storedGraph.edges.map((edge) => ({
            id: edge.id,
            source: edge.source,
            sourceHandle: edge.sourceHandle,
            target: edge.target,
            targetHandle: edge.targetHandle,
        }))

        setNodes((currentNodes) => {
            if (currentNodes.length === 0) {
                return hydratedNodes
            }

            const mergedById = new Map(hydratedNodes.map((node) => [node.id, node]))
            currentNodes.forEach((node) => {
                mergedById.set(node.id, node)
            })
            return Array.from(mergedById.values())
        })
        setEdges((currentEdges) => {
            if (currentEdges.length === 0) {
                return hydratedEdges
            }

            const mergedById = new Map(hydratedEdges.map((edge) => [edge.id, edge]))
            currentEdges.forEach((edge) => {
                mergedById.set(edge.id, edge)
            })
            return Array.from(mergedById.values())
        })
        setHydrated(true)
    }, [catalog.length, catalogByType, createCanvasNode, hydrated, setEdges, setNodes, storedGraph.edges, storedGraph.nodes])

    useEffect(() => {
        if (!hydrated) {
            return
        }

        const graph: WorkflowGraph = {
            nodes: nodes.map((node) => ({
                id: node.id,
                type: node.data.definition.type,
                position: node.position,
                params: node.data.params,
            })),
            edges: edges.map((edge) => ({
                id: edge.id,
                source: edge.source,
                sourceHandle: edge.sourceHandle || '',
                target: edge.target,
                targetHandle: edge.targetHandle || '',
            })),
        }
        setStoredGraph(graph)
    }, [edges, hydrated, nodes, setStoredGraph])

    const addNode = useCallback(
        (nodeType: string, x?: number, y?: number) => {
            const definition = catalogByType[nodeType]
            if (!definition) {
                setRuntimeError(`Unknown node type: ${nodeType}`)
                return
            }

            const id = `${nodeType.toLowerCase()}_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 7)}`
            const currentNodeCount = reactFlowApi.getNodes().length
            const defaultPosition = {
                x: 120 + currentNodeCount * 24,
                y: 120 + currentNodeCount * 16,
            }

            const workflowNode: WorkflowNode = {
                id,
                type: definition.type,
                position: {
                    x: finiteOrFallback(x, defaultPosition.x),
                    y: finiteOrFallback(y, defaultPosition.y),
                },
                params: buildDefaultParams(definition),
            }

            setNodes((currentNodes) => [...currentNodes, createCanvasNode(definition, workflowNode)])
            setRuntimeError(null)
            setStatusText(`Added ${definition.label} node`)
            focusNodePosition(workflowNode.position.x, workflowNode.position.y)
        },
        [catalogByType, createCanvasNode, focusNodePosition, reactFlowApi, setNodes],
    )

    const queueNodeRequest = useCallback((request: PendingNodeRequest) => {
        setPendingNodeRequests((currentRequests) => [...currentRequests, request])
        setRuntimeError(null)
        setStatusText('Loading node catalog...')
    }, [])

    const requestNodeAdd = useCallback(
        (nodeType: string, x?: number, y?: number) => {
            if (!hydrated || catalog.length === 0) {
                queueNodeRequest({ nodeType, x, y })
                return
            }
            addNode(nodeType, x, y)
        },
        [addNode, catalog.length, hydrated, queueNodeRequest],
    )

    useEffect(() => {
        if (!hydrated || pendingNodeRequests.length === 0) {
            return
        }

        pendingNodeRequests.forEach((request) => {
            addNode(request.nodeType, request.x, request.y)
        })
        setPendingNodeRequests([])
    }, [addNode, hydrated, pendingNodeRequests])

    const isValidConnection: IsValidConnection<CanvasEdge> = useCallback(
        (candidate) => {
            const source = candidate.source
            const target = candidate.target
            const sourceHandle = candidate.sourceHandle ?? null
            const targetHandle = candidate.targetHandle ?? null

            if (!source || !target || !sourceHandle || !targetHandle) {
                return false
            }

            if (source === target) {
                return false
            }

            const sourceNode = nodes.find((node) => node.id === source)
            const targetNode = nodes.find((node) => node.id === target)
            if (!sourceNode || !targetNode) {
                return false
            }

            const sourceDefinition = sourceNode.data.definition
            const targetDefinition = targetNode.data.definition
            const categoryPair = `${sourceDefinition.category}->${targetDefinition.category}`
            const allowedPairs = new Set(['input->process', 'process->process', 'process->output'])
            if (!allowedPairs.has(categoryPair)) {
                return false
            }

            const sourcePort = sourceDefinition.ports.find(
                (port) => port.direction === 'output' && port.handle === sourceHandle,
            )
            const targetPort = targetDefinition.ports.find(
                (port) => port.direction === 'input' && port.handle === targetHandle,
            )

            if (!sourcePort || !targetPort) {
                return false
            }

            const isCompatible =
                sourcePort.data_type === targetPort.data_type ||
                sourcePort.data_type === 'any' ||
                targetPort.data_type === 'any'

            if (!isCompatible) {
                return false
            }

            const duplicateEdge = edges.some(
                (edge) =>
                    edge.source === source &&
                    edge.sourceHandle === sourceHandle &&
                    edge.target === target &&
                    edge.targetHandle === targetHandle,
            )
            return !duplicateEdge
        },
        [edges, nodes],
    )

    const onConnect: OnConnect = useCallback(
        (connection: Connection) => {
            if (!isValidConnection(connection)) {
                return
            }

            setEdges((currentEdges) =>
                addEdge(
                    {
                        ...connection,
                        id: `edge_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 6)}`,
                    },
                    currentEdges,
                ),
            )
        },
        [isValidConnection, setEdges],
    )

    const runWorkflow = useCallback(async () => {
        const graph: WorkflowGraph = {
            nodes: nodes.map((node) => ({
                id: node.id,
                type: node.data.definition.type,
                position: node.position,
                params: node.data.params,
            })),
            edges: edges.map((edge) => ({
                id: edge.id,
                source: edge.source,
                sourceHandle: edge.sourceHandle || '',
                target: edge.target,
                targetHandle: edge.targetHandle || '',
            })),
        }

        setIsRunning(true)
        setRuntimeError(null)
        setStatusText('Validating workflow...')

        try {
            const validation = await validateWorkflow(graph)
            if (!validation.valid) {
                throw new Error(validation.errors.join('; '))
            }

            setStatusText('Starting execution...')
            const execution = await executeWorkflow(graph)
            const finalStatus = await pollWorkflowJob(execution.job_id, execution.poll_interval, (status) => {
                setStatusText(`Running (${Math.round(status.progress)}%)`)
            })

            if (finalStatus.status === 'completed') {
                const outputs = finalStatus.result?.outputs || {}
                setNodes((currentNodes) =>
                    currentNodes.map((node) => {
                        if (node.data.definition.type !== 'Output') {
                            return node
                        }
                        return {
                            ...node,
                            data: {
                                ...node.data,
                                params: {
                                    ...node.data.params,
                                    outputText: outputs[node.id]?.text || '',
                                },
                            },
                        }
                    }),
                )
                setStatusText('Workflow completed')
                return
            }

            if (finalStatus.status === 'failed') {
                throw new Error(finalStatus.error || 'Workflow failed')
            }

            setStatusText(`Workflow ${finalStatus.status}`)
        } catch (error: unknown) {
            const message = error instanceof Error ? error.message : 'Workflow execution failed'
            setRuntimeError(message)
            setStatusText('Execution failed')
        } finally {
            setIsRunning(false)
        }
    }, [edges, nodes, setNodes])

    useEffect(() => {
        const handleEscape = (event: KeyboardEvent) => {
            if (event.key === 'Escape') {
                setContextMenu(null)
            }
        }

        const handleAddNodeEvent = (event: Event) => {
            const customEvent = event as CustomEvent<AddNodeEventDetail>
            const nodeType = customEvent.detail?.nodeType || 'Prompt'
            const canvasBounds = canvasRef.current?.getBoundingClientRect()
            const center = reactFlowApi.screenToFlowPosition({
                x: canvasBounds ? canvasBounds.left + canvasBounds.width / 2 : window.innerWidth / 2,
                y: canvasBounds ? canvasBounds.top + canvasBounds.height / 2 : window.innerHeight / 2,
            })
            requestNodeAdd(nodeType, center.x, center.y)
        }

        const handleRunEvent = () => {
            if (!isRunning) {
                void runWorkflow()
            }
        }

        window.addEventListener('keydown', handleEscape)
        window.addEventListener(WORKFLOW_ADD_EVENT, handleAddNodeEvent as EventListener)
        window.addEventListener(WORKFLOW_RUN_EVENT, handleRunEvent)

        return () => {
            window.removeEventListener('keydown', handleEscape)
            window.removeEventListener(WORKFLOW_ADD_EVENT, handleAddNodeEvent as EventListener)
            window.removeEventListener(WORKFLOW_RUN_EVENT, handleRunEvent)
        }
    }, [isRunning, reactFlowApi, requestNodeAdd, runWorkflow])

    const onPaneContextMenu = useCallback(
        (event: MouseEvent | ReactMouseEvent<Element, MouseEvent>) => {
            if (!('clientX' in event)) {
                return
            }
            event.preventDefault()
            const position = reactFlowApi.screenToFlowPosition({
                x: event.clientX,
                y: event.clientY,
            })
            setContextMenu({
                screenX: event.clientX,
                screenY: event.clientY,
                flowX: position.x,
                flowY: position.y,
            })
        },
        [reactFlowApi],
    )

    const fitWorkflow = useCallback(() => {
        void reactFlowApi.fitView({
            duration: 200,
            padding: 0.2,
        })
    }, [reactFlowApi])

    const zoomIn = useCallback(() => {
        void reactFlowApi.zoomIn({ duration: 180 })
    }, [reactFlowApi])

    const zoomOut = useCallback(() => {
        void reactFlowApi.zoomOut({ duration: 180 })
    }, [reactFlowApi])

    const nodeTypes = useMemo(
        () => ({
            workflowNode: WorkflowNodeCard,
        }),
        [],
    )

    const addableTypes = useMemo(
        () => WORKFLOW_ADDABLE_TYPES.filter((typeName) => Boolean(catalogByType[typeName])),
        [catalogByType],
    )

    return (
        <div className="workflow-page" onClick={() => setContextMenu(null)}>
            <div className="workflow-statusbar">
                <span>{statusText}</span>
                {isRunning ? <span className="workflow-pill">Running</span> : <span className="workflow-pill idle">Idle</span>}
            </div>

            {catalogError && <div className="workflow-alert">Catalog error: {catalogError}</div>}
            {runtimeError && <div className="workflow-alert">{runtimeError}</div>}

            <div className="workflow-canvas" ref={canvasRef}>
                <ReactFlow<CanvasNode, CanvasEdge>
                    nodes={nodes}
                    edges={edges}
                    onNodesChange={onNodesChange}
                    onEdgesChange={onEdgesChange}
                    onConnect={onConnect}
                    onPaneContextMenu={onPaneContextMenu}
                    onPaneClick={() => setContextMenu(null)}
                    isValidConnection={isValidConnection}
                    nodeTypes={nodeTypes}
                    fitView
                    minZoom={0.25}
                    maxZoom={2}
                    defaultEdgeOptions={{ animated: true }}
                    proOptions={{ hideAttribution: true }}
                >
                    <MiniMap pannable zoomable nodeColor="#38bdf8" />
                    {showGrid && <Background variant={BackgroundVariant.Lines} gap={20} size={1} color="#1f2937" />}
                </ReactFlow>

                <div className="workflow-canvas-controls" onClick={(event) => event.stopPropagation()}>
                    <button type="button" className="workflow-icon-button" aria-label="Zoom in" title="Zoom in" onClick={zoomIn}>
                        <Plus size={14} />
                    </button>
                    <button type="button" className="workflow-icon-button" aria-label="Zoom out" title="Zoom out" onClick={zoomOut}>
                        <Minus size={14} />
                    </button>
                    <button
                        type="button"
                        className={`workflow-icon-button${showGrid ? ' active' : ''}`}
                        aria-label={showGrid ? 'Disable grid' : 'Enable grid'}
                        title={showGrid ? 'Disable grid' : 'Enable grid'}
                        onClick={() => setShowGrid((current) => !current)}
                    >
                        <Grid3X3 size={14} />
                    </button>
                </div>

                {nodes.length === 0 && (
                    <div className="workflow-empty-state">
                        <h2>Start with typed nodes</h2>
                        <p>
                            Add a Prompt, connect it to LLM, then finish with Output. You can use the top-right controls
                            or right-click anywhere on the canvas.
                        </p>
                    </div>
                )}

                {contextMenu && (
                    <div
                        className="workflow-context-menu"
                        style={{ left: contextMenu.screenX, top: contextMenu.screenY }}
                        onClick={(event) => event.stopPropagation()}
                    >
                        <div className="workflow-context-title">Canvas actions</div>
                        {addableTypes.map((typeName) => (
                            <button
                                key={typeName}
                                type="button"
                                onClick={() => {
                                    requestNodeAdd(typeName, contextMenu.flowX, contextMenu.flowY)
                                    setContextMenu(null)
                                }}
                            >
                                Add {typeName}
                            </button>
                        ))}
                        <button
                            type="button"
                            className="workflow-context-secondary"
                            onClick={() => {
                                fitWorkflow()
                                setContextMenu(null)
                            }}
                        >
                            Fit workflow
                        </button>
                    </div>
                )}
            </div>
        </div>
    )
}

export default function WorkflowPage() {
    return (
        <ReactFlowProvider>
            <WorkflowCanvas />
        </ReactFlowProvider>
    )
}
