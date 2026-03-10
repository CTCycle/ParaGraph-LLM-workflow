import { type PointerEvent as ReactPointerEvent, useCallback, useEffect, useMemo, useRef } from 'react'

import { workflowActions, useWorkflowStore } from '../../app/stores/workflowStore'
import { getUiState, uiActions, useUiStore } from '../../app/stores/uiStore'
import { useRuntimeStore } from '../../app/stores/runtimeStore'
import { NodeDefinition, WorkflowEdgeSpec, WorkflowNodeSpec } from '../../workflow/schema/types'
import './GraphCanvas.css'

type InteractionState =
    | { mode: 'idle' }
    | { mode: 'pan'; startX: number; startY: number; initialCameraX: number; initialCameraY: number }
    | { mode: 'drag-node'; nodeId: string; offsetX: number; offsetY: number }
    | { mode: 'connect'; fromNodeId: string; fromPort: string }

const PORT_RADIUS = 6

function worldToScreen(worldX: number, worldY: number, cameraX: number, cameraY: number, zoom: number) {
    return {
        x: (worldX - cameraX) * zoom,
        y: (worldY - cameraY) * zoom,
    }
}

function screenToWorld(screenX: number, screenY: number, cameraX: number, cameraY: number, zoom: number) {
    return {
        x: screenX / zoom + cameraX,
        y: screenY / zoom + cameraY,
    }
}

function getPortPosition(
    nodeX: number,
    nodeY: number,
    nodeWidth: number,
    index: number,
    direction: 'input' | 'output',
): { x: number; y: number } {
    const y = nodeY + 54 + index * 22
    return {
        x: direction === 'input' ? nodeX : nodeX + nodeWidth,
        y,
    }
}

export interface GraphCanvasProps {
    nodeCatalog: NodeDefinition[]
}

export default function GraphCanvas({ nodeCatalog }: GraphCanvasProps) {
    const canvasRef = useRef<HTMLCanvasElement | null>(null)
    const containerRef = useRef<HTMLDivElement | null>(null)
    const interactionRef = useRef<InteractionState>({ mode: 'idle' })

    const definition = useWorkflowStore((state) => state.definition)
    const visualNodes = useWorkflowStore((state) => state.visualGraph.nodes)
    const selectedNodeId = useWorkflowStore((state) => state.selectedNodeId)
    const runtimeStatus = useRuntimeStore((state) => state.status)
    const runtimeStepStatus = useRuntimeStore((state) => state.stepStatus)

    const cameraX = useUiStore((state) => state.cameraX)
    const cameraY = useUiStore((state) => state.cameraY)
    const zoom = useUiStore((state) => state.zoom)
    const showGrid = useUiStore((state) => state.showGrid)
    const connectingFrom = useUiStore((state) => state.connectingFrom)
    const pointerWorld = useUiStore((state) => state.pointerWorld)

    const nodeDefinitionByType = useMemo(
        () => Object.fromEntries(nodeCatalog.map((item) => [item.type, item])),
        [nodeCatalog],
    )

    const visualByNodeId = useMemo(
        () => Object.fromEntries(visualNodes.map((node) => [node.node_id, node])),
        [visualNodes],
    )

    const draw = useCallback(() => {
        const canvas = canvasRef.current
        const container = containerRef.current
        if (!canvas || !container) {
            return
        }

        const viewportWidth = Math.max(1, container.clientWidth)
        const viewportHeight = Math.max(1, container.clientHeight)
        const dpr = window.devicePixelRatio || 1
        const pixelWidth = Math.max(1, Math.round(viewportWidth * dpr))
        const pixelHeight = Math.max(1, Math.round(viewportHeight * dpr))

        if (canvas.width !== pixelWidth || canvas.height !== pixelHeight) {
            canvas.width = pixelWidth
            canvas.height = pixelHeight
        }

        const context = canvas.getContext('2d')
        if (!context) {
            return
        }

        context.setTransform(dpr, 0, 0, dpr, 0, 0)
        context.clearRect(0, 0, viewportWidth, viewportHeight)

        if (showGrid) {
            const gridGap = zoom < 0.5 ? 120 : 24
            context.strokeStyle = 'rgba(36, 58, 75, 0.5)'
            context.lineWidth = 1

            const startX = (-(cameraX * zoom) % gridGap + gridGap) % gridGap
            const startY = (-(cameraY * zoom) % gridGap + gridGap) % gridGap

            for (let x = startX; x <= viewportWidth; x += gridGap) {
                context.beginPath()
                context.moveTo(x, 0)
                context.lineTo(x, viewportHeight)
                context.stroke()
            }
            for (let y = startY; y <= viewportHeight; y += gridGap) {
                context.beginPath()
                context.moveTo(0, y)
                context.lineTo(viewportWidth, y)
                context.stroke()
            }
        }

        const edges = definition.edges
        context.lineWidth = 2
        context.strokeStyle = 'rgba(82, 176, 255, 0.85)'

        for (const edge of edges) {
            const sourceVisual = visualByNodeId[edge.source.node_id]
            const targetVisual = visualByNodeId[edge.target.node_id]
            const sourceNodeSpec = definition.nodes.find((node) => node.node_id === edge.source.node_id)
            const targetNodeSpec = definition.nodes.find((node) => node.node_id === edge.target.node_id)
            if (!sourceVisual || !targetVisual || !sourceNodeSpec || !targetNodeSpec) {
                continue
            }

            const sourceDef = nodeDefinitionByType[sourceNodeSpec.node_type]
            const targetDef = nodeDefinitionByType[targetNodeSpec.node_type]
            if (!sourceDef || !targetDef) {
                continue
            }

            const sourceIndex = sourceDef.ports.filter((port) => port.direction === 'output').findIndex((port) => port.handle === edge.source.port)
            const targetIndex = targetDef.ports.filter((port) => port.direction === 'input').findIndex((port) => port.handle === edge.target.port)
            if (sourceIndex < 0 || targetIndex < 0) {
                continue
            }

            const sourcePort = getPortPosition(
                sourceVisual.x,
                sourceVisual.y,
                sourceVisual.width,
                sourceIndex,
                'output',
            )
            const targetPort = getPortPosition(
                targetVisual.x,
                targetVisual.y,
                targetVisual.width,
                targetIndex,
                'input',
            )

            const sourceScreen = worldToScreen(sourcePort.x, sourcePort.y, cameraX, cameraY, zoom)
            const targetScreen = worldToScreen(targetPort.x, targetPort.y, cameraX, cameraY, zoom)
            const cpOffset = Math.max(40, Math.abs(targetScreen.x - sourceScreen.x) * 0.45)

            context.beginPath()
            context.moveTo(sourceScreen.x, sourceScreen.y)
            context.bezierCurveTo(
                sourceScreen.x + cpOffset,
                sourceScreen.y,
                targetScreen.x - cpOffset,
                targetScreen.y,
                targetScreen.x,
                targetScreen.y,
            )
            context.stroke()
        }

        if (connectingFrom && pointerWorld) {
            const sourceVisual = visualByNodeId[connectingFrom.nodeId]
            const sourceNodeSpec = definition.nodes.find((node) => node.node_id === connectingFrom.nodeId)
            if (sourceVisual && sourceNodeSpec) {
                const sourceDef = nodeDefinitionByType[sourceNodeSpec.node_type]
                const outputPorts = sourceDef?.ports.filter((port) => port.direction === 'output') ?? []
                const sourceIndex = outputPorts.findIndex((port) => port.handle === connectingFrom.port)
                if (sourceIndex >= 0) {
                    const sourcePort = getPortPosition(
                        sourceVisual.x,
                        sourceVisual.y,
                        sourceVisual.width,
                        sourceIndex,
                        'output',
                    )
                    const sourceScreen = worldToScreen(sourcePort.x, sourcePort.y, cameraX, cameraY, zoom)
                    const pointerScreen = worldToScreen(pointerWorld.x, pointerWorld.y, cameraX, cameraY, zoom)
                    const cpOffset = Math.max(40, Math.abs(pointerScreen.x - sourceScreen.x) * 0.45)

                    context.strokeStyle = 'rgba(252, 211, 77, 0.85)'
                    context.beginPath()
                    context.moveTo(sourceScreen.x, sourceScreen.y)
                    context.bezierCurveTo(
                        sourceScreen.x + cpOffset,
                        sourceScreen.y,
                        pointerScreen.x - cpOffset,
                        pointerScreen.y,
                        pointerScreen.x,
                        pointerScreen.y,
                    )
                    context.stroke()
                    context.strokeStyle = 'rgba(82, 176, 255, 0.85)'
                }
            }
        }

        for (const visualNode of visualNodes) {
            const node = definition.nodes.find((entry) => entry.node_id === visualNode.node_id)
            if (!node) {
                continue
            }
            const nodeDefinition = nodeDefinitionByType[node.node_type]
            if (!nodeDefinition) {
                continue
            }

            const nodeScreen = worldToScreen(visualNode.x, visualNode.y, cameraX, cameraY, zoom)
            const nodeWidth = visualNode.width * zoom
            const nodeHeight = visualNode.height * zoom

            const isSelected = selectedNodeId === node.node_id
            const stepStatus = runtimeStepStatus[node.node_id]

            context.fillStyle = 'rgba(16, 24, 40, 0.94)'
            context.strokeStyle = isSelected ? '#facc15' : '#3b82f6'
            if (stepStatus === 'running') {
                context.strokeStyle = '#22c55e'
            }
            if (stepStatus === 'failed') {
                context.strokeStyle = '#ef4444'
            }
            if (runtimeStatus === 'completed' && stepStatus === 'completed') {
                context.strokeStyle = '#16a34a'
            }

            context.lineWidth = isSelected ? 2.5 : 1.2
            context.beginPath()
            context.roundRect(nodeScreen.x, nodeScreen.y, nodeWidth, nodeHeight, 10)
            context.fill()
            context.stroke()

            if (zoom > 0.35) {
                context.fillStyle = '#e2e8f0'
                context.font = `${Math.max(10, 14 * zoom)}px ui-sans-serif, system-ui`
                context.fillText(nodeDefinition.label, nodeScreen.x + 12 * zoom, nodeScreen.y + 22 * zoom)

                const inputPorts = nodeDefinition.ports.filter((port) => port.direction === 'input')
                const outputPorts = nodeDefinition.ports.filter((port) => port.direction === 'output')

                context.font = `${Math.max(8, 11 * zoom)}px ui-sans-serif, system-ui`

                inputPorts.forEach((port, index) => {
                    const portWorld = getPortPosition(visualNode.x, visualNode.y, visualNode.width, index, 'input')
                    const portScreen = worldToScreen(portWorld.x, portWorld.y, cameraX, cameraY, zoom)
                    context.fillStyle = '#0ea5e9'
                    context.beginPath()
                    context.arc(portScreen.x, portScreen.y, PORT_RADIUS * zoom, 0, Math.PI * 2)
                    context.fill()

                    context.fillStyle = 'rgba(203, 213, 225, 0.9)'
                    context.fillText(port.label, nodeScreen.x + 14 * zoom, portScreen.y + 4 * zoom)
                })

                outputPorts.forEach((port, index) => {
                    const portWorld = getPortPosition(visualNode.x, visualNode.y, visualNode.width, index, 'output')
                    const portScreen = worldToScreen(portWorld.x, portWorld.y, cameraX, cameraY, zoom)
                    context.fillStyle = '#38bdf8'
                    context.beginPath()
                    context.arc(portScreen.x, portScreen.y, PORT_RADIUS * zoom, 0, Math.PI * 2)
                    context.fill()

                    const textWidth = context.measureText(port.label).width
                    context.fillStyle = 'rgba(203, 213, 225, 0.9)'
                    context.fillText(
                        port.label,
                        nodeScreen.x + nodeWidth - textWidth - 14 * zoom,
                        portScreen.y + 4 * zoom,
                    )
                })
            }
        }
    }, [
        cameraX,
        cameraY,
        connectingFrom,
        definition.edges,
        definition.nodes,
        nodeDefinitionByType,
        pointerWorld,
        runtimeStatus,
        runtimeStepStatus,
        selectedNodeId,
        showGrid,
        visualByNodeId,
        visualNodes,
        zoom,
    ])

    useEffect(() => {
        draw()
    }, [draw])

    useEffect(() => {
        const container = containerRef.current
        if (!container) {
            return
        }
        const observer = new ResizeObserver(() => draw())
        observer.observe(container)
        return () => observer.disconnect()
    }, [draw])

    const findPortHit = useCallback(
        (worldX: number, worldY: number): { nodeId: string; port: string; direction: 'input' | 'output' } | null => {
            const hitRadius = Math.max(7, PORT_RADIUS / zoom + 2)
            for (const visualNode of [...visualNodes].reverse()) {
                const node = definition.nodes.find((entry) => entry.node_id === visualNode.node_id)
                if (!node) {
                    continue
                }
                const nodeDef = nodeDefinitionByType[node.node_type]
                if (!nodeDef) {
                    continue
                }

                const inputPorts = nodeDef.ports.filter((port) => port.direction === 'input')
                const outputPorts = nodeDef.ports.filter((port) => port.direction === 'output')

                for (let i = 0; i < inputPorts.length; i += 1) {
                    const port = inputPorts[i]
                    const position = getPortPosition(visualNode.x, visualNode.y, visualNode.width, i, 'input')
                    if (Math.hypot(worldX - position.x, worldY - position.y) <= hitRadius) {
                        return { nodeId: node.node_id, port: port.handle, direction: 'input' }
                    }
                }

                for (let i = 0; i < outputPorts.length; i += 1) {
                    const port = outputPorts[i]
                    const position = getPortPosition(visualNode.x, visualNode.y, visualNode.width, i, 'output')
                    if (Math.hypot(worldX - position.x, worldY - position.y) <= hitRadius) {
                        return { nodeId: node.node_id, port: port.handle, direction: 'output' }
                    }
                }
            }
            return null
        },
        [definition.nodes, nodeDefinitionByType, visualNodes, zoom],
    )

    const findNodeHit = useCallback(
        (worldX: number, worldY: number): WorkflowNodeSpec | null => {
            for (const visualNode of [...visualNodes].reverse()) {
                const inside =
                    worldX >= visualNode.x &&
                    worldX <= visualNode.x + visualNode.width &&
                    worldY >= visualNode.y &&
                    worldY <= visualNode.y + visualNode.height
                if (!inside) {
                    continue
                }
                const node = definition.nodes.find((entry) => entry.node_id === visualNode.node_id)
                if (node) {
                    return node
                }
            }
            return null
        },
        [definition.nodes, visualNodes],
    )

    const handlePointerDown = useCallback(
        (event: ReactPointerEvent<HTMLCanvasElement>) => {
            const canvas = canvasRef.current
            if (!canvas) {
                return
            }
            canvas.setPointerCapture(event.pointerId)
            const bounds = canvas.getBoundingClientRect()
            const world = screenToWorld(event.clientX - bounds.left, event.clientY - bounds.top, cameraX, cameraY, zoom)

            const portHit = findPortHit(world.x, world.y)
            if (portHit?.direction === 'output') {
                interactionRef.current = { mode: 'connect', fromNodeId: portHit.nodeId, fromPort: portHit.port }
                uiActions.startConnection(portHit.nodeId, portHit.port)
                uiActions.setPointerWorld(world.x, world.y)
                workflowActions.setSelectedNode(portHit.nodeId)
                return
            }

            const nodeHit = findNodeHit(world.x, world.y)
            if (nodeHit) {
                const visualNode = visualByNodeId[nodeHit.node_id]
                if (!visualNode) {
                    return
                }
                interactionRef.current = {
                    mode: 'drag-node',
                    nodeId: nodeHit.node_id,
                    offsetX: world.x - visualNode.x,
                    offsetY: world.y - visualNode.y,
                }
                workflowActions.setSelectedNode(nodeHit.node_id)
                return
            }

            interactionRef.current = {
                mode: 'pan',
                startX: event.clientX,
                startY: event.clientY,
                initialCameraX: cameraX,
                initialCameraY: cameraY,
            }
            workflowActions.setSelectedNode(null)
        },
        [cameraX, cameraY, findNodeHit, findPortHit, visualByNodeId, zoom],
    )

    const handlePointerMove = useCallback(
        (event: ReactPointerEvent<HTMLCanvasElement>) => {
            const canvas = canvasRef.current
            if (!canvas) {
                return
            }
            const bounds = canvas.getBoundingClientRect()
            const world = screenToWorld(event.clientX - bounds.left, event.clientY - bounds.top, cameraX, cameraY, zoom)

            const interaction = interactionRef.current
            if (interaction.mode === 'drag-node') {
                workflowActions.moveNode(interaction.nodeId, world.x - interaction.offsetX, world.y - interaction.offsetY)
                return
            }
            if (interaction.mode === 'pan') {
                const dx = event.clientX - interaction.startX
                const dy = event.clientY - interaction.startY
                uiActions.setCamera(interaction.initialCameraX - dx / zoom, interaction.initialCameraY - dy / zoom, zoom)
                return
            }
            if (interaction.mode === 'connect') {
                uiActions.setPointerWorld(world.x, world.y)
            }
        },
        [cameraX, cameraY, zoom],
    )

    const handlePointerUp = useCallback(
        (event: ReactPointerEvent<HTMLCanvasElement>) => {
            const canvas = canvasRef.current
            const interaction = interactionRef.current

            if (canvas) {
                canvas.releasePointerCapture(event.pointerId)
                const bounds = canvas.getBoundingClientRect()
                const world = screenToWorld(event.clientX - bounds.left, event.clientY - bounds.top, cameraX, cameraY, zoom)

                if (interaction.mode === 'connect') {
                    const targetPort = findPortHit(world.x, world.y)
                    if (targetPort && targetPort.direction === 'input') {
                        const edge: WorkflowEdgeSpec = {
                            edge_id: `edge_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 6)}`,
                            source: {
                                node_id: interaction.fromNodeId,
                                port: interaction.fromPort,
                            },
                            target: {
                                node_id: targetPort.nodeId,
                                port: targetPort.port,
                            },
                        }
                        workflowActions.connectPorts(edge, nodeCatalog)
                    }
                }
            }

            interactionRef.current = { mode: 'idle' }
            uiActions.clearConnection()
        },
        [cameraX, cameraY, findPortHit, nodeCatalog, zoom],
    )

    const handleWheel = useCallback(
        (event: React.WheelEvent<HTMLCanvasElement>) => {
            event.preventDefault()
            event.stopPropagation()
            const canvas = canvasRef.current
            if (!canvas) {
                return
            }

            const bounds = canvas.getBoundingClientRect()
            const pointerX = event.clientX - bounds.left
            const pointerY = event.clientY - bounds.top
            const nextZoom = event.deltaY < 0 ? zoom * 1.1 : zoom * 0.9
            uiActions.zoomAtPoint(pointerX, pointerY, nextZoom)
        },
        [zoom],
    )

    useEffect(() => {
        const onKeyDown = (event: KeyboardEvent) => {
            const uiState = getUiState()
            if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'z') {
                event.preventDefault()
                if (event.shiftKey) {
                    workflowActions.redo()
                } else {
                    workflowActions.undo()
                }
                return
            }
            if (event.key === 'Delete' || event.key === 'Backspace') {
                const selected = selectedNodeId
                if (selected) {
                    workflowActions.deleteNode(selected)
                }
                return
            }
            if (event.key.toLowerCase() === 'g' && (event.ctrlKey || event.metaKey)) {
                event.preventDefault()
                uiActions.toggleGrid()
                return
            }
            if (event.key === 'Escape' && uiState.connectingFrom) {
                uiActions.clearConnection()
                interactionRef.current = { mode: 'idle' }
            }
        }

        window.addEventListener('keydown', onKeyDown)
        return () => window.removeEventListener('keydown', onKeyDown)
    }, [selectedNodeId])

    return (
        <div ref={containerRef} className="graph-canvas-root">
            <canvas
                ref={canvasRef}
                className="graph-canvas-surface"
                onPointerDown={handlePointerDown}
                onPointerMove={handlePointerMove}
                onPointerUp={handlePointerUp}
                onWheel={handleWheel}
            />
        </div>
    )
}

