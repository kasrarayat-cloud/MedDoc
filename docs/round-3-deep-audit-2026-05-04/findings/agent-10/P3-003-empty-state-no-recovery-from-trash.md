---
id: A10-P3-003
severity: P3
domain: UX — empty states
title: All-visits empty state does not surface trash/archive — first-time and post-cleanup users have no signal that a recovery path exists
---

## Issue

The `/visits` page (`apps/transcribe-md/src/app/visits/page.tsx`) shows an `<EmptyState>` when the filtered query returns zero results, with title "No visits yet" and body "Capture your first encounter — live recording, audio upload, or text." This is the right empty state for a brand-new user with zero visits ever created.

But the same empty state fires for a user who has soft-deleted or archived **all** their visits. They see "No visits yet" — a confusing claim because they remember creating them — and have no path from this empty state to the trash or archive view to recover one.

The dashboard's "Patients" tab has a similar issue: empty state implies "you have no patients", but if every patient has been deleted there's no link to /patients/trash or equivalent.

The `Trash` page (`apps/transcribe-md/src/app/patients/[id]/trashed-visit-card.tsx` references one but I did not see a top-level `/trash` route) is reachable only from inside a patient detail page, not from a dashboard empty state.

## Evidence

`apps/transcribe-md/src/app/visits/page.tsx:170-182` (rough — the EmptyState mount):

```tsx
<EmptyState
  kind="sparkle"
  eyebrow="No visits yet"
  title="Start your first visit"
  body="Capture your first encounter — live recording, audio upload, or text."
  cta={<Link href="/visits/new" ...>+ New visit</Link>}
/>
```

No conditional second CTA pointing to `/trash` or "View archived" when the count of trashed/archived visits is non-zero.

`apps/transcribe-md/src/app/dashboard/page.tsx` — the `EmptyPatients` and `EmptyVisits` components inline-render minimal empty states with one CTA. Same pattern.

## Risk

- A doctor who deletes a visit by accident (despite the confirm modal) and immediately revisits the dashboard sees an empty state with no recovery path. They will need to know to navigate to a patient → see trash card per patient. The recoverability is technically present but psychologically invisible.
- HIPAA retention logic keeps deleted visits for 30 days — but that backstop is invisible to the user from the empty state.

## Recommended fix

In `apps/transcribe-md/src/app/visits/page.tsx`, before rendering the EmptyState, run a second cheap count query for trashed/archived visits scoped to the user. If non-zero, conditionally show a second tertiary CTA below the primary one:

```tsx
const [trashedCount, archivedCount] = await Promise.all([
  prisma.transcribeVisit.count({ where: { userId, deletedAt: { not: null } } }),
  prisma.transcribeVisit.count({ where: { userId, deletedAt: null, archivedAt: { not: null } } }),
]);

// in render:
<EmptyState
  ...
  cta={
    <>
      <Link href="/visits/new" ...>+ New visit</Link>
      {trashedCount > 0 && <Link href="/trash" ...>View {trashedCount} in trash</Link>}
      {archivedCount > 0 && <Link href="/archive" ...>View {archivedCount} archived</Link>}
    </>
  }
/>
```

(If a top-level `/trash` route doesn't exist, route to `/visits?filter=trashed` and add the filter to the existing filter pill row. Either way the recovery path needs to be reachable in 1 click from the empty state.)

Same treatment for the dashboard's `EmptyVisits` and `EmptyPatients` inline components.

Also worth considering: an explicit "Trash" entry on the IconRail with a small badge showing the count when > 0 — surfaces the recovery affordance proactively rather than only on empty state.
