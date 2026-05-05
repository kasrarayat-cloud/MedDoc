---
id: A11-P1-006
severity: P1
domain: error-handling-observability
title: No BullMQ DLQ + no bull-board — failed jobs are blind to ops
---

# A11-P1-006 — Failed BullMQ jobs disappear into a hidden Redis list with no operator UI

## Issue

The BullMQ wiring in `apps/transcribe-md/src/lib/queue.ts:47-66` configures:

```ts
defaultJobOptions: {
  attempts: 3,
  backoff: { type: 'exponential', delay: 5_000 },
  removeOnComplete: { count: 500, age: 24 * 3600 },
  removeOnFail:     { count: 500 },
},
```

This is a sensible retry policy, but:

1. **No dead-letter queue**: failed jobs after 3 attempts go to BullMQ's
   internal `bull:transcribe-md:failed` ZSET, capped at 500 entries.
   No separate DLQ that ops can inspect with retention longer than the
   500-entry rolling buffer. A burst of 600 failures (e.g. a Deepgram
   regional outage) overflows the buffer and the oldest failures are
   silently evicted before anyone has a chance to investigate.

2. **No bull-board / Arena / no UI** mounted anywhere. The only ways
   ops can see failed jobs today:
   - `redis-cli ZRANGE bull:transcribe-md:failed 0 -1 WITHSCORES`
     (raw BullMQ key — fragile if BullMQ changes its key naming)
   - The visit-side `transcribeVisit.findMany({ status: FAILED })`
     query, which only catches failures that wrote a FAILED row.
     If the failure happened during the worker's own boot
     (`ensureBucket` etc.) or before the row was written, it's
     invisible.

3. **No poison-message protection beyond max-attempts**: once a
   permanent error fails 3 attempts, the visit row is `FAILED` and
   the job sits in the failed list. There's no automatic flag,
   alert, or quarantine — operator must `redis-cli` or run a manual
   migration script.

`/api/admin/system/health/route.ts:104-107` does surface
`bull:transcribe-md:wait` length, but **NOT** `:failed` count, so the
admin dashboard's "queues" widget doesn't show how many jobs are
failing.

## Evidence

```
$ grep -rn "DLQ\|dead.letter\|deadletter\|bull-board\|@bull-board\|ArenaQueue" \
    /opt/meddoc-pro/apps /opt/meddoc-pro/packages --include="*.ts"
# (zero hits — no UI, no DLQ exporter)

$ grep -rn "removeOnFail\|attempts:" /opt/meddoc-pro/apps/transcribe-md/src/lib/queue.ts
apps/transcribe-md/src/lib/queue.ts:54:      attempts: 3,
apps/transcribe-md/src/lib/queue.ts:57:      removeOnComplete: { count: 500, age: 24 * 3600 },
apps/transcribe-md/src/lib/queue.ts:58:      removeOnFail: { count: 500 },
```

`apps/transcribe-md/src/app/api/admin/system/health/route.ts:104-107` —
queries `wait` only:
```ts
const [tmWait, cleanupWait] = await Promise.all([
  r.llen('bull:transcribe-md:wait').catch(() => 0),
  r.llen('bull:transcribe-md-cleanup:wait').catch(() => 0),
]);
```
No `:failed` ZSET cardinality query.

## Risk

When a Deepgram-API-key rotation happens during a deploy and 500+ visits
fail before anyone notices the env-var got dropped:

1. The first 500 failures are visible via `redis-cli ZRANGE`.
2. The 501st pushes the oldest off the head of the failed-list. We've
   permanently lost the original failure context.
3. The on-call engineer eventually runs `prisma transcribeVisit.findMany({
   status: FAILED })` and gets 500+ rows back, but the per-job retry
   trail in BullMQ is partly gone.
4. A bulk re-enqueue script has to guess at which visits are still
   recoverable — and it has to query `transcribeVisit` directly,
   bypassing BullMQ's idempotency (so a re-enqueue while the worker
   is recovering can double-process).

A poison-message scenario: one visit's payload triggers a deterministic
unhandled rejection in (say) the `runLayer3ExtractEntities` JSON parser.
That visit retries 3 times and lands in `:failed`. Per
`isPermanentInputError` in `error-categorize.ts:113-153` it would be
caught — but **only if the error message matches the regex list**.
A new failure mode (e.g. Anthropic returning a new error string
not in the regex) gets misclassified as transient, retried 3 times, then
marked FAILED. If three doctors hit it simultaneously, that's 9 wasted
Anthropic calls before the system gives up.

## Recommended fix

1. **Mount bull-board** behind admin auth at e.g.
   `/admin/ops/queues` (transcribe-md app). Existing admin gate
   (`apps/transcribe-md/src/lib/admin-api-gate.ts`) already enforces
   SUPER_ADMIN — wrap the bull-board Express adapter with that
   middleware. Quick win: ~50 lines.

2. **Add explicit DLQ visibility** to `/api/health` and to
   `/api/admin/system/health`:
   - `bull:transcribe-md:failed` ZCARD (count of failed jobs)
   - `bull:transcribe-md:active` LLEN (count of in-progress —
     anomalously high active count = wedged worker; see A11-P1-003)
   - `bull:transcribe-md-cleanup:failed` ZCARD

3. **Bump `removeOnFail.count`** from 500 to e.g. 5,000 (and add
   `age: 30*24*3600`) so a real outage doesn't lose context. Memory
   hit is negligible — BullMQ stores ~1 KB per failed job.

4. **Sentry-side alert**: configure the existing Sentry integration
   to alert on `tags.layer = 'L1' OR layer = 'init'` with a 5-minute
   sliding window — if more than 10 failures, page on-call. (No
   change needed in code; just configure Sentry alert rules and
   document them.)
