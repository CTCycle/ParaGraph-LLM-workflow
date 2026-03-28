# TypeScript Guidelines (ParaGraph Client)

Stack baseline:
- React 18
- TypeScript 5
- Vite 5
- React Router 6
- `@xyflow/react` for workflow graph UI

## 1. Types and Contracts

- Keep strict typing enabled.
- Prefer `unknown` over `any` for untrusted inputs.
- Type all exported functions and component props.
- Keep shared workflow/API contracts in `src/workflow/schema/types.ts`.

## 2. Project Structure

- Route/pages: `src/pages`
- Shared UI/layout: `src/components`
- API layer: `src/app/services`
- Workflow schema/hooks: `src/workflow`

Do not move API logic into page components.

## 3. API Rules

- Use `requestJson` from `src/app/services/api.ts` for HTTP calls.
- Keep `VITE_API_BASE_URL` relative (default `/api`).
- Surface backend errors with actionable UI messages.
- Validate websocket/event payload assumptions before use.

## 4. Workflow UI Rules

- Node forms must stay manifest-driven (from `/nodes/catalog` contracts).
- Keep connection validation deterministic and mirrored with backend constraints.
- Use stable node identifiers and avoid random-only IDs that hinder debugging.
- Output rendering should be based on execution results/events, not speculative local state.

## 5. Accessibility and UX

- Keep keyboard access (`focus-visible`, dialog semantics, Escape handling where applicable).
- Avoid color-only status communication.
- Keep loading/progress states tied to backend status (`pending/running/completed/failed/cancelled`).

## 6. Quality Gates

- Required after frontend changes:
  - `npm run build`
- Prefer also running:
  - `npm run test:unit`
  - `npm run test:e2e` for affected flows
