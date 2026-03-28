# UI Standards (Frontend)

Date: 2026-03-28  
Scope: `ParaGraph/client`

## Spacing Scale

- Base rhythm: 4px
- Tokens:
  - `--space-1`: 4px
  - `--space-2`: 8px
  - `--space-3`: 12px
  - `--space-4`: 16px
  - `--space-5`: 24px
- Page container spacing:
  - `--page-padding`: `clamp(16px, 2vw, 28px)`
- Top bar:
  - `--topbar-height`: `56px`

## Typography Scale

- Keep heading hierarchy semantic (`h1 > h2 > h3`).
- Prefer a compact app scale:
  - Page title: `clamp(1.35rem, 1.85vw, 1.75rem)`
  - Section heading: `~1rem`
  - Body: `0.84rem - 1rem`
  - Supporting/meta text: `0.72rem - 0.86rem`
- Global baseline line-height: `1.4`.

## Color System

- Core app/background:
  - `--color-bg-app`: `#020617`
  - `--color-bg-surface`: `#0f172a`
- Text:
  - `--color-text-primary`: `#eef6ff`
  - `--color-text-muted`: `#a9bfda`
- Borders/focus:
  - `--color-border-subtle`: `#334155`
  - `--focus-ring-color`: `rgba(96, 165, 250, 0.9)`
  - `--focus-ring-shadow`: `0 0 0 2px rgba(96, 165, 250, 0.45)`

## Global Baseline Rules

- Root font stack currently uses Inter-based fallback stack.
- `color-scheme` is dark.
- `:focus-visible` styles are required for `button`, `input`, `select`, `textarea`, and links.
- Reduced-motion handling must be preserved via `prefers-reduced-motion`.

## Component Usage Rules

- Controls:
  - Use tokenized heights:
    - `--control-height-sm`: 32px
    - `--control-height-md`: 36px
    - `--control-height-lg`: 40px
  - Use tokenized radii:
    - `--radius-sm`: 8px
    - `--radius-md`: 12px
    - `--radius-lg`: 14px
- Focus/interaction:
  - All interactive elements must expose visible `:focus-visible`.
  - Hover styles must never be the only affordance.
  - Disabled state must use both visual dimming and disabled semantics.
- Modals:
  - Must include `role="dialog"` and `aria-modal="true"`.
  - Must provide title/description association (`aria-labelledby` + `aria-describedby`).
  - Must support Escape close unless an in-progress blocking state is active.

## Do / Don't

- Do:
  - Reuse global tokens before adding one-off values.
  - Keep layout and interaction changes incremental and testable.
  - Add explicit labels/`aria-label` to icon-only or placeholder-driven inputs.
  - Respect `prefers-reduced-motion`.

- Don't:
  - Introduce new arbitrary spacing/radius/font values when existing tokens fit.
  - Rely on color alone to communicate status.
  - Remove keyboard accessibility to simplify pointer interactions.
  - Mix multiple near-identical variants of buttons/inputs without a clear purpose.
