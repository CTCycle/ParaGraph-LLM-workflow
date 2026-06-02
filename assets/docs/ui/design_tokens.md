# Design Tokens
Last updated: 2026-06-02

## Typography
- Base font stack: `'Inter', 'Segoe UI', Roboto, Helvetica, Arial, sans-serif` from `src/index.css`.
- Monospace content such as JSON, runtime output, and text editors uses `'Cascadia Mono', 'Consolas', 'Courier New', monospace`.
- Typical scale in the current implementation:
  - Page titles: about `0.95rem` to `1rem`
  - Body and form text: about `0.8rem` to `0.9rem`
  - Meta labels and captions: about `0.7rem` to `0.78rem`
- Default body line-height is `1.4`, with tighter values used for dense metadata blocks.

## Spacing
- `--space-1: 4px`
- `--space-2: 8px`
- `--space-3: 12px`
- `--space-4: 16px`
- `--space-5: 24px`

## Layout Tokens
- `--topbar-height: 56px`
- `--radius-sm: 8px`
- `--radius-md: 12px`
- `--radius-lg: 14px`

## Color System
- Dark theme is the default and enforced with `color-scheme: dark`.
- Core tokens include:
  - `--color-bg-app: #020617`
  - `--color-bg-surface: #0f172a`
  - `--color-text-primary: #eef6ff`
  - `--color-text-muted: #a9bfda`
  - `--color-border-subtle: #334155`

## Semantic Feedback
- Success uses green-tinted borders and glow states.
- Error uses red or pink borders, glow states, and alert text.
- Warning and attention states use amber or yellow accents.
