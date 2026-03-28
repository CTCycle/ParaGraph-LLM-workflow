# General Rules

This file is mandatory context for every task.

## 1. Required Documentation Review

Read the minimum relevant docs in `assets/docs` before coding:

- `GENERAL_RULES.md` (always)
- `ARCHITECTURE.md` (system shape, API surface, data flow)
- `NODES_LIBRARY.md` (mandatory when adding/modifying nodes)
- `BACKGROUND_JOBS.md` (mandatory when touching async or polling flows)
- `GUIDELINES_PYTHON.md` (Python backend work)
- `GUIDELINES_TYPESCRIPT.md` (frontend/client work)
- `GUIDELINES_TESTS.md` (test changes or verification runs)
- `PACKAGING_AND_RUNTIME_MODES.md` (runtime/env/launcher behavior)
- `UI_STANDARDS.md` and `UI_UX_AUDIT_REPORT.md` (UI changes)
- `README_WRITING.md` (README changes)

## 2. Runtime and Command Rules

- Use PowerShell by default.
- For Python commands, use `runtimes/.venv` when present:
  - `.\runtimes\.venv\Scripts\python.exe ...`
- Use local runtime toolchain from this repository (`runtimes/`) for launcher-driven flows.
- Use `cmd /c` only for `.bat` scripts or CMD-specific syntax.
- After frontend code changes, run from `ParaGraph/client`:
  - `npm run build`

## 3. Documentation Policy

- If behavior, architecture, runtime setup, tests, or APIs change, update the relevant `assets/docs` files in the same task.
- Keep docs coherent with each other and with current code.
- Remove legacy references instead of adding contradictory notes.

## 4. Engineering Principles

- Prefer small, verifiable changes and deterministic behavior.
- Keep code readable, typed, and testable.
- Keep API handlers thin; push logic into services.
- Apply secure defaults: input validation, secret protection, and least privilege.

## 5. Frontend File Handling Rules

- Do not add backend-native file/folder dialogs for workflow nodes (no Tkinter/server-side OS pickers).
- In browser/local mode, selection and user-approved writes must be frontend-driven via browser file APIs.

## 6. Skills

When a reusable skill matches the task, use it. Apply only the relevant skill(s), not everything.

