---
id: A10-P2-003
severity: P2
domain: UX — error pages
title: 404 page has only "Go to dashboard" + "Sign in" — no search, no recent-visits link, no helpful navigation
---

## Issue

`apps/transcribe-md/src/app/not-found.tsx` renders an aesthetic but functionally minimal 404: a "Not here." headline + body copy ("We couldn't find that page. It may have moved, or you may not have access.") + two links: "Go to dashboard" (primary) and "Sign in" (ghost). The same is true of `apps/transcribe-md/src/app/visits/[id]/not-found.tsx`, which is what fires when a doctor hits a visit URL that doesn't exist or has been deleted (the most common 404 trigger in production).

In a clinical workflow, a 404 typically means the doctor pasted a stale link from a previous session, or the visit was archived/trashed/deleted. Neither error is rare. The right 404 helps the doctor find what they were looking for. Current 404 sends them to the dashboard (which they can already navigate to from the sidebar at any time).

## Evidence

`apps/transcribe-md/src/app/not-found.tsx:1-110` — the entire page body is decorative (AnimatedGrid + sage-glow radial + GradientText), and the actionable surface is two links. There's no:

- Search box (the global Cmd+K palette is mounted, but a focus prompt could direct the user to it).
- "Recent visits" list — a server component could query the last 5 visits for the authed user and render them as quick links.
- "Go to patients" link — second-most-common destination after dashboard.

`apps/transcribe-md/src/app/visits/[id]/not-found.tsx:34-58` — visit-specific 404 says "Visit not found" / "This visit doesn't exist or you don't have access to it." with a single back-to-dashboard link. If the visit was deleted, the user has no way to discover that without going to /trash (which they may not know exists). If they pasted a wrong ID, they have no way to search for the right one.

`apps/marketing/src/app/not-found.tsx` — also minimal, no search or pricing/contact pointers.

## Risk

- Clinical workflow friction: a doctor hits a stale link (browser back from /visits/abc-deleted), has to navigate to /dashboard, then re-find the patient. Probably 30 seconds per occurrence — ×5 per week ×100 doctors = real time.
- Lost retention signal: a 404 with only "Go to dashboard" gives the user the impression the product is brittle. A 404 with "Here are your 5 most recent visits" feels alive.

## Recommended fix

Convert `apps/transcribe-md/src/app/not-found.tsx` into a server component (it currently is one — no `'use client'`) that fetches the auth session and, if signed in, queries the last 5 non-deleted visits + recent patients:

```tsx
const session = await auth();
let recentVisits: Array<{ id: string; patientName: string | null; createdAt: Date }> = [];
let recentPatients: Array<{ id: string; name: string }> = [];
if (session?.user?.id) {
  recentVisits = await prisma.transcribeVisit.findMany({
    where: { userId: session.user.id, deletedAt: null, archivedAt: null },
    orderBy: { createdAt: 'desc' },
    take: 5,
    select: { id: true, patient: { select: { name: true } }, createdAt: true },
  });
  recentPatients = await prisma.transcribeMdPatient.findMany({
    where: { practiceId: session.user.practiceId, deletedAt: null },
    orderBy: { updatedAt: 'desc' },
    take: 3,
    select: { id: true, name: true },
  });
}
```

Render them as a hairline-bordered surface-1 card with a "Maybe you meant?" header. Include the Cmd+K hint at the bottom: "Press Cmd+K to search."

For `visits/[id]/not-found.tsx` specifically, also check whether the visit ID exists in the trash/archived state for the same user, and surface "This visit was [trashed on …](/visits/[id]?showTrashed=1) — restore?" if so. That converts a dead-end 404 into a one-click recovery for the most common cause of this 404.

Marketing 404 (`apps/marketing/src/app/not-found.tsx`) — at minimum, link to /pricing, /security, /contact prominently; one line each.
