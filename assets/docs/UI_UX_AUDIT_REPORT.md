# UI/UX Status Report

Date: 2026-03-28  
Scope: `ParaGraph/client`

This file tracks current UI/UX status and verification checkpoints for the active frontend.

## 1. Current Surfaces

- `/` Workflow page
- `/nodes` Nodes library/import page
- `/models` Models/provider page
- `/config` Configurations page

Core layout and global styling entry points:
- `src/index.css`
- `src/components/MainLayout.css`
- page-specific CSS files under `src/pages`

## 2. Standardized Foundations Present

Implemented and expected to remain in place:

- global spacing/radius/control-size design tokens in `src/index.css`
- global `:focus-visible` ring behavior
- reduced-motion fallback (`prefers-reduced-motion`)
- consistent topbar sizing and improved nav hit area
- shared dark-theme palette tokens used by page styles

## 3. Accessibility Baseline Expectations

- interactive controls must remain keyboard reachable and visibly focused
- modals must preserve dialog semantics (`role`, `aria-modal`, labels)
- Escape-close behavior should remain available for dismissible overlays
- icon/placeholder-driven inputs need explicit labels (`aria-label` or visible labels)

## 4. Areas to Re-Verify After UI Changes

These checks should be re-run whenever related screens are modified:

- focus order and visibility across all routes
- modal close behavior (button + Escape + backdrop policy)
- contrast for text and status indicators in hover/focus/disabled states
- responsive overflow for dense tables/cards/menus
- reduced-motion behavior for animated/transitional elements

## 5. Current Risk Profile

- Low risk: tokenized spacing/radius/control consistency regressions on new components
- Medium risk: keyboard accessibility regressions in newly added modals/menus
- Medium risk: page-specific CSS drift from shared token system

## 6. Recommended Verification Pass (Per UI PR)

1. `npm run build`
2. `npm run test:unit` for touched pages/services
3. `npm run test:e2e` when navigation/workflow interactions change
4. manual keyboard walkthrough on affected route(s)
