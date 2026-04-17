# General Rules
Last updated: 2026-04-17

This is the mandatory entry document for every task.

## 1. Reading Order and Precedence

1. Read this file (`GENERAL_RULES.md`) first.
2. Read only the additional docs needed for the task scope.
3. If two docs conflict:
   - Task-specific requirements (user request + this task context) win.
   - `GENERAL_RULES.md` defines shared baseline behavior.
   - Specialized docs (Python/TypeScript/UI/tests/runtime) refine implementation details.

## 2. Canonical Docs Index (`assets/docs`)

| Document | Purpose | Read When |
| --- | --- | --- |
| `GENERAL_RULES.md` | Global workflow and documentation policy. | Always. |
| `ARCHITECTURE.md` | System structure, active API surface, runtime flow, persistence boundaries. | Any backend/frontend feature touching contracts or flow wiring. |
| `NODES_LIBRARY.md` | Source-of-truth node inventory and node contract expectations. | Adding/modifying nodes, ports/controllers, categories, or node behavior. |
| `BACKGROUND_JOBS.md` | Job manager, polling, cancellation, async execution patterns. | Touching long-running operations, job lifecycle, progress streams, or cancellation. |
| `GUIDELINES_PYTHON.md` | Backend coding standards, layering, FastAPI practices, typing and runtime expectations. | Editing `ParaGraph/server` or backend tests. |
| `GUIDELINES_TYPESCRIPT.md` | Client architecture, typing, API-layer usage, workflow UI constraints. | Editing `ParaGraph/client`. |
| `GUIDELINES_TESTS.md` | Test layout, fixtures, commands, quality gates. | Adding/updating/running tests. |
| `PACKAGING_AND_RUNTIME_MODES.md` | Runtime/deployment modes, path behavior, packaging constraints. | Changes affecting launch/config/runtime behavior or packaging. |
| `UI_STANDARDS.md` | Design tokens, spacing/typography/color/focus/accessibility standards. | Any UI/CSS/component interaction change. |
| `UI_UX_AUDIT_REPORT.md` | Known UX gaps and remediation priorities. | UI changes where consistency with existing audit guidance matters. |
| `USER_MANUAL.md` | End-user operation guide: user journeys, commands, usage patterns, and troubleshooting. | User onboarding, operations docs, and usage clarifications. |

## 3. Runtime and Command Rules

- Use PowerShell by default.
- Use repository runtime tools and environments.
- For Python commands, use `runtimes/.venv` when present:
  - `./runtimes/.venv/Scripts/python.exe ...`
- Use `cmd /c` only for `.bat` scripts or CMD-specific behavior.

## 4. Verification Gates

- After frontend code changes (from `ParaGraph/client`):
  - `npm run build`
- For backend changes:
  - Run relevant `pytest` suites (at minimum affected unit tests).
- For cross-layer changes:
  - Validate both frontend build and backend tests.

## 5. Documentation Update Policy

Update docs in the same task when behavior/contracts change.

Required consistency checks:
- Node/catalog/runtime changes -> update `NODES_LIBRARY.md`.
- Architecture/API-flow changes -> update `ARCHITECTURE.md`.
- Runtime/deployment/config changes -> update `PACKAGING_AND_RUNTIME_MODES.md`.
- UI behavior/interaction changes -> align with `UI_STANDARDS.md` and review `UI_UX_AUDIT_REPORT.md`.
- Test strategy/commands changed -> update `GUIDELINES_TESTS.md`.

## 6. Engineering Principles

- Prefer small, verifiable increments.
- Keep behavior deterministic and contracts explicit.
- Keep API handlers thin and move logic into services.
- Preserve backward compatibility where required; migrate legacy contracts explicitly.
- Use secure defaults: validation, path safety, least privilege.
- Do not introduce global variables (`global ...`, mutable module-level shared state, or `globalThis`-based shared mutable data). Use explicit dependency injection, local state, or scoped context providers instead.
- Enforce this rule across code and docs under `assets/docs`; when adding or updating coding guidance, keep this prohibition explicit.

## 7. Frontend File Handling Rules

- Do not add backend-native OS pickers for workflow nodes.
- In browser/local mode, selection and user-approved writes must be frontend-driven via browser file APIs.

## 8. Skills

Use matching skills when relevant, but only those needed for the task.
