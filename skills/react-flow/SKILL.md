---
name: react-flow
description: Comprehensive React Flow engineering guide for building, debugging, migrating, and optimizing node-based UIs with @xyflow/react. Use when implementing flows, custom nodes or edges, connection logic, layouting, whiteboard interactions, TypeScript typing, SSR or image generation, performance tuning, or when resolving React Flow warnings and runtime issues.
---

# React Flow

Use this skill to execute React Flow work with a fast, repeatable workflow and official docs-first guidance.

## Workflow

1. Classify the task before coding.
- Use `references/troubleshooting-playbook.md` first for warnings, runtime errors, or broken interactions.
- Use `references/examples-index.md` first for "build X feature like Y" requests.
- Use `references/official-docs-index.md` first for API design, migration, and version-sensitive behavior.
- Use `references/best-practices.md` first for architecture and performance decisions.
- Use `references/ecosystem-and-tools.md` first when layout/routing/collaboration/export tooling is needed.

2. Establish a correct baseline in code.
- Install `@xyflow/react`.
- Import `@xyflow/react/dist/style.css`.
- Ensure the React Flow parent container has explicit width and height.
- Prefer controlled flows (`nodes`, `edges`, `onNodesChange`, `onEdgesChange`) for production.

3. Choose implementation strategy explicitly.
- Use custom nodes and edges for real applications, not only built-in types.
- Keep `nodeTypes`, `edgeTypes`, callbacks, and object props memoized or module-scoped.
- Use `ReactFlowProvider` when accessing flow state outside `<ReactFlow />` or when rendering multiple flows.
- Use `useReactFlow()` instance methods for imperative actions (viewport, updates, queries).

4. Validate before finishing.
- Verify pan/zoom/select/connect/delete behavior.
- Verify reconnect, handle IDs, and edge source/target integrity.
- Verify performance under drag + zoom with realistic graph size.
- Verify keyboard accessibility and focus behavior for custom controls.
- Verify SSR/static export requirements when rendering off-client.

## Task Playbooks

### Build or Extend a Flow Feature
1. Start from an official example in `references/examples-index.md`.
2. Keep initial behavior close to the example, then layer custom logic.
3. Add strict node and edge typing early when using TypeScript.
4. Add tests for connection validity and node data propagation.

### Diagnose a Broken Flow
1. Match symptom to known warnings in `references/troubleshooting-playbook.md`.
2. Verify container size, CSS import, provider usage, node/edge IDs, and handle IDs.
3. Inspect dynamic handle changes; call `useUpdateNodeInternals()` when needed.
4. Re-check memoization and state subscriptions for hidden re-render loops.

### Migrate Versions
1. Identify current package and target package.
2. Use migration notes from `references/official-docs-index.md`.
3. Apply API renames in one pass, then fix typing changes.
4. Re-test dimensions, reconnect behavior, and custom node/edge wrappers.

## Quality Bar

Treat these as required unless the user asks otherwise:

- Prefer official React Flow docs and examples as primary references.
- Preserve controlled data flow and avoid hidden state mutations.
- Keep render paths stable with memoization and narrow store selectors.
- Avoid untyped `any` node/edge payloads in TypeScript codebases.
- Capture root cause and deterministic repro steps when debugging.

## References

- `references/official-docs-index.md`: Official docs map, API coverage, migrations, and "what to read when".
- `references/examples-index.md`: Example catalog grouped by feature area, including MIT and Pro examples.
- `references/best-practices.md`: Architecture, performance, typing, accessibility, testing, and styling guidelines.
- `references/troubleshooting-playbook.md`: Warning-to-fix mapping and fast diagnosis checklist.
- `references/ecosystem-and-tools.md`: Layout, routing, export, collaboration, UI kits, and community resources.
