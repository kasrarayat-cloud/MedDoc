---
id: A09-P1-001
title: Worker pipeline lacks in-flight lock — concurrency=2 + cross-minute retry can run two pipelines on one visit
severity: P1
domain: concurrency / clinical content duplication
---

## Issue
`apps/transcribe-md/src/worker.ts` runs with `concurrency = 2` by default
(`docker-compose.yml: TRANSCRIBE_MD_WORKER_CONCURRENCY: ${…:-2}`). The
deduplication strategy is BullMQ jobId — `enqueueProcessVisit` builds the
jobId as `visit-<id>-<minuteSinceEpoch>` (or `visit-<id>-retry-<minute>` on
the retry endpoint). This dedupe window is **60 seconds**.

What happens when the dedupe fails:
1. User uploads at minute X. Job `visit-V-X` enqueues. Worker A picks it up,
   starts pipeline.
2. The pipeline takes >10 min on Layer 1 (long Deepgram recording). User
   hits Retry at minute X+12.
3. The retry route's STILL_PROCESSING gate fires only when `now -
   updatedAt < 10 min`. But layer 1 doesn't update `updatedAt` until it
   finishes, and L1 alone can run >10 min on a 45-min recording. The gate
   passes, retry enqueues `visit-V-retry-(X+12)`.
4. Worker has `concurrency=2`. Worker B picks the retry job. Now BOTH
   workers are running `processVisit(visitId='V')` simultaneously.
5. Both call `prisma.transcribeVisit.update({ where: { id: 'V' }, data: { …
   }})` for every layer. Writes interleave; T-M13 resume logic reads
   columns to decide what to skip — those reads see the OTHER worker's
   in-flight writes. Deepgram is called twice (cost!), Anthropic is called
   twice for L4-L6, two `confidenceScores` rolls collide.

Also: the retry endpoint guards STILL_PROCESSING by `IN_FLIGHT_STATUSES`, but
between FAILED and TRANSCRIBING there's a window where the worker has read
the row, enqueued itself, but not yet written `processingStartedAt` /
status. Two concurrent retry POSTs in that window would each pass the gate
and BOTH enqueue.

The only thing protecting most cases today is BullMQ's per-minute jobId
dedupe — but that:
- only covers within the same 60s wallclock window;
- doesn't apply across the `retry` vs initial-enqueue namespaces (different
  jobId suffixes by design);
- doesn't apply if a job hits BullMQ's `removeOnComplete: 24h` boundary and
  is purged before the user retries (post-purge same jobId wouldn't dedupe).

## Evidence
- `apps/transcribe-md/src/worker.ts:79-82`: `const CONCURRENCY = Number.
  parseInt(process.env.TRANSCRIBE_MD_WORKER_CONCURRENCY ?? '2', 10);`.
- `apps/transcribe-md/src/lib/queue.ts:97-114`: `enqueueProcessVisit` —
  per-minute jobId; no DB-level "this visit is currently locked" record.
- `apps/transcribe-md/src/worker.ts:225-294`: `processVisit` opens with
  `prisma.transcribeVisit.findUnique` + unconditional `update({ where: {
  id }, data: { status: initialStatus, … } })`. No status precondition,
  no row lock.
- `apps/transcribe-md/src/worker/layers/01-transcribe.ts:90-97`: layer 1
  writes with `where: { id }` — never checks "am I still the active
  worker for this visit".
- All other layers (02-07) follow the same pattern (verified by `grep -nE
  "transcribeVisit\.(update|updateMany)" apps/transcribe-md/src/worker/
  layers/*.ts`).
- `apps/transcribe-md/src/app/api/visits/[id]/retry/route.ts:46-68`:
  STILL_PROCESSING is `now - updatedAt < 10 min`. Layer 1 alone can write
  zero `updatedAt` bumps for >10 min if Deepgram is slow.

## Risk
P1 — duplicate processing of clinical content. Concrete consequences when
the race fires:
1. **Cost**: Deepgram + Anthropic each get billed twice for the same audio.
   On a 45-min recording, that's $1-2 per duplicate × thousands of pilot
   visits = real money.
2. **Telemetry pollution**: AiCall rows get duplicated; the
   `processingCostCents` rollup at finalization (sums ai_calls)
   double-counts.
3. **Inconsistent SOAP draft**: Worker A finishes L4 → soapDraft = "A's
   draft". Worker B's L4 finishes ~3s later → overwrites with "B's draft".
   Worker A reads "B's draft" for L5 critique, Worker B reads its own.
   The critique reasoning may not match what's in soapFinal. Visible to
   the doctor as "the critique mentions a section that's not in my note".
4. **Status churn**: `status` column flips QUEUED → TRANSCRIBING (A) →
   EXTRACTING (A) → TRANSCRIBING (B, since B re-runs L1) → EXTRACTING
   (B) → … the live UI status spinner thrashes.

Severity is P1 not P0 because:
- The window requires either a BullMQ removeOnComplete-purged job + user
  retry, or a >10-min L1 followed by user retry. Both are rare in current
  pilot scale but expected to manifest with longer recordings.
- The eventual READY/SIGNED state is at least *consistent* even if the
  intermediate is corrupt — soapFinal is whichever worker wrote last.

## Recommended fix
Atomic claim at the top of `processVisit`:

```ts
const claimed = await prisma.transcribeVisit.updateMany({
  where: {
    id: visitId,
    status: { in: [TranscribeVisitStatus.QUEUED, TranscribeVisitStatus.FAILED] },
    deletedAt: null,
  },
  data: {
    status: initialStatus,
    processingStartedAt: startedAt,
    processingWorkerJobId: job.id,  // new column
  },
});
if (claimed.count === 0) {
  log.warn('worker', 'visit already claimed by another worker — bailing out', { visitId, jobId: job.id });
  return; // exit cleanly; the OTHER worker owns this visit
}
```

This turns "fan-in to one row" into "first writer wins, second writer
exits as a no-op". The new `processingWorkerJobId` column lets ops see
which BullMQ job is the active owner.

Layer-level writes should also include `where: { id, processingWorkerJobId:
<thisJobId> }` to refuse stale writes from a worker that lost the claim.
That's a bigger change — first ship the entry-point claim + alert when it
catches a duplicate, see how often the alert fires, then decide whether
the per-layer guard is worth the schema churn.

Lower-effort partial fix: tighten the STILL_PROCESSING gate — instead of
`updatedAt < 10 min`, keep a heartbeat column the worker writes every
30s during long Deepgram calls. The retry route then sees a fresh
heartbeat even mid-Deepgram and rejects the duplicate. Doesn't fix
admin-triggered re-enqueues but covers the doctor-driven path.
