# Troubleshooting Playbook

## TOC
- First-pass diagnosis
- Common warnings and fixes
- Runtime breakages
- Graph correctness checks
- Debugging workflow

## First-pass diagnosis
1. Confirm `@xyflow/react/dist/style.css` import exists.
2. Confirm flow container has explicit dimensions.
3. Confirm hooks are used under `<ReactFlowProvider />` when required.
4. Confirm node IDs, edge IDs, source IDs, target IDs, and handle IDs are valid.
5. Confirm dynamic handles call `useUpdateNodeInternals`.

## Common warnings and fixes

### "Seems like you have not used zustand provider as an ancestor."
- Cause: React Flow hooks used outside provider context.
- Fix: Wrap with `<ReactFlowProvider />` or move hook usage inside `<ReactFlow />` subtree.

### "The React Flow parent container needs a width and a height to render the graph."
- Cause: Parent element has no dimensions.
- Fix: Set explicit `width` and `height` (or layout that computes concrete size).

### "Node type not found. Using fallback type 'default'."
- Cause: Missing key in `nodeTypes`.
- Fix: Register all referenced node types and keep map stable.

### "Could not create edge for source/target handle id."
- Cause: Handle ID mismatch or missing handles.
- Fix: Ensure edge `sourceHandle`/`targetHandle` values match declared `Handle id`.

### "Only child nodes can use a parent extent."
- Cause: `extent: 'parent'` set on node without valid `parentId`.
- Fix: Set `parentId` correctly or remove `extent: 'parent'`.

### "Handle: No node id found."
- Cause: `<Handle />` used outside custom node renderer.
- Fix: Use `Handle` only inside a React Flow node component.

### "Can't create edge. An edge needs a source and a target."
- Cause: Invalid `Connection` object.
- Fix: Guard on connect and ensure both IDs are present.

## Runtime breakages

### Edges disappear after updates
- Check source/target node IDs still exist after node mutations.
- Ensure immutable updates do not drop IDs.
- Ensure reconnect logic uses valid edge IDs.

### Handles stop connecting after node data changes
- If handle count/position changes dynamically, call `useUpdateNodeInternals(nodeId)`.
- Avoid remount loops caused by unstable node keys/types.

### Custom node controls fail
- Ensure pointer-events and z-index are not blocked by wrappers.
- Ensure event handlers are memoized if bound deeply in many nodes.

## Graph correctness checks
- Every edge source and target references existing node IDs.
- Every custom handle edge references existing handle IDs.
- Node IDs remain stable across updates.
- No duplicate node IDs or edge IDs.
- Connection validator enforces required domain rules (cycles/schema).

## Debugging workflow
1. Reproduce with minimal graph fixture.
2. Compare implementation against nearest official example.
3. Turn off custom rendering and re-enable incrementally.
4. Add logging around `onConnect`, `onNodesChange`, `onEdgesChange`, reconnect handlers.
5. Validate store updates for accidental mutation.
6. Capture deterministic repro steps and root cause before patching.

## Canonical source
- Official common errors: https://reactflow.dev/learn/troubleshooting/common-errors
