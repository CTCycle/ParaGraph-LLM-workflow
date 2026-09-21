# Contextual guidance validation

Validated 2026-08-26 against the local frontend and mock-backed application.

## Evidence

- `guidance-01-empty-workflow.png` — blank workflow onboarding callout.
- `guidance-02-editor-tour-library.png` — editor tour step 1 with the node library highlighted.
- `guidance-03-editor-tour-connect.png` — editor tour step 3 with the finite connection demonstration.
- `guidance-04-chat-help-popover.png` — disconnected Chat node and manually opened Conversation help popover.
- `guidance-05-tips-tricks.png` — reusable Help dialog and Tips & Tricks cards.
- `guidance-06-config-tip-1024.png` — configuration tip at the 1024px desktop validation width.

## Checks

- Frontend and backend ran locally; the mock backend supported the browser workflow checks.
- Blank workflow onboarding opened only on the empty canvas. `Show me` opened the node library and started the four-step tour.
- Tour progress, Back, Next, Finish, Skip, close, cross-route replay, and missing-target fallback were exercised by unit/component tests and browser checks.
- Completing the editor tour and dismissing the configuration tip remained suppressed after reload.
- Help opened from Workflow, Nodes, Models, and Configurations in Playwright coverage. Tips & Tricks remained manual.
- Chat help did not open automatically; the disconnected inline hint and Escape dismissal were verified.
- 1280px/default and 1024px viewports were checked. Guidance cards stayed inside the viewport and the document did not overflow horizontally.
- Keyboard focus was checked for initial dialog focus, Tab cycling, Escape dismissal, and focus restoration to the launcher.
- Reduced-motion coverage used Playwright `prefers-reduced-motion: reduce`; the connector animation resolved to `none` and the static equivalent remained available.

## Deliberate omissions

No automatic guidance was added to Models, Nodes, Database Schema, or ordinary navigation controls because their labels, descriptions, filters, and empty states were already clear. No recurring route modals, per-control help icons, GIF/video assets, or backend persistence were added.
