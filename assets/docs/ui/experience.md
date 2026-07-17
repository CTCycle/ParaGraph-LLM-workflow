# Experience
Last updated: 2026-07-17

## User Experience Rules
- Prefer clear system status communication through inline notices, banners, modals, and status text.
- Keep action buttons close to the content they affect.
- Provide explicit loading and empty states in list and canvas contexts.
- Surface recoverable errors with actionable copy and retry affordances.

## Responsiveness
- At `max-width: 1120px`:
  - The workflow toolbar stacks vertically.
  - The workflow grid collapses to a single column.
- At `max-width: 760px`:
  - The top bar becomes horizontally scrollable.
  - Workflow action buttons switch to a compact grid.
  - The bottom editor panel is hidden to preserve viewport space.

## Accessibility
- Global `:focus-visible` outlines and shadow rings are implemented for keyboard navigation.
- Reduced motion is supported through `prefers-reduced-motion`.
- Navigation uses `aria-label` on the primary nav and on many actionable controls.
- Modal and dialog surfaces use roles plus label and description IDs where implemented.
- Critical states must preserve contrast against dark backgrounds.

## Design Principles
- Preserve consistency across pages through shared tokens and a common interaction language.
- Prioritize readability and operational clarity over decorative variance.
- Use dense layouts only where task efficiency requires them, especially in workflow editor contexts.
- Keep gradients and glow effects intentional so they communicate hierarchy or state rather than decoration alone.
## Workflow execution feedback

The workflow editor keeps compiler diagnostics visible after compilation and
labels warnings separately from execution-blocking errors. Runtime state uses
distinct text labels for running, retrying, timed out, skipped, blocked,
cancelled, paused, and resumed states. Cancellation is submitted against the
current durable run and the UI continues polling persisted state after reload.

The editor's node data types are synchronized with the backend catalog contract;
unsupported or removed node versions are not silently substituted. A real
backend/frontend Playwright contract check covers catalog loading and prompt to
text-output compilation. Full provider-backed execution remains dependent on a
configured local provider.
