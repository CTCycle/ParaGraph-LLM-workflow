# TypeScript
Last updated: 2026-08-20

## Baseline
- Use strict TypeScript typing for application logic and service boundaries.
- Prefer explicit interfaces and types for API payloads and domain state.
- Keep API calls centralized under `client/src/app/services`.

## React And State
- Use function components with hooks.
- Keep route-level pages orchestrating behavior and move reusable logic into hooks, services, or shared components.
- Use memoization such as `useMemo` and `useCallback` only when there is a clear behavioral or performance reason.
- Keep route pages in `client/src/pages` and shared UI in `client/src/components`.

## UI And Styling
- Reuse design tokens and CSS variables from `src/index.css`.
- Keep component-specific or page-specific styles colocated.
- Preserve accessibility primitives such as `focus-visible`, semantic labels, and reduced-motion handling.

## Frontend Structure
- Treat `client/src/workflow` as the editor-local domain area for schema, hooks, and workflow-specific presentation.
- Keep shared cross-page services typed and isolated from page rendering logic.
- Prefer narrow, reusable components over page-local duplication when interaction patterns repeat.
- Keep workflow editor persistence and pure graph I/O helpers under
  `client/src/workflow`; route pages should coordinate them rather than own all
  serialization and validation logic.
- Keep API response types in the typed API service boundary and editor-only
  state types in `client/src/workflow/schema`. Do not make a page-local editor
  shape the implicit API contract.
- Continue decomposing `WorkflowPage.tsx` by responsibility: persistence and
  I/O, execution control, graph interaction, and presentation components.

## Documentation Expectation
- Update the corresponding UI, runtime, or user documentation when frontend changes alter routes, workflows, interaction patterns, or visible runtime behavior.
