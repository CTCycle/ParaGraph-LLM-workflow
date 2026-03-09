import { MouseEvent as ReactMouseEvent, useCallback, useEffect, useMemo, useState } from 'react'
import {
    addEdge,
    Background,
    Connection,
    Controls,
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
import '@xyflow/react/dist/style.css'
import WorkflowNodeCard, {
    WorkflowCanvasNode,
    WorkflowNodeData,
} from '../components/workflow/WorkflowNodeCard'
import { usePersistedRecord } from '../hooks/usePersistedRecord'
import {
    AddNodeEventDetail,
    WORKFLOW_ADD_EVENT,
    WORKFLOW_ADDABLE_TYPES,
    WORKFLOW_RUN_EVENT,
    WorkflowGraph,
    WorkflowNode,
    WorkflowNodeDefinition,
} from '../types'
import { executeWorkflow, fetchWorkflowCatalog, pollWorkflowJob, validateWorkflow } from '../services/workflow'
import './WorkflowPage.css'

type CanvasNode = WorkflowCanvasNode
type CanvasEdge = Edge

function buildDefaultParams(definition: WorkflowNodeDefinition): Record<string, unknown> {
    return definition.parameters.reduce<Record<string, unknown>>((accumulator, parameter) => {
        accumulator[parameter.key] = parameter.default ?? ''
        return accumulator
    }, {})
}

function WorkflowCanvas() {
    const reactFlowApi = useReactFlow<CanvasNode, CanvasEdge>()
    const [catalog, setCatalog] = useState<WorkflowNodeDefinition[]>([])
    const [catalogError, setCatalogError] = useState<string | null>(null)
    const [statusText, setStatusText] = useState('Ready')
    const [runtimeError, setRuntimeError] = useState<string | null>(null)
    const [isRunning, setIsRunning] = useState(false)
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
            .map((workflowNode) => {
                const definition = catalogByType[workflowNode.type]
                if (!definition) {
                    return null
                }
                return createCanvasNode(definition, workflowNode)
            })
            .filter((node): node is CanvasNode => node !== null)

        const hydratedEdges: CanvasEdge[] = storedGraph.edges.map((edge) => ({
            id: edge.id,
            source: edge.source,
            sourceHandle: edge.sourceHandle,
            target: edge.target,
            targetHandle: edge.targetHandle,
        }))

        setNodes(hydratedNodes)
        setEdges(hydratedEdges)
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
            const defaultPosition = {
                x: 120 + nodes.length * 24,
                y: 120 + nodes.length * 16,
            }

            const workflowNode: WorkflowNode = {
                id,
                type: definition.type,
                position: {
                    x: x ?? defaultPosition.x,
                    y: y ?? defaultPosition.y,
                },
                params: buildDefaultParams(definition),
            }

            setNodes((currentNodes) => [...currentNodes, createCanvasNode(definition, workflowNode)])
            setRuntimeError(null)
        },
        [catalogByType, createCanvasNode, nodes.length, setNodes],
    )

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
        const handleAddNodeEvent = (event: Event) => {
            const customEvent = event as CustomEvent<AddNodeEventDetail>
            const nodeType = customEvent.detail?.nodeType || 'Prompt'
            const center = reactFlowApi.screenToFlowPosition({
                x: window.innerWidth / 2,
                y: window.innerHeight / 2,
            })
            addNode(nodeType, center.x, center.y)
        }

        const handleRunEvent = () => {
            if (!isRunning) {
                void runWorkflow()
            }
        }

        window.addEventListener(WORKFLOW_ADD_EVENT, handleAddNodeEvent as EventListener)
        window.addEventListener(WORKFLOW_RUN_EVENT, handleRunEvent)

        return () => {
            window.removeEventListener(WORKFLOW_ADD_EVENT, handleAddNodeEvent as EventListener)
            window.removeEventListener(WORKFLOW_RUN_EVENT, handleRunEvent)
        }
    }, [addNode, isRunning, reactFlowApi, runWorkflow])

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

            <div className="workflow-canvas">
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
                    <Controls />
                    <Background gap={18} color="#1f2937" />
                </ReactFlow>

                {contextMenu && (
                    <div
                        className="workflow-context-menu"
                        style={{ left: contextMenu.screenX, top: contextMenu.screenY }}
                        onClick={(event) => event.stopPropagation()}
                    >
                        <div className="workflow-context-title">Add node</div>
                        {addableTypes.map((typeName) => (
                            <button
                                key={typeName}
                                type="button"
                                onClick={() => {
                                    addNode(typeName, contextMenu.flowX, contextMenu.flowY)
                                    setContextMenu(null)
                                }}
                            >
                                {typeName}
                            </button>
                        ))}
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

