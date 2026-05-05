---
id: A10-P2-004
severity: P2
domain: UX — navigation history
title: Browser-back from /visits/[id] resets dashboard scroll to top — doctor loses position in long visit list
---

## Issue

A typical clinician workflow: scroll the dashboard "All visits" tab to find a 3-week-old visit, click into it, review, hit browser-back. With Next.js 15+ App Router, the default scroll behaviour for back/forward navigation **does** restore scroll on simple GET → GET — but multiple paths in the dashboard hot-flow break this:

1. The dashboard tabs are `Link` components with `scroll={false}` (`apps/transcribe-md/src/app/dashboard/page.tsx:225`). Switching from "Patients" → "All visits" doesn't scroll, but the URL change pushes a history entry. Hitting back from a deeper visit detail returns to the dashboard but scroll position is on the wrong tab.

2. There is no explicit `experimental: { scrollRestoration: true }` in `next.config.ts`. Next.js's default scroll-restoration in App Router is documented as best-effort and can be flaky when a page transitions back through a Suspense boundary that re-fetches (which the dashboard does — every navigation back re-runs the `Suspense fallback={<DashboardSkeleton />}` flow before settling).

3. No manual `useScrollRestoration` hook is wired anywhere in `apps/transcribe-md/src/`. No `sessionStorage`-based scroll cache.

4. The `/visits` list page (`apps/transcribe-md/src/app/visits/page.tsx`) has no pagination cursor in the URL, and rendering 80 rows then clicking into one and pressing back loses position even more reliably than the dashboard.

## Evidence

```bash
$ grep -rn "scrollRestoration\|sessionStorage.*scroll\|useScrollRestoration" apps/transcribe-md/src apps/transcribe-md/next.config.ts
# (no results)
```

`apps/transcribe-md/next.config.ts:1-17` — no `experimental.scrollRestoration`.

`apps/transcribe-md/src/app/dashboard/page.tsx:225` (TabBar) — Link uses `scroll={false}`:
```tsx
<Link key={t.id} href={t.href} scroll={false} ...>
```

`apps/transcribe-md/src/app/visits/[id]/back-link.tsx` — exists, but uses `router.back()` which just calls `history.back()` and inherits the same default behaviour. No scroll-position fingerprint is stored before navigating away.

## Risk

- Time-on-task: a doctor reviewing 5 visits in a row from the dashboard pays the scroll-relocation tax 5 times. With 80+ visits in the list, that's 10-15 seconds of scrolling per round-trip.
- The visits page hits this hardest because doctors with > 30 visits per week will scroll.
- Confidence — when a click loses your context, the product feels unfinished.

## Recommended fix

1. Add to `apps/transcribe-md/next.config.ts`:
   ```ts
   experimental: {
     scrollRestoration: true,
     optimizePackageImports: ['lucide-react'],
   }
   ```

2. For the dashboard tab links specifically, change `scroll={false}` → drop the prop (default is `scroll={true}` on the same path → no reflow). This still preserves the scroll position because the URL push uses `replaceState` semantics for shallow tab swaps. Test by switching tabs to verify no jump.

3. For the dashboard list and `/visits` list, add a `useScrollRestoration` hook that stores `window.scrollY` keyed by `pathname + searchParams` in `sessionStorage` on `beforeunload` and restores on `useLayoutEffect` mount:
   ```ts
   // src/lib/scroll-restoration.ts
   export function useRememberScroll(key: string) {
     useLayoutEffect(() => {
       const saved = sessionStorage.getItem(`scroll:${key}`);
       if (saved) window.scrollTo(0, Number(saved));
       const onSave = () => sessionStorage.setItem(`scroll:${key}`, String(window.scrollY));
       window.addEventListener('scroll', onSave, { passive: true });
       return () => window.removeEventListener('scroll', onSave);
     }, [key]);
   }
   ```
   Mount it in a thin client wrapper around `<DashboardBody>` and `<VisitList>`.

4. As a smaller mitigation: visit-detail's `back-link.tsx` could `router.back()` and explicitly `window.scrollTo(0, scrollY)` from a memorised value passed via `sessionStorage`.

Test plan: scroll dashboard halfway, click visit, click back-link. Verify scroll returns. Repeat with `/visits?filter=signed`.
