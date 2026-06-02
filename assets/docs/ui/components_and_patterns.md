# Components And Patterns
Last updated: 2026-06-02

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

## Shared Composition
- `MainLayout` wraps page routes.
- Each page follows a consistent header and content-panel structure.
- The workflow page is the deepest interaction surface and acts as the main operational template for the rest of the app.
