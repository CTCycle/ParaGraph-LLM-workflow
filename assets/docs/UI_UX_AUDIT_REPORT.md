# UI/UX Audit Report (Pre-Implementation)

Date: 2026-03-27  
Scope: `ParaGraph/client` frontend (React 18 + TypeScript + CSS modules-by-page)

## Discovery Summary

- Routing and primary screens:
  - `/` -> Workflow page ([`src/pages/WorkflowPage.tsx`](../../ParaGraph/client/src/pages/WorkflowPage.tsx))
  - `/nodes` -> Nodes library ([`src/pages/NodesPage.tsx`](../../ParaGraph/client/src/pages/NodesPage.tsx))
  - `/models` -> Models explorer ([`src/pages/ModelsPage.tsx`](../../ParaGraph/client/src/pages/ModelsPage.tsx))
  - `/config` -> Runtime/access configuration ([`src/pages/ConfigurationsPage.tsx`](../../ParaGraph/client/src/pages/ConfigurationsPage.tsx))
- Styling approach:
  - Global CSS baseline: [`src/index.css`](../../ParaGraph/client/src/index.css)
  - Layout shell CSS: [`src/components/MainLayout.css`](../../ParaGraph/client/src/components/MainLayout.css)
  - Page-scoped CSS per route.
- Theme/token status:
  - No centralized spacing/typography/color token system.
  - Large volume of one-off values (especially in `WorkflowPage.css`).
- Repeated style logic:
  - Similar button/input/card styles duplicated across `NodesPage.css`, `ModelsPage.css`, `ConfigurationsPage.css`.

## Findings By Component

### Main Layout / Global

1. **High** - Keyboard focus visibility is effectively missing across most interactive controls.  
   - References:
     - [`src/index.css`](../../ParaGraph/client/src/index.css) (global control base, no focus styles)
     - [`src/components/MainLayout.css`](../../ParaGraph/client/src/components/MainLayout.css:35)
     - [`src/pages/ModelsPage.css`](../../ParaGraph/client/src/pages/ModelsPage.css:66)
     - [`src/pages/NodesPage.css`](../../ParaGraph/client/src/pages/NodesPage.css:91)
     - [`src/pages/ConfigurationsPage.css`](../../ParaGraph/client/src/pages/ConfigurationsPage.css:73)
   - Root cause: Hover states are implemented, but `:focus-visible` system is not.
   - Minimal fix: Add global `:focus-visible` ring token + opt-in scoped overrides where needed.

2. **High** - Top navigation links have small hit area and weak interaction affordance.  
   - References:
     - [`src/components/MainLayout.css`](../../ParaGraph/client/src/components/MainLayout.css:10)
     - [`src/components/MainLayout.css`](../../ParaGraph/client/src/components/MainLayout.css:35)
   - Root cause: `topbar` height and zero link padding/border radius.
   - Minimal fix: Increase nav item padding and radius while preserving existing visual style.

3. **Medium** - No reduced-motion handling despite active animation usage.  
   - References:
     - [`src/pages/WorkflowPage.css`](../../ParaGraph/client/src/pages/WorkflowPage.css:515)
   - Root cause: Animation/transitions defined without `prefers-reduced-motion` fallback.
   - Minimal fix: Add global reduced-motion media query to disable/reduce motion.

### Configurations Screen

4. **High** - Vertical sizing is inconsistent with topbar height, causing layout drift potential.  
   - References:
     - [`src/components/MainLayout.css`](../../ParaGraph/client/src/components/MainLayout.css:10)
     - [`src/pages/ConfigurationsPage.css`](../../ParaGraph/client/src/pages/ConfigurationsPage.css:2)
   - Root cause: Config page subtracts `56px` while topbar is `48px`.
   - Minimal fix: Normalize against a shared topbar token or use container-height-based layout.

5. **Medium** - Control dimensions and spacing differ from peer pages (buttons 29px, varied paddings/radii).  
   - References:
     - [`src/pages/ConfigurationsPage.css`](../../ParaGraph/client/src/pages/ConfigurationsPage.css:73)
     - [`src/pages/ConfigurationsPage.css`](../../ParaGraph/client/src/pages/ConfigurationsPage.css:113)
     - [`src/pages/ConfigurationsPage.css`](../../ParaGraph/client/src/pages/ConfigurationsPage.css:203)
   - Root cause: Page-local one-off sizing.
   - Minimal fix: Standardize with shared control-height/padding/radius tokens.

### Nodes Screen

6. **Medium** - Spacing rhythm is inconsistent (mixed 9/10/11/13/15px values) and not tokenized.  
   - References:
     - [`src/pages/NodesPage.css`](../../ParaGraph/client/src/pages/NodesPage.css:63)
     - [`src/pages/NodesPage.css`](../../ParaGraph/client/src/pages/NodesPage.css:110)
     - [`src/pages/NodesPage.css`](../../ParaGraph/client/src/pages/NodesPage.css:184)
     - [`src/pages/NodesPage.css`](../../ParaGraph/client/src/pages/NodesPage.css:216)
   - Root cause: Local ad-hoc spacing.
   - Minimal fix: Align to 4/8-based spacing scale via tokens.

7. **High** - Modal keyboard accessibility is incomplete (no Escape handling).  
   - References:
     - [`src/pages/NodesPage.tsx`](../../ParaGraph/client/src/pages/NodesPage.tsx:353)
     - [`src/pages/NodesPage.tsx`](../../ParaGraph/client/src/pages/NodesPage.tsx:363)
   - Root cause: Modal close is pointer/button driven only.
   - Minimal fix: Add Escape close behavior and robust dialog labeling.

### Models Screen

8. **High** - Form controls rely on placeholder/icon in several places without explicit accessible labels.  
   - References:
     - [`src/pages/ModelsPage.tsx`](../../ParaGraph/client/src/pages/ModelsPage.tsx:584)
     - [`src/pages/ModelsPage.tsx`](../../ParaGraph/client/src/pages/ModelsPage.tsx:593)
     - [`src/pages/ModelsPage.tsx`](../../ParaGraph/client/src/pages/ModelsPage.tsx:664)
     - [`src/pages/ModelsPage.tsx`](../../ParaGraph/client/src/pages/ModelsPage.tsx:679)
   - Root cause: Inputs/selects are visually contextual but semantically under-labeled.
   - Minimal fix: Add `aria-label` (or visible labels) for all search/filter controls.

9. **Medium** - Control styling remains duplicated and mildly divergent from Nodes/Config pages.  
   - References:
     - [`src/pages/ModelsPage.css`](../../ParaGraph/client/src/pages/ModelsPage.css:66)
     - [`src/pages/ModelsPage.css`](../../ParaGraph/client/src/pages/ModelsPage.css:79)
     - [`src/pages/ModelsPage.css`](../../ParaGraph/client/src/pages/ModelsPage.css:126)
   - Root cause: Re-implemented surface/button/input styling by page.
   - Minimal fix: Consolidate repeated control styles on shared tokenized values.

### Workflow Screen

10. **High** - Dense toolbar/tree controls use very small typography and compact targets, hurting readability and keyboard usability.  
    - References:
      - [`src/pages/WorkflowPage.css`](../../ParaGraph/client/src/pages/WorkflowPage.css:35)
      - [`src/pages/WorkflowPage.css`](../../ParaGraph/client/src/pages/WorkflowPage.css:81)
      - [`src/pages/WorkflowPage.css`](../../ParaGraph/client/src/pages/WorkflowPage.css:209)
    - Root cause: Multiple sub-0.8rem font sizes and low-height controls.
    - Minimal fix: Raise minimum readable type and control-height baseline while preserving layout.

11. **High** - Modal and context menu interactions are partially pointer-centric; keyboard handling is limited.  
    - References:
      - [`src/pages/WorkflowPage.tsx`](../../ParaGraph/client/src/pages/WorkflowPage.tsx:3125)
      - [`src/pages/WorkflowPage.tsx`](../../ParaGraph/client/src/pages/WorkflowPage.tsx:3321)
    - Root cause: No Escape close for error modal/context menu and no contextual keyboard fallback.
    - Minimal fix: Add global Escape handlers for transient overlays and preserve current click behavior.

12. **Medium** - Extensive one-off color/spacing values reduce maintainability and consistency.  
    - References:
      - [`src/pages/WorkflowPage.css`](../../ParaGraph/client/src/pages/WorkflowPage.css) (broadly, multiple unique values)
    - Root cause: Evolved page-specific tuning without token consolidation.
    - Minimal fix: Introduce token aliases for shared spacing/radii/control metrics first; keep visual palette intact.

## Needs Verification (Visual/Runtime)

- **Contrast pass/fail by WCAG AA** across all text/surface combinations requires runtime visual verification and measured contrast in rendered UI states (hover/focus/disabled/selected).
- **Responsive overflow/clipping** for context menus and long model metadata at extreme viewport widths requires browser verification.
- **Focus order and trap behavior** inside modals requires interactive keyboard walkthrough validation.

## Quick Wins (Low Risk)

- Add global focus-visible and reduced-motion behavior.
- Standardize control sizing/radius/spacing tokens.
- Normalize topbar nav hit area.
- Add missing `aria-label` to filter/search controls.
- Add Escape-close behavior to modals.

## Structural Improvements (Still Scoped)

- Consolidate repeated page-level control styles into a small shared layer (token-backed).
- Gradually replace one-off spacing values on high-traffic screens (Models/Nodes/Config, then Workflow controls).

## Implemented Fixes (This Pass)

- Added global design tokens and baseline interaction polish in [`src/index.css`](../../ParaGraph/client/src/index.css):
  - spacing/radius/control-size tokens
  - global `:focus-visible` ring
  - consistent disabled affordance
  - reduced-motion fallback
- Improved shell navigation sizing/clarity in [`src/components/MainLayout.css`](../../ParaGraph/client/src/components/MainLayout.css).
- Standardized page-level spacing/control consistency in:
  - [`src/pages/ConfigurationsPage.css`](../../ParaGraph/client/src/pages/ConfigurationsPage.css)
  - [`src/pages/NodesPage.css`](../../ParaGraph/client/src/pages/NodesPage.css)
  - [`src/pages/ModelsPage.css`](../../ParaGraph/client/src/pages/ModelsPage.css)
  - targeted control-density cleanup in [`src/pages/WorkflowPage.css`](../../ParaGraph/client/src/pages/WorkflowPage.css)
- Accessibility updates:
  - explicit labels for models filters/searches in [`src/pages/ModelsPage.tsx`](../../ParaGraph/client/src/pages/ModelsPage.tsx)
  - search labeling + modal keyboard/dismiss semantics in [`src/pages/NodesPage.tsx`](../../ParaGraph/client/src/pages/NodesPage.tsx)
  - dialog backdrop/escape handling in [`src/components/ModalDialog.tsx`](../../ParaGraph/client/src/components/ModalDialog.tsx) and usage wiring in [`src/pages/ConfigurationsPage.tsx`](../../ParaGraph/client/src/pages/ConfigurationsPage.tsx)
  - error modal dismiss and menu semantics in [`src/pages/WorkflowPage.tsx`](../../ParaGraph/client/src/pages/WorkflowPage.tsx)
