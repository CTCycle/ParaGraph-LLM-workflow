# UI_STANDARDS

Last updated: 2026-04-24

## Typography

- Base font stack: `'Inter', 'Segoe UI', Roboto, Helvetica, Arial, sans-serif` (`src/index.css`).
- Monospace content (JSON, runtime output, text editor): `'Cascadia Mono', 'Consolas', 'Courier New', monospace`.
- Typical scale in implementation:
  - Page titles: ~`0.95rem` to `1rem` equivalent headings.
  - Body/form text: `0.8rem` to `0.9rem`.
  - Meta labels/captions: `0.7rem` to `0.78rem`.
- Default line-height: `1.4` body; tighter values used for dense metadata blocks.

## Layout and Spacing

- Global spacing tokens:
  - `--space-1: 4px`
  - `--space-2: 8px`
  - `--space-3: 12px`
  - `--space-4: 16px`
  - `--space-5: 24px`
- App shell uses a fixed top bar (`--topbar-height: 56px`) and full-height content area.
- Workflow page uses a two-column grid in desktop (`node library + canvas`) and collapses to single-column at smaller breakpoints.
- Border radius tokens:
  - `--radius-sm: 8px`
  - `--radius-md: 12px`
  - `--radius-lg: 14px`

## Color System

- Dark theme is the default and enforced (`color-scheme: dark`).
- Core tokens:
  - App background: `--color-bg-app: #020617`
  - Surface background: `--color-bg-surface: #0f172a`
  - Primary text: `--color-text-primary: #eef6ff`
  - Muted text: `--color-text-muted: #a9bfda`
  - Border subtle: `--color-border-subtle: #334155`
- Semantic feedback patterns:
  - Success: green-tinted border/glow states.
  - Error: red/pink-tinted border/glow + alert text.
  - Warning/attention: amber/yellow accents.

## Components and Patterns

- Navigation: top bar with active route underline and hover background.
- Primary application surfaces:
  - Workflow canvas + node tree + node cards.
  - Models explorer split columns (Ollama/Hugging Face).
  - Configuration forms with modal load/save flows.
  - Nodes catalog + template cards + import modal.
- Interaction states explicitly styled:
  - hover, active, selected, disabled, focus-visible.
  - workflow node runtime states: running, active, selected, skipped, pinged.
- Form controls use inherited typography and consistent dark field styling.

## Page Structure

Main route map:

- `/` -> Workflow editor
- `/nodes` -> Node library + templates
- `/models` -> Model catalogs
- `/config` -> Runtime/access configuration

Shared composition:

- `MainLayout` wraps page routes.
- Each page uses a consistent header + content panel strategy.
- Workflow page is the deepest interaction surface and defines the main operational template.

## User Experience Rules

- Prefer clear system status communication (`status text`, inline notices, banners, modals).
- Keep action buttons close to affected content (toolbar actions, row actions, node-local actions).
- Provide explicit loading and empty states in list/canvas contexts.
- Surface recoverable errors with actionable copy and retry affordances.

## Responsiveness

Implemented breakpoints:

- `max-width: 1120px`:
  - workflow toolbar stacks vertically.
  - workflow grid collapses to single column.
- `max-width: 760px`:
  - topbar becomes horizontally scrollable.
  - workflow action buttons become a compact grid.
  - bottom editor panel is hidden to preserve viewport space.

## Accessibility

- Global `:focus-visible` outlines + shadow ring are implemented for keyboard navigation.
- Reduced motion is supported via `prefers-reduced-motion` media query.
- Navigation includes `aria-label` on primary nav and many actionable controls.
- Modal/dialog surfaces use roles and label/description IDs where implemented.
- Color usage should preserve contrast against dark backgrounds; avoid low-contrast muted text for critical states.

## Design Principles

- Preserve consistency across pages through shared tokens and common interaction language.
- Prioritize readability and operational clarity over decorative variance.
- Use dense layouts only where task efficiency requires it (workflow canvas/editor contexts).
- Keep visual complexity intentional: gradients and glow effects should communicate hierarchy/state, not decoration alone.
