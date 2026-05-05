---
id: A10-P2-006
severity: P2
domain: UX — mobile / responsive
title: No mobile bottom-bar nav; sidebar collapses but no thumb-reach navigation on phone-width
---

## Issue

The transcribe-md app shell (`apps/transcribe-md/src/components/ui/app-frame.tsx`) is a 240-px sidebar + content grid. At ≤ 980 px the grid collapses to single-column (`apps/transcribe-md/src/app/globals.css:166-169`), which removes the IconRail entirely on mobile. On a phone the user is left with:

- TopNav at the top (48 px tall, sticky) — out of thumb reach on iPhone 13 (812 px height).
- Cmd-K trigger pill in the TopNav — still requires a thumb stretch.
- "+ New visit" CTA in the TopNav — same.

There is no bottom-bar nav. The first-action button "+ New visit" — the most-pressed control in the product — is a 48-px-tall button at the very top of a 812-px viewport, requiring a one-handed thumb stretch that fails iOS Human Interface Guidelines for primary actions on phones.

A clinician using QuillMD between patients in a hallway is the canonical mobile use case — they will use one hand. They will press the same button 30 times a day. It needs to live in the bottom 25% of the screen.

## Evidence

`apps/transcribe-md/src/app/globals.css:166-170`:
```css
@media (max-width: 980px) {
  .qm-lin-app {
    grid-template-columns: 1fr;
  }
}
```

When the IconRail vanishes, **no replacement nav surface is added** for mobile. The `.qm-lin-chrome` (TopNav) stays, but its CTA + brand + Cmd-K trigger compete for ~3 distinct top-row positions on a 390-px viewport.

```bash
$ grep -rn "bottom-bar\|bottom-nav\|fixed bottom" apps/transcribe-md/src
# (no results)
```

iOS HIG thumb zone diagram puts the comfortable thumb reach for a 6.1" iPhone at the bottom 35% of the screen and the stretchy "I can do this once" zone in the top 30%. Putting "+ New visit" in the top-right corner of a 812-px-tall iPhone screen is the worst possible position.

## Risk

- Adoption signal: doctors who try the product on their phone will find it fiddly and revert to desktop-only use, which kills the "between-patient capture on phone" workflow that's a core value prop.
- Repeated-stretch ergonomic issue.
- Touch-target compliance: `.qm-lin-btn-primary` does have a `min-height: 44px` mobile rule (good — A10-positive), but ergonomic placement is independent of size.

## Recommended fix

Add a mobile-only bottom bar to `apps/transcribe-md/src/components/ui/app-frame.tsx`. Render the same 4-5 IconRail destinations (Dashboard, Patients, Visits, Settings) as flat icons in a sticky bottom row, and promote "+ New visit" to a centered pill or FAB above the bar:

```tsx
{/* Mobile-only bottom bar — sticky, hairline-bordered */}
<nav
  aria-label="Primary"
  className="qm-lin-bottom-nav"
>
  <Link href="/dashboard" aria-label="Dashboard">…</Link>
  <Link href="/visits" aria-label="Visits">…</Link>
  <Link href="/visits/new" aria-label="New visit"
        className="qm-lin-btn-primary">+</Link>
  <Link href="/patients" aria-label="Patients">…</Link>
  <Link href="/settings" aria-label="Settings">…</Link>
</nav>
```

CSS (add to globals.css):
```css
.qm-lin-bottom-nav { display: none; }
@media (max-width: 980px) {
  .qm-lin-bottom-nav {
    display: grid;
    grid-template-columns: repeat(5, 1fr);
    position: fixed;
    inset: auto 0 0 0;
    height: 56px;
    padding: 0 12px env(safe-area-inset-bottom);
    background: var(--color-linear-surface-1);
    border-top: 1px solid var(--color-linear-border);
    z-index: 40;
  }
  /* Bottom-pad the main content so the bar doesn't overlap last row. */
  main { padding-bottom: calc(72px + env(safe-area-inset-bottom)); }
  /* Strip the top "+ New visit" CTA on mobile to avoid duplication. */
  .qm-lin-chrome .qm-lin-btn-primary { display: none; }
}
```

Each icon should have an explicit `aria-label` (already required for the IconRail row). Ensure tap targets are ≥ 44 px (the row is 56 px so the icon hit area satisfies). Add `aria-current="page"` on the active route's link for screen readers.

This is the single most-impactful mobile UX change for the pre-pilot. Effort: ~80 lines (one file + one CSS block + 5 icon imports).
