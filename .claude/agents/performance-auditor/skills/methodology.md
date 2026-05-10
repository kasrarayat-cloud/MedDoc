# Methodology — Performance Auditor

> Five phases. Phases 1, 2, 4 read live state; phases 3, 5 run
> against PR diffs / build artifacts. Each phase emits findings per
> `finding-classes.md`'s severity table.

## Phase 0 — Schema/dependency sanity

Pre-condition check. Reads `data-sources.md` §1's columns from
`information_schema.columns`; confirms each is present + typed
correctly. Reads §2's Redis keys; confirms each is reachable.
Reads §3's filesystem paths; confirms `app-build-manifest.json`
exists if Phase 5 will run.

**Output.** Either "phase 0 OK" or one or more `SCHEMA_GAP`
findings. Schema gaps fail the run — fix before continuing.

## Phase 1 — Pipeline RTT

Reads `transcribe_visits` for `WHERE status = 'READY' AND
deletedAt IS NULL AND uploadedAt >= NOW() - INTERVAL '24 hours'`.

Computes:

```sql
SELECT
  COUNT(*) AS n,
  PERCENTILE_DISC(0.5)  WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (processedAt - uploadedAt))) AS p50_sec,
  PERCENTILE_DISC(0.95) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (processedAt - uploadedAt))) AS p95_sec,
  PERCENTILE_DISC(0.99) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (processedAt - uploadedAt))) AS p99_sec
FROM transcribe_visits
WHERE status = 'READY'
  AND "deletedAt" IS NULL
  AND "uploadedAt" >= NOW() - INTERVAL '24 hours';
```

Compares against `fixtures/pipeline-rtt-baseline-v1.json` (when
present). Emits per-tier findings. Per-mode rollup as a sub-query.

## Phase 2 — Queue + DLQ depth

Single Redis read pass:

```
SCARD bull:transcribe-md:waiting
SCARD bull:transcribe-md:active
SCARD bull:transcribe-md:delayed
SCARD bull:transcribe-md-dlq:waiting
SCARD bull:transcribe-md:completed
SCARD bull:transcribe-md:failed
```

Compares each cardinality against the trigger thresholds in
`finding-classes.md` Phase 2.

If `bull:transcribe-md-dlq:waiting > 0`, fetch up to 5 job IDs
(via `LRANGE 0 4`) but **do not deserialize the payloads** — only
the job ID strings are read, for the operator to look up later.

## Phase 3 — Prisma N+1 (PR diff mode)

Static analysis of the PR diff. Triggered only when invoked with
"Run the performance shadow audit on PR #N" or
"Run the performance bundle check on PR #N".

The auditor walks the diff hunks and looks for these patterns
inside any added or modified `*.ts` / `*.tsx` lines:

```
for (... of ...) { await prisma.<X>.<findUnique|findFirst|findMany|...>
.forEach(async (...) => { await prisma.<...>
.map(async (...) => prisma.<...>) - flagged when wrapped in Promise.all
```

The auditor does NOT execute the code; it's a regex + AST hint
over the diff text. False positives possible (e.g. an
intentionally-tiny loop with deliberate per-row reads); the
finding's fix-hint includes a "if intentional, ignore this
finding" instruction.

## Phase 4 — Route TTFB

Reads server-side timing if `audit_logs.metadata` carries the key
`responseTimeMs` (already emitted by `withApiHandler` for selected
routes). Aggregates over the last 24h for the three high-traffic
routes:

```
GET /visits
GET /visits/[id]
GET /visits/[id]/record
```

Computes p50/p95/p99; compares against
`fixtures/route-ttfb-baseline-v1.json` (when present).

If `responseTimeMs` is not present in `audit_logs` for these
routes, emits `TTFB_NO_DATA` and notes that operator should wire
timing capture before Phase 4 produces signal. (Today, the field
may be inconsistently populated — operator hardening is part of
graduation.)

## Phase 5 — Bundle size

Reads `apps/transcribe-md/.next/app-build-manifest.json` (after a
fresh `next build`). Computes per-route gzipped JS bundle size for
the three high-traffic routes.

Compares against `fixtures/bundle-baseline-v1.json` (when
present). Emits per-tier findings. The per-PR mode of this phase
runs against a fresh build of the PR's branch + the baseline of
main; the absolute-budget mode of this phase runs against a
single build's manifest.

## Output assembly

After all phases complete, the auditor writes a single markdown
report to:

```
docs/agent-shadow-runs/performance/<UTC-timestamp>.md
```

The report has:

1. Phase coverage table at the top (which phases ran, which
   emitted NO_DATA / NO_BASELINE).
2. Findings grouped by phase, then by severity tier.
3. Summary footer with total counts:

```
Summary: 1 BLOCKING_OUTAGE · 0 BLOCKING_REGRESSION · 1 BLOCKING_BUDGET · 3 WARN_DRIFT · 4 INFO_TREND
Phases: 5/5 ran (Phase 4 emitted NO_BASELINE).
```

## Shadow vs production output

Per `activation-criteria.md` graduation criteria — shadow output
goes to `docs/agent-shadow-runs/performance/`. Production output
(post-graduation) will go to `docs/performance-reports/`. The
agent reads its own status from this file's frontmatter (or from
`README.md`'s status block) and routes the output accordingly.
