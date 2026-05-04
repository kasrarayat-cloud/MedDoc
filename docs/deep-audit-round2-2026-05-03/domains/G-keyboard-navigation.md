# Domain G — Keyboard Navigation

**Run:** 2026-05-03 20:59 UTC

## Summary

| # | Test | Status | Finding |
|---|---|---|---|
| G1 | Tab order on dashboard | ✓ partial | first 8 tab stops captured; nav links + main content reachable |
| G2 | Esc closes Cmd-K palette | ✓ | true |
| G3 | Cmd-K opens with shortcuts visible | ✓ | shortcuts: ⌘K, N (new), D (dashboard), S (settings), ↑↓ (navigate), ↵ (select), esc (close) — all documented in palette UI |
| G4 | Focus trap in modals | DEFERRED | requires opening Sign & Send modal + verifying Tab cycles within |
| G5 | Focus restoration after modal close | DEFERRED | same |
| G6 | Skip-to-content link | NOT FOUND | absent — see G-001 |
| G7 | Enter submits login form | ✓ | submitted + landed on /dashboard |

## Findings

### G-001 — No skip-to-content link (P3 a11y)

A11y best practice: every page should have a `<a href="#main">Skip to
main content</a>` as the first focusable element, allowing
keyboard / screen-reader users to bypass the nav on every page.

QuillMD app pages don't have this. WCAG 2.4.1 (Bypass Blocks) is the
relevant criterion.

**Recommended fix:** add to the auth shell + app shell layouts:
```tsx
<a href="#main" className="sr-only focus:not-sr-only">Skip to main content</a>
```
Plus an `<main id="main">` wrapper.

**Effort:** ~10 min
**Risk if NOT fixed:** mid-impact for keyboard-only users.

### G-002 — Cmd-K palette is well-documented (POSITIVE)

The palette displays its keyboard shortcuts inline (⌘K to open,
arrow keys to navigate, ↵ to select, esc to close) AND lists
single-key navigation: N (new visit), D (dashboard), S (settings).
This is genuinely good UX — discoverable shortcuts.

## What was NOT covered

- Focus trap in modals + restoration (G4/G5) — requires more
  complex Tab-cycling tests
- All form-tab orders (G1) — only sampled the dashboard
