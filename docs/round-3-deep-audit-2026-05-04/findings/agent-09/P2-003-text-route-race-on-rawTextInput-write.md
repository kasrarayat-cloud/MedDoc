---
id: A09-P2-003
title: /api/visits/[id]/text race — concurrent submits both pass the "already-submitted" guard, both enqueue
severity: P2
domain: concurrency / duplicate processing
---

## Issue
`POST /api/visits/[id]/text` (apps/transcribe-md/src/app/api/visits/[id]/
text/route.ts) check-then-act races: the route reads `rawTextInput`,
returns 409 if non-empty, otherwise updates + enqueues. Two simultaneous
requests can both pass the read (both see null), both update (the second
overwrites the first's text), both enqueue (BullMQ jobId per-minute may
dedupe, see A09-P1-004 for the boundary case).

```ts
if (visit.rawTextInput?.trim()) {
  return apiError('text has already been submitted for this visit', 409);
}
if (visit.status !== TranscribeVisitStatus.QUEUED) {
  return apiError('visit is already processing or finalized', 409);
}

await prisma.transcribeVisit.update({
  where: { id: visitId },
  data: { rawTextInput: parsed.data.text, ... },
});

await enqueueProcessVisit(visitId, userId);
```

The dictation/upload route has the same shape (check
`dictationAudioKey === null`, then update). The only check-then-act write
that's atomic is `/sign`, which uses `updateMany({ where: { id, status:
READY }, … })`.

## Evidence
- `apps/transcribe-md/src/app/api/visits/[id]/text/route.ts:79-100`.
- `apps/transcribe-md/src/app/api/visits/[id]/dictation/upload/route.ts
  :82-89, 160-173`.
- `/sign` route (line 233-244) uses the correct atomic pattern:
  ```ts
  const updated = await prisma.transcribeVisit.updateMany({
    where: { id: visitId, status: TranscribeVisitStatus.READY },
    data: { status: SIGNED, … },
  });
  if (updated.count === 0) { /* race lost */ }
  ```

## Risk
P2 — duplicate clinical content, double cost, brief UI confusion. Severity:
- A doctor double-submitting text notes is rare (a single textarea with
  a Submit button; the button presumably gets disabled on click — but
  client-side disable only).
- The damage from a successful race is contained: both requests write the
  same text body in the typical case (user double-clicked the same
  button), so visible artifact is minimal — but the duplicate enqueue
  still risks a duplicate pipeline run if BullMQ jobId dedupe doesn't
  catch it (see A09-P1-004).
- An adversarial client (e.g. a flaky network with retry middleware)
  could send DIFFERENT text in two requests and the loser's text is
  silently dropped while still being counted in audit_logs / api_usage.

## Recommended fix
Same pattern as `/sign`:

```ts
const updated = await prisma.transcribeVisit.updateMany({
  where: {
    id: visitId,
    status: TranscribeVisitStatus.QUEUED,
    OR: [{ rawTextInput: null }, { rawTextInput: '' }],
    deletedAt: null,
    archivedAt: null,
  },
  data: { rawTextInput: parsed.data.text, /* … */ },
});
if (updated.count === 0) {
  return apiError('Text already submitted or visit is no longer accepting text.', 409);
}
```

The same pattern fits dictation/upload (replace `rawTextInput` predicate
with `dictationAudioKey: null`).

For audio /upload: the existing flow PUTs to MinIO before any DB write, so
the check-then-act is harder to atomicise. Best mitigation there is the
worker-side claim from A09-P1-001 + a unique constraint on `(visitId)`
in BullMQ's queue (use `visitId` as jobId — see A09-P1-004 fix).
