---
id: A10-P3-004
severity: P3
domain: UX — mobile gestures
title: No pull-to-refresh and no swipe gestures anywhere — mobile feels static and non-native
---

## Issue

The transcribe-md app on mobile has zero gesture-based UI. No pull-to-refresh on the dashboard or visits list. No swipe-to-archive or swipe-to-delete on visit cards. No swipe-back gesture (Next.js / browser handles back, but no in-app cue). On a phone, every interaction is tap-only.

Native iOS / Android users expect mobile-web apps with this much real-time data to support pull-to-refresh as a baseline gesture. The dashboard polls live status via `processing-state.tsx`'s 2 s interval, so the data is fresh — but a user who *just* signed a visit on desktop, picked up their phone, and opened the dashboard sees stale data until they manually navigate away and back.

Swipe gestures on visit list rows are a polish item, not a baseline — but the missing pull-to-refresh is more notable.

## Evidence

```bash
$ grep -rn "swipe\|onSwipe\|TouchEvent\|touchstart\|pull-to-refresh" apps/transcribe-md/src
# (no results)
```

No use of any gesture library (`framer-motion` is in dependencies but its drag/swipe API is unused). No `touchstart` / `touchmove` / `touchend` handlers anywhere in `src/`.

`apps/transcribe-md/src/app/dashboard/page.tsx` is a server component — no client-side refresh trigger beyond `router.refresh()` which is wired only to specific actions (sign, archive, etc.).

## Risk

- Perception of polish. Doctors who try the iPhone app will compare against iOS-native messaging or Notion mobile and find QuillMD feels stiff.
- Real workflow: a doctor who shares the practice across devices wants the phone view to "feel live". Without pull-to-refresh they either reload the browser tab (loses state, accidentally signs them out on session-cookie envs) or assume the data is stale and don't trust it.

## Recommended fix

Pull-to-refresh is the highest-leverage of the gesture options. Implementation in 30 lines:

1. Wrap `<DashboardBody>` and `<VisitList>` in a small `PullToRefresh` client component:

   ```tsx
   'use client';
   import { useEffect, useRef } from 'react';
   import { useRouter } from 'next/navigation';

   export function PullToRefresh({ children }: { children: React.ReactNode }) {
     const router = useRouter();
     const startY = useRef(0);
     useEffect(() => {
       const onStart = (e: TouchEvent) => { startY.current = e.touches[0].clientY; };
       const onEnd = (e: TouchEvent) => {
         if (window.scrollY === 0 && e.changedTouches[0].clientY - startY.current > 80) {
           router.refresh();
         }
       };
       document.addEventListener('touchstart', onStart, { passive: true });
       document.addEventListener('touchend', onEnd, { passive: true });
       return () => {
         document.removeEventListener('touchstart', onStart);
         document.removeEventListener('touchend', onEnd);
       };
     }, [router]);
     return <>{children}</>;
   }
   ```

   For visual feedback, add a small spinner that animates in as the user pulls past 30 px and stays until the refresh completes.

2. Optional: swipe-to-archive on visit-list rows. The data flow already has an archive action (`apps/transcribe-md/src/app/visits/[id]/visit-lifecycle-actions.tsx`); wire a swipe-left gesture on the row component to invoke it with a confirm-undo toast. Reuse `framer-motion`'s `<motion.div drag="x" dragConstraints={{ left: -100, right: 0 }}>` API — already a dependency, no new install.

Effort: pull-to-refresh ~30 lines, ~1 hour of testing across iOS Safari + Android Chrome. Swipe-to-archive deferred to post-pilot polish unless feature scope expands.
