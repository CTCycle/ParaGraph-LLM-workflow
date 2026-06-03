# TypeScript
Last updated: 2026-06-02

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

## Documentation Expectation
- Update the corresponding UI, runtime, or user documentation when frontend changes alter routes, workflows, interaction patterns, or visible runtime behavior.
