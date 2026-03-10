import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import GraphCanvas from '../graph/canvas/GraphCanvas'
import { nodeCatalogActions, useNodeCatalogStore } from '../app/stores/nodeCatalogStore'
import { providerCatalogActions } from '../app/stores/providerCatalogStore'
import { runtimeActions, useRuntimeStore } from '../app/stores/runtimeStore'
import { getUiState, uiActions, useUiStore } from '../app/stores/uiStore'
import { workflowActions, useWorkflowStore } from '../app/stores/workflowStore'
import {
    executeWorkflow,
    pollWorkflowJob,
    subscribeExecutionEvents,
    validateWorkflow,
} from '../app/services/workflowApi'
import { AddNodeEventDetail, WORKFLOW_ADD_EVENT, WORKFLOW_RUN_EVENT } from '../types'
import { ConfigFieldSchema, NodeCategory, NodeDefinition } from '../workflow/schema/types'
import './WorkflowPage.css'

type NodeLibraryCategoryFilter = 'all' | NodeCategory
type NodeLibraryPortFilter = 'all' | 'has-input' | 'has-output'

const NODE_CATEGORY_LABELS: Record<NodeCategory, string> = {
    input: 'Inputs',
    process: 'Process',
    output: 'Output',
}

function parseNumber(value: string): number | null {
    if (!value.trim()) {
        return null
    }
    const parsed = Number.parseFloat(value)
    return Number.isFinite(parsed) ? parsed : null
}

function toDisplay(value: unknown): string {
    if (typeof value === 'string') {
        return value
    }
    if (typeof value === 'number' || typeof value === 'boolean') {
        return String(value)
    }
    if (value == null) {
        return ''
    }
    return JSON.stringify(value)
}
function getCanvasViewportCenter(): { x: number; y: number } {
    const canvasRoot = document.querySelector<HTMLElement>('.graph-canvas-root')
    if (!canvasRoot) {
        return { x: 320, y: 220 }
    }
    return {
        x: Math.max(1, canvasRoot.clientWidth) / 2,
        y: Math.max(1, canvasRoot.clientHeight) / 2,
    }
}

function renderField(
    schema: ConfigFieldSchema,
    value: unknown,
    onChange: (next: unknown) => void,
): JSX.Element {
    const display = toDisplay(value)

    if (schema.field_type === 'select') {
        return (
            <select value={display} onChange={(event) => onChange(event.target.value)}>
                {schema.options.map((option) => (
                    <option key={option} value={option}>
                        {option}
                    </option>
                ))}
            </select>
        )
    }

    if (schema.field_type === 'textarea') {
        return <textarea value={display} rows={4} onChange={(event) => onChange(event.target.value)} />
    }

    if (schema.field_type === 'number') {
        return (
            <input
                type="number"
                step="any"
                value={display}
                onChange={(event) => onChange(parseNumber(event.target.value))}
            />
        )
    }

    return <input type="text" value={display} onChange={(event) => onChange(event.target.value)} />
}

export default function WorkflowPage() {
    const [statusText, setStatusText] = useState('Ready')
    const [isRunning, setIsRunning] = useState(false)
    const [nodeSearchQuery, setNodeSearchQuery] = useState('')
    const [nodeCategoryFilter, setNodeCategoryFilter] = useState<NodeLibraryCategoryFilter>('all')
    const [nodePortFilter, setNodePortFilter] = useState<NodeLibraryPortFilter>('all')

    const nodes = useNodeCatalogStore((state) => state.nodes)
    const nodeCatalogLoading = useNodeCatalogStore((state) => state.loading)
    const nodeCatalogError = useNodeCatalogStore((state) => state.error)

    const workflowDefinition = useWorkflowStore((state) => state.definition)
    const selectedNodeId = useWorkflowStore((state) => state.selectedNodeId)
    const workflowError = useWorkflowStore((state) => state.lastError)

    const runtimeStatus = useRuntimeStore((state) => state.status)
    const runtimeError = useRuntimeStore((state) => state.error)
    const runtimeProgress = useRuntimeStore((state) => state.progress)
    const runtimeOutputs = useRuntimeStore((state) => state.outputs)
    const runtimeEvents = useRuntimeStore((state) => state.events)

    const cameraX = useUiStore((state) => state.cameraX)
    const cameraY = useUiStore((state) => state.cameraY)
    const zoom = useUiStore((state) => state.zoom)
    const showGrid = useUiStore((state) => state.showGrid)

    const stopEventsRef = useRef<(() => void) | null>(null)

    const selectedNode = useMemo(
        () => workflowDefinition.nodes.find((node) => node.node_id === selectedNodeId) ?? null,
        [selectedNodeId, workflowDefinition.nodes],
    )

    const selectedDefinition = useMemo<NodeDefinition | null>(() => {
        if (!selectedNode) {
            return null
        }
        return nodes.find((item) => item.type === selectedNode.node_type) ?? null
    }, [nodes, selectedNode])
    const filteredNodeLibrary = useMemo(() => {
        const normalizedSearch = nodeSearchQuery.trim().toLowerCase()

        return nodes.filter((nodeDefinition) => {
            if (nodeCategoryFilter !== 'all' && nodeDefinition.category !== nodeCategoryFilter) {
                return false
            }

            if (nodePortFilter === 'has-input' && !nodeDefinition.ports.some((port) => port.direction === 'input')) {
                return false
            }

            if (nodePortFilter === 'has-output' && !nodeDefinition.ports.some((port) => port.direction === 'output')) {
                return false
            }

            if (!normalizedSearch) {
                return true
            }

            const searchableText = `${nodeDefinition.label} ${nodeDefinition.type}`.toLowerCase()
            return searchableText.includes(normalizedSearch)
        })
    }, [nodeCategoryFilter, nodePortFilter, nodeSearchQuery, nodes])
    const addNodeAtViewportCenter = useCallback(
        (nodeType: string) => {
            const definition = nodes.find((entry) => entry.type === nodeType)
            if (!definition) {
                return
            }
            const center = getCanvasViewportCenter()
            const worldX = cameraX + center.x / Math.max(zoom, 0.1)
            const worldY = cameraY + center.y / Math.max(zoom, 0.1)
            workflowActions.addNode(definition, worldX, worldY)
        },
        [cameraX, cameraY, nodes, zoom],
    )

    const handleZoomFromToolbar = useCallback((factor: number) => {
        const uiState = getUiState()
        const center = getCanvasViewportCenter()
        uiActions.zoomAtPoint(center.x, center.y, uiState.zoom * factor)
    }, [])

    const runWorkflow = useCallback(async () => {
        if (isRunning) {
            return
        }

        setIsRunning(true)
        runtimeActions.reset()
        setStatusText('Validating workflow...')

        try {
            const legacyGraph = workflowActions.toLegacyGraph()
            const validation = await validateWorkflow(legacyGraph)
            if (!validation.valid) {
                throw new Error(validation.errors.join('; '))
            }

            setStatusText('Starting run...')
            const execution = await executeWorkflow(legacyGraph)
            runtimeActions.startRun(execution.job_id)

            stopEventsRef.current?.()
            stopEventsRef.current = subscribeExecutionEvents(execution.job_id, {
                onEvent(event) {
                    runtimeActions.applyEvent(event)
                },
                onError(error) {
                    setStatusText(error)
                },
            })

            const finalStatus = await pollWorkflowJob(execution.job_id, execution.poll_interval, (status) => {
                runtimeActions.applyJobStatus(status)
                setStatusText(`Running (${Math.round(status.progress)}%)`)
            })

            if (finalStatus.status === 'completed') {
                setStatusText('Workflow completed')
            } else if (finalStatus.status === 'failed') {
                throw new Error(finalStatus.error || 'Workflow failed')
            } else {
                setStatusText(`Workflow ${finalStatus.status}`)
            }
        } catch (error) {
            setStatusText(error instanceof Error ? error.message : 'Execution failed')
        } finally {
            setIsRunning(false)
        }
    }, [isRunning])

    useEffect(() => {
        void nodeCatalogActions.load()
        void providerCatalogActions.load()
        return () => {
            stopEventsRef.current?.()
            stopEventsRef.current = null
        }
    }, [])

    useEffect(() => {
        const handleAddNodeEvent = (event: Event) => {
            const customEvent = event as CustomEvent<AddNodeEventDetail>
            addNodeAtViewportCenter(customEvent.detail?.nodeType || 'Prompt')
        }

        const handleRunEvent = () => {
            void runWorkflow()
        }

        window.addEventListener(WORKFLOW_ADD_EVENT, handleAddNodeEvent as EventListener)
        window.addEventListener(WORKFLOW_RUN_EVENT, handleRunEvent)

        return () => {
            window.removeEventListener(WORKFLOW_ADD_EVENT, handleAddNodeEvent as EventListener)
            window.removeEventListener(WORKFLOW_RUN_EVENT, handleRunEvent)
        }
    }, [addNodeAtViewportCenter, runWorkflow])

    return (
        <section className="workflow-shell">
            <div className="workflow-toolbar">
                <span>{statusText}</span>
                <span className={`workflow-badge status-${runtimeStatus}`}>{runtimeStatus}</span>
                <span>{Math.round(runtimeProgress)}%</span>
                <button type="button" onClick={() => handleZoomFromToolbar(1.1)}>
                    Zoom +
                </button>
                <button type="button" onClick={() => handleZoomFromToolbar(0.9)}>
                    Zoom -
                </button>
                <button type="button" onClick={() => uiActions.toggleGrid()}>
                    {showGrid ? 'Hide Grid' : 'Show Grid'}
                </button>
                <button type="button" className="workflow-run" onClick={() => void runWorkflow()} disabled={isRunning}>
                    {isRunning ? 'Running...' : 'Run Workflow'}
                </button>
            </div>

            {(nodeCatalogError || workflowError || runtimeError) && (
                <div className="workflow-error">
                    {nodeCatalogError || workflowError || runtimeError}
                </div>
            )}

            <div className="workflow-layout">
                <div className="workflow-canvas-panel">
                    {nodeCatalogLoading ? <div className="workflow-loading">Loading node catalog...</div> : <GraphCanvas nodeCatalog={nodes} />}
                </div>

                <aside className="workflow-sidepanel">
                    <section className="workflow-panel workflow-node-library">
                        <h2>Node Library</h2>
                        <div className="workflow-node-library-controls">
                            <input
                                type="search"
                                value={nodeSearchQuery}
                                placeholder="Search by name"
                                onChange={(event) => setNodeSearchQuery(event.target.value)}
                            />
                            <div className="workflow-node-library-filters">
                                <select
                                    aria-label="Filter node category"
                                    value={nodeCategoryFilter}
                                    onChange={(event) => setNodeCategoryFilter(event.target.value as NodeLibraryCategoryFilter)}
                                >
                                    <option value="all">All categories</option>
                                    {(['input', 'process', 'output'] as const).map((category) => (
                                        <option key={category} value={category}>
                                            {NODE_CATEGORY_LABELS[category]}
                                        </option>
                                    ))}
                                </select>
                                <select
                                    aria-label="Filter node ports"
                                    value={nodePortFilter}
                                    onChange={(event) => setNodePortFilter(event.target.value as NodeLibraryPortFilter)}
                                >
                                    <option value="all">All ports</option>
                                    <option value="has-input">Has input</option>
                                    <option value="has-output">Has output</option>
                                </select>
                            </div>
                        </div>
                        <div className="workflow-node-list">
                            {filteredNodeLibrary.map((node) => (
                                <button key={node.type} type="button" onClick={() => addNodeAtViewportCenter(node.type)}>
                                    + {node.label}
                                </button>
                            ))}
                            {filteredNodeLibrary.length === 0 && <p className="workflow-node-empty">No nodes match the current filters.</p>}
                        </div>
                    </section>

                    <section className="workflow-panel">
                        <h2>Inspector</h2>
                        {!selectedNode || !selectedDefinition ? (
                            <p>Select a node to edit its configuration.</p>
                        ) : (
                            <div className="workflow-inspector-fields">
                                <h3>{selectedDefinition.label}</h3>
                                {selectedDefinition.config_schema.map((field) => {
                                    const value = selectedNode.config[field.key] ?? field.default ?? ''
                                    return (
                                        <label key={field.key}>
                                            <span>{field.label}</span>
                                            {renderField(field, value, (next) => {
                                                workflowActions.updateNodeConfig(selectedNode.node_id, { [field.key]: next })
                                            })}
                                        </label>
                                    )
                                })}

                                {selectedNode.node_type === 'Output' && (
                                    <label>
                                        <span>Runtime Output</span>
                                        <textarea
                                            value={runtimeOutputs[selectedNode.node_id] || ''}
                                            rows={5}
                                            readOnly
                                        />
                                    </label>
                                )}

                                <button type="button" className="workflow-delete" onClick={() => workflowActions.deleteNode(selectedNode.node_id)}>
                                    Delete Node
                                </button>
                            </div>
                        )}
                    </section>

                    <section className="workflow-panel">
                        <h2>Runtime Events</h2>
                        <div className="workflow-events">
                            {runtimeEvents.slice(-10).reverse().map((event) => (
                                <article key={`${event.sequence}-${event.event_type}`}>
                                    <strong>{event.event_type}</strong>
                                    <span>{event.step_id || 'run'}</span>
                                </article>
                            ))}
                            {runtimeEvents.length === 0 && <p>No events yet.</p>}
                        </div>
                    </section>
                </aside>
            </div>
        </section>
    )
}

