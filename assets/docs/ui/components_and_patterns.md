# Components And Patterns
Last updated: 2026-08-26

## Navigation
- The app uses a top bar with active-route underline and hover background treatment.

## Primary Surfaces
- Workflow canvas, node tree, and node cards.
- Models explorer with split columns for Ollama and Hugging Face.
- Configuration forms with modal save and load flows.
- Nodes catalog, template cards, and custom import modal.

## Interaction States
- Explicit styles exist for hover, active, selected, disabled, and `focus-visible`.
- Workflow node runtime states include running, active, selected, skipped, and pinged.
- Form controls use inherited typography and consistent dark field styling.

## Route Structure
- `/` maps to the workflow editor.
- `/nodes` maps to the node library and templates.
- `/models` maps to model catalogs.
- `/config` maps to runtime and access configuration.
- `/database-schema/:nodeId` is the workflow database-node schema inspection
  surface and returns to `/` through the route state supplied by the editor.

## Shared Composition
- `MainLayout` wraps page routes.
- Each page follows a consistent header and content-panel structure.
- The workflow page is the deepest interaction surface and acts as the main operational template for the rest of the app.
- `WorkflowPage.tsx` remains the editor coordinator. Workflow persistence is
  isolated in `workflow/hooks/workflowPersistence.ts`; additional extraction
  should keep graph behavior, execution controls, and presentation components
  independently testable.

## Contextual Guidance
- `guidance/` contains the shared `GuidanceProvider`, versioned persistence, `FeatureTip`, `HelpPopover`, `GuidedTour`, `GuidanceDialog`, `TipsAndTricksDialog`, and `TutorialMedia` primitives.
- Guidance state is local to the browser under `paragraph.guidance.state.v1` and must remain separate from workflow graph persistence.
- First-use callouts are limited to the blank workflow and provider configuration surfaces. The top-bar Help entry provides manual Tips & Tricks and tour replay without adding help controls to every component.
- Dialogs and tours use portals, labelled dialog semantics, bounded focus handling, Escape dismissal, and focus restoration. Popovers are non-modal and reposition against their trigger so they remain inside the viewport.
- Tutorial media is decorative CSS animation with a replay control. Reduced-motion users receive a static equivalent, and no guidance animation runs continuously outside the active tour.
