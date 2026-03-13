# Best Practices

## TOC
- Baseline setup
- State architecture
- Custom nodes and edges
- Connection and graph integrity
- Performance engineering
- TypeScript strategy
- Accessibility and UX
- SSR and export paths
- Testing strategy

## Baseline setup
- Install with `npm install @xyflow/react`.
- Import styles once at app entry: `@xyflow/react/dist/style.css`.
- Give the flow container explicit width and height.
- Prefer controlled state (`nodes`, `edges`, change callbacks) for deterministic behavior.

## State architecture
- Keep graph data in one authoritative store (React state, Zustand, or external store).
- Use immutable updates for nodes and edges.
- Use helper utilities (`applyNodeChanges`, `applyEdgeChanges`, `addEdge`) unless custom behavior is required.
- Keep domain data in `node.data` and avoid derived data duplication.

## Custom nodes and edges
- Keep `nodeTypes` and `edgeTypes` stable with `useMemo` or module-level constants.
- Use custom node components for business logic, not ad hoc rendering in parent components.
- Use `Handle` IDs when multiple handles of same type exist on one node.
- Call `useUpdateNodeInternals(nodeId)` after programmatic handle changes.
- Hide handles with `opacity: 0` or `visibility: hidden`, not `display: none`.

## Connection and graph integrity
- Validate edges in `isValidConnection` when DAG constraints or schema rules apply.
- Reject cycles proactively in connection handlers when needed.
- Ensure all edges reference existing source and target nodes.
- Use deterministic edge IDs to prevent stale reconnection behavior.

## Performance engineering
- Avoid broad subscriptions to nodes/edges in many child components.
- Use narrow selectors with `useStore` where possible.
- Memoize callbacks (`onConnect`, `onNodesChange`, `onEdgesChange`) and heavy props.
- Avoid rebuilding arrays/objects every render unless values changed.
- Gate expensive node content behind zoom thresholds when appropriate.
- Profile drag + zoom + selection interactions with realistic graph sizes.

## TypeScript strategy
- Define explicit node and edge unions:
- `type AppNode = Node<MyData, "typeA" | "typeB"> | ...`
- `type AppEdge = Edge<MyEdgeData, "custom"> | ...`
- Pass generics to hooks and `ReactFlowInstance` methods.
- Use typed wrappers for custom node `data` payloads to avoid `any`.

## Accessibility and UX
- Ensure interactive elements inside nodes are keyboard reachable.
- Use semantic buttons for toolbar actions in nodes and edges.
- Preserve visible focus states.
- Keep hit areas large for touch interactions.
- Define keyboard shortcuts centrally (copy, paste, undo, redo, delete).

## SSR and export paths
- For server-rendered diagrams, confirm layout and sizing constraints before render.
- For client-side PNG/SVG export, use the official download-image example pattern.
- For server-side image generation, use the official server-side image creation pattern.

## Testing strategy
- Unit test connection validation and node/edge transformation helpers.
- Integration test add/move/connect/delete flows.
- Snapshot or visual regression test custom nodes/edges and theming variants.
- Add deterministic fixtures for large graph performance checks.

## Fast pre-merge checklist
- Container has width and height.
- Stylesheet is imported once.
- Provider usage is correct for all hooks.
- Node and edge type maps are stable.
- Multi-handle nodes use unique handle IDs.
- Dynamic handle updates call `useUpdateNodeInternals`.
- No unexpected re-render storms in profiling.
