---
id: A10-P3-002
severity: P3
domain: design tokens / brand consistency
title: Marketing landing.css text-3 (#8b929c) is one full step lighter than transcribe-md text-3 (#6c737f)
---

## Issue

Two design-token systems are diverging:

- `apps/transcribe-md/src/app/globals.css:66` defines `--color-linear-text-3: #6c737f`. Used for muted body labels in app chrome.
- `apps/marketing/src/app/landing.css:36` defines `--text-3: #8b929c`. Same conceptual role on the public site.

Both apps share a single comment header in their CSS pointing to "docs/design-directions-v8-linear/" mockups as the source of truth. The values came out one step apart (the marketing one passes WCAG AA on the dark canvas, the app one does not — see A10-P1-001).

This is a brand-consistency issue: a doctor on the marketing site → click sign-up → arrive in the app sees subtly different muted-text tones. It also means the cross-app a11y story is split — fixing one without the other leaves the same token name with two different real values.

## Evidence

```bash
$ grep -nE "color:.*#" apps/transcribe-md/src/app/globals.css | grep "linear-text"
65: --color-linear-text-2: #b4bcc8;
66: --color-linear-text-3: #6c737f;   # FAILS AA
67: --color-linear-text-4: #4b5159;   # FAILS AA

$ grep -nE "color:.*#" apps/marketing/src/app/landing.css | grep "text"
33: --text:         #f7f8f8;
34: --text-2:       #b4bcc8;
35: --text-3:       #8b929c;   # ~4.7:1 — passes AA
```

`--text-2: #b4bcc8` is identical in both files (good). `--text` is identical (good). `--text-3` is the only divergence, and it happens to be the divergence that determines AA conformance.

## Risk

- Brand tone-of-voice continuity broken at the most important transition: marketing → app.
- The same `text-3` token name has two different real values — confusing to designers and engineers, especially since both files reference the same mockup directory as the source of truth.
- See A10-P1-001 for the cascading a11y impact in the app — this finding is the brand-side observation.

## Recommended fix

Adopt marketing's `#8b929c` as the canonical `text-3` in both apps. Update `apps/transcribe-md/src/app/globals.css:66`:

```css
--color-linear-text-3: #8b929c;   /* was #6c737f — bumped to match marketing token + WCAG AA */
```

Then verify once more that all 480 call sites of `text-linear-text-3` / `var(--color-linear-text-3)` in the app still read correctly at the new tone (they will — this is a 1-step lighten, not a colour-family shift).

For `--color-linear-text-4: #4b5159` (also defined only in the app, not marketing), pick either `#5e636e` (~3.0:1, large-text-only AA) and add a documentation comment + ESLint rule to restrict its use to >= 18pt or >= 14pt-bold contexts; or eliminate it entirely and consolidate on text-3 for muted contexts.

This finding can be closed in the same commit as A10-P1-001.
