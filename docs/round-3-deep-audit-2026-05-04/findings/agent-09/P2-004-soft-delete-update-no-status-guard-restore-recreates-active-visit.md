---
id: A09-P2-004
title: /restore route lacks status check — restoring a visit whose pipeline ran post-delete creates a "READY" trash-survivor
severity: P2
domain: data-integrity / soft-delete semantics
---

## Issue
This issue compounds with A09-P1-002 (worker doesn't check deletedAt). When
a visit is soft-deleted while the pipeline is mid-flight, the worker keeps
writing. By the time the user visits Trash and clicks Restore, the row may
have transitioned soft-delete → READY → (worker continues writing L7
columns + cost) → soft-delete-with-content. Restore clears `deletedAt`
unconditionally:

```ts
await prisma.transcribeVisit.update({
  where: { id: visit.id },
  data: { deletedAt: null },
});
```

— so the doctor sees a fully-populated SOAP visit they had explicitly
deleted, with no audit trail explaining what they deleted vs what they
restored. The doctor's expectation when restoring a "QUEUED" trashed visit
is "I get back what I deleted." The actual outcome is "I get back a fully
processed visit, including content I never reviewed pre-delete."

Reverse race: if the worker FAILS post-delete (e.g. Anthropic throws), the
catch block in `processVisit` writes `status=FAILED`, `reviewReason='…'` to
the trashed row. Restore then surfaces a FAILED visit + an alarming review
banner the doctor doesn't expect.

## Evidence
- `apps/transcribe-md/src/app/api/visits/[id]/restore/route.ts:64-71`:
  ```ts
  if (visit.deletedAt === null) {
    return NextResponse.json({ ok: true, alreadyActive: true });
  }
  await prisma.transcribeVisit.update({
    where: { id: visit.id },
    data: { deletedAt: null },
  });
  ```
  No status check. No "this visit was modified after delete" warning.
- `apps/transcribe-md/src/app/api/visits/[id]/delete/route.ts:185-190`:
  the soft-delete path writes ONLY `deletedAt = now()` — doesn't change
  status, doesn't cancel the BullMQ job.

## Risk
P2 — surprising UX + audit-trail confusion. Severity:
- Not P1 because the data is at least correct (worker output is
  consistent with what the visit's content would have been).
- The doctor can immediately re-delete if the restored content is
  unexpected.
- HIPAA: each individual write IS audited (worker writes don't go through
  the audit log, but the delete + restore are both logged). The state
  reconciliation is left to a careful reader of the timeline.

## Recommended fix
Two complementary changes:

1. **Cancel pipeline on soft-delete**. In `/delete`, after writing
   `deletedAt`, also:
   - Look up the active BullMQ job by visitId-based jobId (depends on
     adopting the visit-id-only jobId — see A09-P1-004).
   - Call `job.remove()`.
   - Set `status` to a new sentinel like `CANCELLED` so the worker's
     write guards (A09-P1-002) refuse to advance.

2. **Restore-time validation**. In `/restore`, if `deletedAt` is non-null
   AND `processingStartedAt > deletedAt`, surface a flag in the response:
   ```ts
   const wasModifiedAfterDelete =
     visit.processingStartedAt !== null &&
     visit.deletedAt !== null &&
     visit.processingStartedAt > visit.deletedAt;
   return NextResponse.json({
     ok: true,
     wasModifiedAfterDelete,
     // The UI can surface "this visit was processed after you deleted
     // it; its content may differ from what you remember"
   });
   ```

The audit log row written by /delete + /restore should also include the
status delta in metadata so a compliance review can reconstruct what the
visit looked like at delete vs at restore.
