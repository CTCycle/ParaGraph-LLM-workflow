# Official Docs Index

## TOC
- Core docs and home pages
- Learn docs by area
- API reference coverage
- UI components docs
- Migration and release tracking
- What to load for each task

## Core docs and home pages
- React Flow docs home: https://reactflow.dev/
- Learn landing: https://reactflow.dev/learn
- API reference landing: https://reactflow.dev/api-reference
- Examples landing: https://reactflow.dev/examples
- UI components landing: https://reactflow.dev/ui/components
- Changelog/updates: https://reactflow.dev/whats-new

## Learn docs by area

### Getting started
- Quick start: https://reactflow.dev/learn
- Installation and requirements: https://reactflow.dev/learn/getting-started/installation-and-requirements
- Build your first flow: https://reactflow.dev/learn/concepts/building-a-flow

### Concepts
- Terms and definitions: https://reactflow.dev/learn/concepts/terms-and-definitions
- Built-in nodes: https://reactflow.dev/learn/concepts/built-in-nodes
- Adding interactivity: https://reactflow.dev/learn/concepts/adding-interactivity
- Utility classes: https://reactflow.dev/learn/customization/utility-classes
- Add node on edge drop: https://reactflow.dev/learn/concepts/adding-nodes-on-edge-drop

### Customization and layout
- Theming: https://reactflow.dev/learn/customization/theming
- Custom nodes: https://reactflow.dev/learn/customization/custom-nodes
- Custom edges: https://reactflow.dev/learn/customization/custom-edges
- Handles: https://reactflow.dev/learn/customization/handles
- Edge labels: https://reactflow.dev/learn/customization/edge-labels
- Connection line: https://reactflow.dev/learn/customization/connection-line
- Layouting overview: https://reactflow.dev/learn/layouting/layouting
- Sub flows and parent-child relations: https://reactflow.dev/learn/layouting/sub-flows

### Advanced use
- Performance: https://reactflow.dev/learn/advanced-use/performance
- Accessibility: https://reactflow.dev/learn/advanced-use/accessibility
- State management: https://reactflow.dev/learn/advanced-use/state-management
- Devtools and debugging: https://reactflow.dev/learn/advanced-use/devtools-and-debugging
- Server-side rendering and static generation: https://reactflow.dev/learn/advanced-use/ssr-ssg-configuration
- Testing: https://reactflow.dev/learn/advanced-use/testing
- TypeScript: https://reactflow.dev/learn/advanced-use/typescript
- Computing flows: https://reactflow.dev/learn/advanced-use/computing-flows
- Whiteboard features: https://reactflow.dev/learn/advanced-use/whiteboard

### Troubleshooting and migration
- Common errors: https://reactflow.dev/learn/troubleshooting/common-errors
- Migrate to v12: https://reactflow.dev/learn/troubleshooting/migrate-to-v12
- Migrate to v11: https://reactflow.dev/learn/troubleshooting/migrate-to-v11
- Migrate to v10: https://reactflow.dev/learn/troubleshooting/migrate-to-v10
- Remove attribution: https://reactflow.dev/learn/troubleshooting/remove-attribution

## API reference coverage

Use these pages as canonical indexes (full lists are maintained by React Flow and can change by release):

- Components index: https://reactflow.dev/api-reference/components
- Hooks index: https://reactflow.dev/api-reference/hooks
- Types index: https://reactflow.dev/api-reference/types
- Utils index: https://reactflow.dev/api-reference/utils

### Components listed in official navigation
- ReactFlow
- ReactFlowProvider
- Background
- BaseEdge
- ControlButton
- Controls
- EdgeLabelRenderer
- EdgeText
- Handle
- MiniMap
- NodeResizeControl
- NodeResizer
- NodeToolbar
- Panel
- ViewportPortal

### Hooks listed in official navigation
- useConnection
- useEdges
- useEdgesState
- useHandleConnections
- useInternalNode
- useKeyPress
- useNodeConnections
- useNodeId
- useNodes
- useNodesData
- useNodesInitialized
- useNodesState
- useOnSelectionChange
- useOnViewportChange
- useReactFlow
- useStore
- useStoreApi
- useUpdateNodeInternals
- useViewport

### Types listed in official navigation
- BackgroundVariant
- ColorMode
- ConnectionLineType
- MarkerType
- PanOnScrollMode
- Position
- SelectionMode
- Connection
- ConnectionState
- CoordinateExtent
- DefaultEdgeOptions
- DeleteElements
- Edge
- EdgeChange
- EdgeMouseHandler
- EdgeProps
- EdgeTypes
- FitViewOptions
- IsValidConnection
- KeyCode
- Node
- NodeChange
- NodeConnection
- NodeHandle
- NodeMouseHandler
- NodeOrigin
- NodeProps
- NodeTypes
- OnBeforeDelete
- OnConnect
- OnConnectStart
- OnConnectEnd
- OnDelete
- OnEdgeUpdateFunc
- OnEdgesChange
- OnEdgesDelete
- OnError
- OnInit
- OnMove
- OnNodeDrag
- OnNodesChange
- OnNodesDelete
- OnReconnect
- OnSelectionChangeFunc
- OnSelectionDrag
- OnSelectionStart
- OnSelectionEnd
- OnViewportChange
- ProOptions
- ReactFlowInstance
- ResizeParams
- SnapGrid
- Viewport

### Utils listed in official navigation
- addEdge
- applyEdgeChanges
- applyNodeChanges
- getBezierPath
- getConnectedEdges
- getIncomers
- getNodesBounds
- getOutgoers
- getSimpleBezierPath
- getSmoothStepPath
- getStraightPath
- getViewportForBounds
- isEdge
- reconnectEdge

## UI components docs
- UI component list root: https://reactflow.dev/ui/components
- Component docs currently include primitives such as:
- BaseNode
- BaseHandle
- ButtonEdge
- DataEdge
- LabeledHandle
- NodeTooltip
- NodeToolbar
- StatusIndicator
- Note
- ResizableNode
- RotatableNode
- ExpandCollapse

## Migration and release tracking
- Always check updates before giving version-sensitive advice:
- https://reactflow.dev/whats-new
- At the time this skill was assembled (March 13, 2026), docs pages indicate React Flow 12.x with recent updates in late 2025 and early 2026.

## What to load for each task
- New flow implementation: load getting started + concepts + `examples-index.md`.
- Custom nodes/edges: load customization pages + API component docs.
- Warning/error fix: load troubleshooting pages + `troubleshooting-playbook.md`.
- Performance work: load advanced performance page + `best-practices.md`.
- Major upgrades: load migration pages + latest `whats-new`.
