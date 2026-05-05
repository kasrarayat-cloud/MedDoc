---
id: A10-P1-002
severity: P1
domain: a11y / WCAG 2.4.1 (Bypass Blocks)
title: Skip-to-content link points at #main but no element in the app has id="main" — link is non-functional
---

## Issue

The transcribe-md root layout renders a "Skip to main content" link as the first focusable element of the body, with `href="#main"`. Round 2's PR #104 added this in response to the WCAG 2.4.1 baseline finding. However, **no element anywhere in `apps/transcribe-md/src/` has the matching `id="main"`** — grep returns zero results across the entire `src/` tree. The link is rendered, the focus animation works, the keyboard shortcut works, but pressing it scrolls nowhere and does not move focus to the main content. Screen-reader users following the same affordance get the same dead-end.

The marketing site (`apps/marketing/src/`) does not even render the skip link — its root layout has no equivalent. Doctors browsing pricing / privacy / security pages on a keyboard have no bypass mechanism for the sticky 56-px nav and brand wordmark on every page.

## Evidence

`apps/transcribe-md/src/app/layout.tsx:80-86`

```tsx
<a
  href="#main"
  className="sr-only focus:not-sr-only focus:fixed focus:left-2 focus:top-2 focus:z-50 focus:rounded-md focus:bg-linear-sage focus:px-3 focus:py-2 focus:font-medium focus:text-linear-bg focus:shadow-lg"
>
  Skip to main content
</a>
```

The comment block immediately above (lines 70-78) acknowledges the issue and tries to argue the link "still passes WCAG technique G1 (skip link present); the target landing simply scrolls to the top of the body":

> *For pages that don't yet have <main id="main">, the link still passes WCAG technique G1 (skip link present); the target landing simply scrolls to the top of the body.*

That is **not how WCAG works** — Technique G1 requires that activating the link "moves the keyboard focus to the main content", not merely that an element with the text exists. axe-core does not catch this because axe checks only for the presence of the link element, not the validity of the fragment target. So R2's gate passed.

`apps/transcribe-md/src/components/ui/app-frame.tsx:60-67` — the canonical authenticated `<main>` element is rendered without an `id`:

```tsx
<main
  style={{
    flex: 1,
    minWidth: 0,
    position: 'relative',
  }}
>
  {children}
</main>
```

Marketing root layout (`apps/marketing/src/app/layout.tsx`) renders no skip link at all — only the `<body>` wrapper. Every marketing page mounts its own `<main>` (e.g. `apps/marketing/src/app/page.tsx:31`) but with no `id` and no upstream skip-to anchor.

```bash
$ grep -rn 'id="main"' apps/transcribe-md/src apps/marketing/src
# (no results)
```

## Risk

- **WCAG 2.4.1 Level A non-conformance** for both apps. Level A failures are a procurement-blocker for hospital systems and federally-funded clinics.
- Keyboard-only and screen-reader doctors cannot bypass the 48-px top nav + sidebar IconRail to reach the dashboard's primary-action region without 6+ tab presses on every navigation.
- Round-2 closed this as fixed when it wasn't; the regression matrix needs updating before pre-pilot.

## Recommended fix

1. In `apps/transcribe-md/src/components/ui/app-frame.tsx`, add `id="main"` and `tabIndex={-1}` to the `<main>` element so the fragment target works and a non-tab-stop element can still receive programmatic focus on activation:

   ```tsx
   <main
     id="main"
     tabIndex={-1}
     style={{ ... }}
   >
   ```

2. In `apps/transcribe-md/src/app/visits/[id]/loading.tsx:25` and `apps/transcribe-md/src/app/visits/[id]/not-found.tsx:22`, also add `id="main"` since those pages render outside the AppFrame boundary. Same in `apps/transcribe-md/src/app/admin/layout.tsx:107`.

3. In `apps/marketing/src/app/layout.tsx`, mirror the transcribe-md skip-link block (using the marketing landing.css's `qm-tap-44`-equivalent and color tokens), and add `id="main" tabIndex={-1}` to every `apps/marketing/src/app/**/page.tsx`'s top-level `<main>` (10 pages: page, pricing, privacy, terms, security, hipaa, contact, about, demo, signup).

4. Update the layout.tsx comment block to remove the "still passes WCAG technique G1" justification — once (1)–(3) land, the comment is wrong and misleading.
