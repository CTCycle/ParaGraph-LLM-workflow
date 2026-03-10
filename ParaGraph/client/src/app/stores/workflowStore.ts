import { addEdge, addNode, moveNode, removeNode, updateNodeConfig } from '../../graph/core/model'
import { toLegacyWorkflowGraph } from '../../graph/core/serialization'
import { validateEdgeCompatibility } from '../../graph/core/validators'
import { CommandHistory } from '../../graph/core/history'
import { buildEmptyVisualGraph, buildEmptyWorkflowDefinition } from '../../workflow/schema/migrations'
import { NodeDefinition, WorkflowDefinition, VisualGraph } from '../../workflow/schema/types'
import { createStore, useStore } from './store'

export interface WorkflowState {
    workflowId: string
    name: string
    definition: WorkflowDefinition
    visualGraph: VisualGraph
    selectedNodeId: string | null
    lastError: string | null
}

const history = new CommandHistory<Pick<WorkflowState, 'definition' | 'visualGraph'>>()

function defaultState(): WorkflowState {
    return {
        workflowId: 'local-workflow',
        name: 'Local Workflow',
        definition: buildEmptyWorkflowDefinition(),
        visualGraph: buildEmptyVisualGraph(),
        selectedNodeId: null,
        lastError: null,
    }
}

const workflowStore = createStore<WorkflowState>(defaultState())

function snapshotForHistory(state: WorkflowState): Pick<WorkflowState, 'definition' | 'visualGraph'> {
    return {
        definition: structuredClone(state.definition),
        visualGraph: structuredClone(state.visualGraph),
    }
}

function persistState(_state: WorkflowState): void {
    // Intentionally no-op: workflow starts empty on each application launch.
}

function commitMutation(mutator: (state: WorkflowState) => WorkflowState, kind: 'mutate' | 'move' = 'mutate'): void {
    const before = snapshotForHistory(workflowStore.getState())
    workflowStore.setState((current) => {
        const next = mutator(current)
        persistState(next)
        return next
    })
    const after = snapshotForHistory(workflowStore.getState())
    history.record({
        before,
        after,
        kind,
        timestamp: Date.now(),
    })
}

export const workflowActions = {
    setSelectedNode(nodeId: string | null) {
        workflowStore.setState((current) => ({ ...current, selectedNodeId: nodeId }))
    },

    addNode(nodeDefinition: NodeDefinition, x: number, y: number) {
        commitMutation((current) => {
            const nodeId = `${nodeDefinition.type.toLowerCase()}_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 6)}`
            const defaults = Object.fromEntries(
                nodeDefinition.config_schema.map((field) => [field.key, field.default ?? '']),
            )

            const graph = addNode(
                {
                    definition: current.definition,
                    visual: { nodes: current.visualGraph.nodes },
                },
                {
                    node_id: nodeId,
                    node_type: nodeDefinition.type,
                    config: defaults,
                },
                {
                    node_id: nodeId,
                    x,
                    y,
                    width: 280,
                    height: 180,
                    collapsed: false,
                },
            )

            return {
                ...current,
                definition: graph.definition,
                visualGraph: {
                    ...current.visualGraph,
                    nodes: graph.visual.nodes,
                },
                selectedNodeId: nodeId,
                lastError: null,
            }
        })
    },

    moveNode(nodeId: string, x: number, y: number) {
        commitMutation(
            (current) => {
                const graph = moveNode(
                    {
                        definition: current.definition,
                        visual: { nodes: current.visualGraph.nodes },
                    },
                    nodeId,
                    x,
                    y,
                )
                return {
                    ...current,
                    visualGraph: {
                        ...current.visualGraph,
                        nodes: graph.visual.nodes,
                    },
                }
            },
            'move',
        )
    },

    updateNodeConfig(nodeId: string, patch: Record<string, unknown>) {
        commitMutation((current) => {
            const graph = updateNodeConfig(
                {
                    definition: current.definition,
                    visual: { nodes: current.visualGraph.nodes },
                },
                nodeId,
                patch,
            )
            return {
                ...current,
                definition: graph.definition,
            }
        })
    },

    deleteNode(nodeId: string) {
        commitMutation((current) => {
            const graph = removeNode(
                {
                    definition: current.definition,
                    visual: { nodes: current.visualGraph.nodes },
                },
                nodeId,
            )
            return {
                ...current,
                definition: graph.definition,
                visualGraph: {
                    ...current.visualGraph,
                    nodes: graph.visual.nodes,
                },
                selectedNodeId: current.selectedNodeId === nodeId ? null : current.selectedNodeId,
            }
        })
    },

    connectPorts(edge: WorkflowDefinition['edges'][number], catalog: NodeDefinition[]) {
        const validationError = validateEdgeCompatibility(workflowStore.getState().definition, catalog, edge)
        if (validationError) {
            workflowStore.setState((current) => ({ ...current, lastError: validationError }))
            return false
        }

        commitMutation((current) => {
            const graph = addEdge(
                {
                    definition: current.definition,
                    visual: { nodes: current.visualGraph.nodes },
                },
                edge,
            )
            return {
                ...current,
                definition: graph.definition,
                lastError: null,
            }
        })

        return true
    },

    clearError() {
        workflowStore.setState((current) => ({ ...current, lastError: null }))
    },

    undo() {
        workflowStore.setState((current) => {
            const restored = history.undo(snapshotForHistory(current))
            const next = {
                ...current,
                definition: restored.definition,
                visualGraph: {
                    ...current.visualGraph,
                    nodes: restored.visualGraph.nodes,
                },
            }
            persistState(next)
            return next
        })
    },

    redo() {
        workflowStore.setState((current) => {
            const restored = history.redo(snapshotForHistory(current))
            const next = {
                ...current,
                definition: restored.definition,
                visualGraph: {
                    ...current.visualGraph,
                    nodes: restored.visualGraph.nodes,
                },
            }
            persistState(next)
            return next
        })
    },

    toLegacyGraph() {
        const state = workflowStore.getState()
        return toLegacyWorkflowGraph(state.definition, state.visualGraph)
    },
}

export function useWorkflowStore<R>(selector: (state: WorkflowState) => R): R {
    return useStore(workflowStore, selector)
}

export function getWorkflowState(): WorkflowState {
    return workflowStore.getState()
}
