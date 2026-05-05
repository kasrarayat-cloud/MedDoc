---
id: A09-P1-004
title: BullMQ jobId dedupe is per-minute — clicks across the minute boundary enqueue duplicate pipelines
severity: P1
domain: concurrency / idempotency
---

## Issue
`enqueueProcessVisit()` in `apps/transcribe-md/src/lib/queue.ts:97-114`
generates a jobId of `visit-<id>-<minuteSinceEpoch>` (or `visit-<id>-retry-
<minute>` for retry endpoint). BullMQ dedupes by jobId — a second `add()`
with an existing jobId is a silent no-op. So a double-click within the same
60-second wallclock window is correctly dedupe'd.

But the window is exactly 60 seconds, and:
- A doctor clicking Upload at second 59 of minute X then re-clicking at
  second 1 of minute X+1 produces TWO different jobIds → TWO enqueues →
  worker will attempt to run the pipeline twice (subject to the
  worker-side claim — see A09-P1-001 — which is also missing).
- Initial-enqueue jobId (`visit-V-<min>`) and retry-enqueue jobId
  (`visit-V-retry-<min>`) live in DIFFERENT namespaces. So if Upload
  enqueues at minute X and Retry enqueues at minute X (same minute),
  jobIds differ and both get queued.
- BullMQ's `removeOnComplete: 24h` purges the original jobId after a day.
  After purge, a same-jobId add() is no longer a no-op (no dedupe state
  left). The 24h purge boundary is invisible to callers.
- Clock skew across the web container's pods (post-pilot when there's
  more than one) means each pod's `Math.floor(Date.now() / 60_000)` may
  differ by ~1 from another pod, defeating dedupe across pods.

A more robust scheme would be a content-addressed jobId (e.g. include
audioKey or visitId+contentHash), or use BullMQ's built-in `jobId =
visitId` and let the worker no-op on already-claimed visits. The latter is
what most production BullMQ pipelines do.

## Evidence
`apps/transcribe-md/src/lib/queue.ts:104-114`:
```ts
const minute = Math.floor(Date.now() / 60_000);
const jobId = opts.retry
  ? `visit-${visitId}-retry-${minute}`
  : `visit-${visitId}-${minute}`;
```

The comment correctly notes the 60s window and the "intentional retry > 60s
later → different jobId → new run" behaviour. The bug is that the SAME
`opts.retry=false` upload click split across the minute boundary also
gets a new jobId.

`apps/transcribe-md/src/lib/queue.ts:50-65`:
```ts
defaultJobOptions: {
  attempts: 3,
  backoff: { type: 'exponential', delay: 5_000 },
  removeOnComplete: { count: 500, age: 24 * 3600 },
  removeOnFail: { count: 500 },
},
```
24-hour `removeOnComplete` window — after that, even the same-minute
re-enqueue won't dedupe.

## Risk
P1 — duplicate pipeline execution → duplicate Deepgram + Anthropic spend
(see A09-P1-001 for the downstream content corruption). Severity
characterisation:
- The minute-boundary case requires submission within ~1 second of the
  clock rolling over. Probability per click: 1/60 ≈ 1.7%.
- Pre-pilot scale: ~50 visits/day → ~5 visits/month hit this race purely
  by chance. Each duplicate burns $0.50-$2 in API spend. Marginal at
  pre-pilot scale, becomes real money at 1000s/day.
- More important: the assumption that "BullMQ jobId protects us" is
  used elsewhere as a rationale for not adding a worker-side claim
  (A09-P1-001). Removing this assumption clarifies that the worker-side
  claim is non-optional.

## Recommended fix
Two options, ship one:

**Option A — content-addressed jobId**. Use `visit-<visitId>` (no minute)
as the jobId. Initial upload enqueues `visit-V`. Subsequent retries within
the 24h window are no-ops (BullMQ dedupes). Subsequent retries outside the
24h window enqueue successfully because the jobId has aged out.

The retry route then explicitly removes the old job before re-adding:
```ts
const queue = getTranscribeMdQueue();
await queue.remove(`visit-${visitId}`).catch(() => {}); // ignore not-found
await queue.add(JOB_PROCESS_VISIT, { visitId, userId },
  { jobId: `visit-${visitId}` });
```

This is the standard pattern. Combined with the worker-side claim
(A09-P1-001), it gives true single-flight per visit.

**Option B — keep the minute scheme, narrow the window to 24 hours**.
Use `Math.floor(Date.now() / 86_400_000)` instead of `60_000`. Same
shape, much wider window. Downside: an intentional retry within 24h
(common after a transient failure) needs an explicit `retry: true`
suffix, which the route already has. So changing 60s → 86400s is
mostly a config tweak.

Option A is cleaner and matches BullMQ idioms. Option B is one-line.
