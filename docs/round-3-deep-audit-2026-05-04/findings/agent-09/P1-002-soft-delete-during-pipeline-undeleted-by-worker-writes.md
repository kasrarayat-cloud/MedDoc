---
id: A09-P1-002
title: Soft-delete + active pipeline race — worker writes to a trashed visit (status flips to READY in trash)
severity: P1
domain: concurrency / soft-delete semantics
---

## Issue
None of the worker's writes (`processVisit` + every layer in
`apps/transcribe-md/src/worker/layers/*.ts`) include `deletedAt: null` /
`archivedAt: null` in their WHERE clauses. The user-facing soft-delete
(`/api/visits/[id]/delete`) writes `deletedAt = now()` without setting
status to anything special. So the worker happily continues writing
`status`, `transcriptRaw`, `soapDraft`, `soapFinal`, `confidenceScores`,
etc. to a row sitting in the trash window.

Concrete sequence:
1. User uploads → status=QUEUED → worker picks up → status=TRANSCRIBING.
2. While L1 (Deepgram) is in flight (~5-30s), the user clicks Delete from
   the dashboard. The /delete route writes `deletedAt = now()`, returns 200.
3. Worker continues. L1 finishes → writes `transcriptRaw`, `transcriptText`.
4. Worker progresses through L2-L6. Each writes to the (now-trashed) row.
5. Eventually status = READY. The doctor sees the visit in the Trash tab
   showing READY. If they restore (`/api/visits/[id]/restore`), they
   suddenly have a "READY" visit they explicitly chose to delete.
6. Worse: the L7 fan-out and final cost rollup all write to the trashed
   row. Cost is incurred for content the doctor signalled they don't want.

The reverse race is symmetric — if the trash sweep cleanup
(`worker/cleanup/stale-visits.ts`) deletes the row at the 15-day mark, but
the worker is mid-write on a job whose visit was soft-deleted 15 days ago
(uncommon but possible if a job was stuck in a retry-backoff for days),
the layer write will fail with P2025 (record not found) AND the
`AiCall.deleteMany` in the cleanup transaction may have already removed
some of the visit's AI-call cost rows.

## Evidence
- `grep -rn "deletedAt" apps/transcribe-md/src/worker/`:
  ```
  worker/cleanup/stale-visits.ts:14    //     WHERE deletedAt IS NOT NULL
  worker/cleanup/stale-visits.ts:15    //       AND deletedAt < now() - 15 days
  worker/cleanup/stale-visits.ts:149   deletedAt: { lt: cutoff },
  worker/cleanup/retention-sweep.ts:16 //   - Skips `deletedAt IS NOT NULL` rows
  worker/cleanup/retention-sweep.ts:93 deletedAt: null,
  ```
  Only the cleanup paths reference `deletedAt`. None of the L1-L7 layers do.
- `apps/transcribe-md/src/worker/layers/04-generate-soap.ts:106-109`:
  ```ts
  await prisma.transcribeVisit.update({
    where: { id: input.visitId },
    data: { soapDraft: text },
  });
  ```
  Writes regardless of `deletedAt`.
- `apps/transcribe-md/src/app/api/visits/[id]/delete/route.ts:185-190`:
  the soft-delete path is `prisma.transcribeVisit.update({ where: { id },
  data: { deletedAt: new Date() } })` with no status guard, no enqueue
  cancellation, no BullMQ-level `job.discard()`.

## Risk
P1 — clinical content shows up in the trash UI (and persists there for 15
days), and ops/cost telemetry counts it as a real visit. Doctor confusion +
audit-trail mess. Severity is P1 not P0 because:
- The data is recoverable — the doctor can permanent-delete from trash.
- No PHI leaks across tenants.
- The cleanup sweep eventually purges everything.

But: the doctor's intent ("I deleted this visit") is silently disregarded for
up to ~15 minutes (the typical pipeline tail), the visit racks up Anthropic +
Deepgram cost, and on restore the row carries content the doctor never
wanted populated.

The HIPAA angle: `audit_logs` carries the `VISIT_DELETED` event, but if
the worker subsequently writes the visit to READY, no compensating
`VISIT_PROCESSING_AFTER_DELETE` event surfaces. An auditor reading the
timeline sees DELETED then nothing, but the row's content reflects post-
delete writes.

## Recommended fix
Two layers:

1. **Layer-write guards**: every `transcribeVisit.update({ where: { id } })`
   in worker.ts + worker/layers/*.ts becomes
   `updateMany({ where: { id, deletedAt: null }, data: … })`. If the
   update returns count=0, the worker logs and bails:
   ```ts
   const r = await prisma.transcribeVisit.updateMany({
     where: { id: input.visitId, deletedAt: null },
     data: { soapDraft: text },
   });
   if (r.count === 0) {
     log.info('worker', 'visit was deleted mid-pipeline — bailing', { visitId });
     throw new VisitDeletedError(); // a new permanent error class
   }
   ```
   The catch block in `processVisit` already classifies categorized errors;
   add 'visit_deleted' as a new permanent category that fail-fast bails
   without further BullMQ retries.

2. **Cancel the BullMQ job on soft-delete**: in the `/delete` route, after
   writing `deletedAt`, look up the active job (by `visit-V-<minute>` jobId
   pattern) and call `job.remove()`. This doesn't prevent already-running
   writes (a worker mid-Anthropic-call won't notice) but it prevents
   downstream layers from running.

The DELETE route should also set status to a new enum value
`DELETED_DURING_PROCESSING` (or just leave it but require the worker to
see deletedAt) so the dashboard distinguishes "trashed before pipeline"
from "trashed during pipeline".
