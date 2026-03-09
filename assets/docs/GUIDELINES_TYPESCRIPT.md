## TypeScript Guidelines (ParaGraph Client)

Project stack baseline:
- React 18 + TypeScript 5
- Vite 5
- React Router 6
- React Flow (`@xyflow/react`) for workflow canvas

## 1. Type Safety Rules

- Keep `strict` mode enabled.
- Prefer `unknown` over `any` for untrusted values.
- Type all exported functions, component props, and service-layer responses.
- Keep shared backend contracts in `src/types.ts`.

## 2. React and State Management

- Keep page orchestration in `src/pages/` and reusable UI in `src/components/`.
- Keep API I/O in `src/services/`.
- Use `useMemo`/`useCallback` only when they reduce real rerender cost.
- Persist only stable UI state (for example workflow graph state in localStorage).

## 3. API and Networking

- Route HTTP calls through service modules (for example `src/services/workflow.ts`).
- Reuse the shared `requestJson` pattern for status handling and error extraction.
- Treat backend responses as untrusted and fail with actionable error messages.
- Keep URLs relative to `VITE_API_BASE_URL` (default `/api`).

## 4. Workflow Builder UI Rules

- Node parameters should stay catalog-driven (`WorkflowNodeDefinition.parameters`) so backend and frontend stay aligned.
- Validate connection rules both client-side and server-side.
- Keep node ids deterministic enough for debugging (prefix by node type).
- Update output nodes only from job result payloads, not speculative client state.

## 5. Error Handling and UX

- Do not swallow async errors; surface them in page status/alert UI.
- Keep progress reporting tied to backend polling state (`pending`, `running`, terminal states).
- Keep cancel/poll logic in service helpers, not duplicated across components.

## 6. Quality Gates

- Keep `npm run build` passing (`tsc && vite build`).
- Keep `npm run lint` passing when lint config is active.
- Prefer small modules and explicit names over broad abstractions.

## 7. Testing Guidance (Current State)

- The repository currently emphasizes backend pytest coverage.
- For frontend changes, prioritize service-layer testability and deterministic behavior.
- Add frontend automated tests when stable UI flows are introduced.
