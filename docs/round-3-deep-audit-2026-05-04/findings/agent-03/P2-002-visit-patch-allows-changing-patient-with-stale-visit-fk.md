---
id: A03-P2-002
severity: P2
title: PATCH /api/visits/[id] only checks NEW patient's practice — visit's existing patientId may already be cross-practice
domain: authz
agent: agent-03
---

## Issue

`PATCH /api/visits/[id]` (apps/transcribe-md/src/app/api/visits/[id]/route.ts:230-251) validates that the **new** `patientId` belongs to the caller's practice and is not soft-deleted:

```ts
if (parsed.data.patientId !== undefined &&
    parsed.data.patientId !== visit.patientId) {
  const newPatient = await prisma.transcribeMdPatient.findUnique({
    where: { id: parsed.data.patientId },
    select: { id: true, name: true, practiceId: true, deletedAt: true },
  });
  if (!newPatient ||
      newPatient.practiceId !== user.practiceId ||
      newPatient.deletedAt !== null) {
    return apiError('Selected patient is not available.', 400, ...);
  }
}
```

But the existing `visit.patientId` is **never** re-validated on read. Because TranscribeVisit is scoped by `userId` (not `practiceId`) and TranscribeMdPatient is scoped by `practiceId`, a user moved between practices could end up:
- owning visits whose `patientId` points at a Patient row in their **old** practice,
- AND, on `GET /api/visits/[id]` (route.ts:76-135), the response `select` includes the full `patient` sub-object — which the practice change made unreadable via the patients API but is still served via this nested include.

## Evidence

apps/transcribe-md/src/app/api/visits/[id]/route.ts:76-135 (GET):

```ts
const visit = await prisma.transcribeVisit.findUnique({
  where: { id: visitId },
  select: {
    ...
    patient: {            // <-- nested include returns full row
      select: { id: true, name: true, dateOfBirth: true,
                externalId: true, mrn: true, insurance: true,
                problemList: true },
    },
    ...
  },
});
if (!visit || visit.userId !== userId) return apiError('not found', 404);
```

The page-level `/visits/[id]/page.tsx:182-235` does the same `prisma.transcribeVisit.findUnique({ patient: { select: ... } })` with no `practiceId` filter on the join.

## Risk

**Practical impact today**: zero — there is no UI or admin tool that re-parents a User between practices, so visit.patientId.practiceId always matches user.practiceId.

**Class of bug**: defense-in-depth. The system enforces practice isolation at the WRITE site (createVisitAction's `resolvePatient` and PATCH's new-patient check) but trusts the existing FK on READ. If a future migration, SUPER_ADMIN tool, or bug ever stores a cross-practice patientId on a visit, the visit-detail page and the API would still hand the patient row out — bypassing the patient-side `practiceId` filter that the rest of the app enforces.

Combined with finding A03-P2-001 (delete-account assumes solo), the same failure mode (a User outliving a Practice membership change) trips both.

## Recommended fix

Tighten the GET + page-level reads to filter the nested patient join on the caller's practice, e.g.:

```ts
const [visit, user] = await Promise.all([
  prisma.transcribeVisit.findUnique({
    where: { id: visitId },
    select: {
      ...,
      patientId: true,
    },
  }),
  prisma.user.findUnique({
    where: { id: userId },
    select: { practiceId: true },
  }),
]);
if (!visit || visit.userId !== userId || !user) return apiError('not found', 404);

const patient = await prisma.transcribeMdPatient.findFirst({
  where: { id: visit.patientId, practiceId: user.practiceId },
  select: { id: true, name: true, ... },
});
// patient may be null if the visit was orphaned by a re-parent —
// render with patientName fallback.
```

Or, structurally: add a denormalised `practiceId` column on `TranscribeVisit` so FK-time consistency is provable in one query and the app never has to JOIN to verify it.
