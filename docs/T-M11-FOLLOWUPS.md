# T-M11 — deferred follow-ups

The T-M11 error-hardening pass flagged four worker-side improvements.
Two landed (per-job 15-min timeout, audit rollup); two are deferred
because they're not blocking launch and each is a larger scope than
T-M11 had room for. Capturing here so they don't get lost.

## 1. Per-layer pipeline resumability

**Today**: if Layer 6 (polish) throws, the BullMQ retry re-runs Layers
1-5 from scratch — re-hitting Deepgram for Layer 1 and re-prompting
Claude for Layers 2-5. At current MOCK-mode speeds that's free; at
production rates a single failed visit costs ~2× the normal
Deepgram + Anthropic spend per retry (up to 3 attempts = 3× waste).

**What to do**: checkpoint after each layer writes its Prisma column.
On retry, the worker inspects the visit row and skips ahead to the
first empty column. Most of the pieces are already there —
`processVisit` already clears the automation columns at the start of
each attempt, but it re-runs L1-6 unconditionally. Would need:

- Layer-by-layer read-first: if `transcriptRaw` exists skip L1, if
  `speakerMap` exists skip L2, etc.
- A retry-attempt guard at the start of the outer catch path so
  L7x automation doesn't re-persist columns we already filled.
- Decide whether a retry after a SUCCESSFUL L1 but failed L2 counts
  as a fresh visit for cost telemetry — probably "sum across
  retries by visitId" is the right answer; current roll-up already
  does that.

**Blast radius**: worker-only, no schema. A half-day of careful
rewriting + a couple of new Playwright scenarios covering retry
paths.

## 2. MinIO orphan cleanup

**Today**: `/api/visits/[id]/upload` puts bytes into MinIO under
`{userId}/{visitId}/…`. If a visit row later disappears (test
cleanup, manual DB delete, HIPAA retention cron) the MinIO object
hangs around. The bucket grows monotonically.

**What to do**: scheduled sweep that lists MinIO objects, cross-
checks against `transcribe_visits.audioKey` / `dictationAudioKey`,
and deletes any object older than (say) 30 days that no DB row
references. Needs:

- A new cron/scheduler — today there's no scheduling infrastructure
  on the TranscribeMD side (the deleted scribe-worker had BullMQ
  repeat jobs for retention but that whole pattern went away with
  Scribe).
- A safety threshold so a transient DB outage can't make the
  cleanup delete everything.
- Ops log + a dry-run flag so the first run can be audited before
  deletions land.

**Blast radius**: new cron service + MinIO listing/deletion logic.
Larger than T-M11 — probably its own small milestone.

## When to revisit

- **Resumability**: when retry costs start showing up in the monthly
  Anthropic bill, or a single customer has a stuck visit retry
  story that burns support time.
- **Orphan cleanup**: when MinIO usage graph shows unbounded growth
  that doesn't match active-visit counts, or at the next HIPAA
  retention review.

Neither is on the launch critical path.
