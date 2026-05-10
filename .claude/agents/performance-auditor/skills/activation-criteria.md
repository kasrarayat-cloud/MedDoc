# Activation criteria — Performance Auditor

> **Status: SHADOW MODE** at file creation in
> `agent/performance-auditor-v1`. Runs against the live system; output
> routes to the shadow path until graduation.

## Shadow mode (current)

### Shadow output contract

| Field | Value |
|---|---|
| **Output path** | `docs/agent-shadow-runs/performance/<UTC-timestamp>.md` |
| **Format** | Markdown, structured per `methodology.md` phase order; phase-coverage table at the top. |
| **Severity behaviour** | Preserved. `BLOCKING_*` findings (e.g. DLQ depth > 100) stay `BLOCKING_*` — shadow only relocates the report. |
| **Action coupling** | None. Shadow reports never trigger automated action; operator reads + decides. |
| **Retention** | One file per run; per-month subdirs once the directory grows past ~30 reports. |

### Why a separate path

A future production path (`docs/performance-reports/…`) is
reserved for runs that have baseline tables baked from real
traffic. Shadow runs that report against unbaselined or sparsely
baselined data should not be mistaken for canonical performance
records.

## Hard gate (for graduation)

The agent produces real signal in shadow today, but graduation to
a production-blocking output path requires meaningful baselines.

```
SELECT COUNT(*)
FROM transcribe_visits
WHERE status = 'READY'
  AND "deletedAt" IS NULL
  AND "uploadedAt" >= NOW() - INTERVAL '14 days';
```

**Threshold:** `count >= 200`.

### Why ≥200 visits over 14 days

- **Below 200 visits:** Per-route p95 + per-layer p99 rollups have
  too much variance. A single 30-minute Anthropic latency excursion
  (already happened twice in 2026-Q1) can skew p95 by 8-15%.
  Findings would be noise.
- **14-day window:** Captures weekly + intra-week variation
  (Monday-vs-Friday traffic, after-hours vs business-hours).

The threshold is a soft floor, not a hard cap. Signal quality
keeps improving up to ~1000 visits / month. Activation at the
floor is fine; the first reports just publish weaker baselines
that the next runs tighten.

## Pre-activation safe operations (running today in shadow)

These produce real findings against shadow output even before the
hard gate is met:

### Queue + DLQ depth (Phase 2)

Reads Redis SET cardinalities for `bull:transcribe-md:waiting`,
`bull:transcribe-md:active`, `bull:transcribe-md:delayed`,
`bull:transcribe-md-dlq:waiting`. Surfaces:

- **Waiting depth > 50** — workers may be overloaded (warn).
- **DLQ depth > 0** — at least one job exhausted retries (always
  worth reading).
- **DLQ depth > 100** — pipeline is broken; likely worker crash
  loop or upstream provider outage (BLOCKING_*).

These signals are **today-runnable** — they don't depend on
historical baselines.

### Prisma N+1 on diff (Phase 3)

PR-time static analysis. Reads the diff, looks for in-loop
Prisma calls. Emits findings for shapes like:

```ts
for (const x of xs) { await prisma.y.findUnique({ where: { id: x.id } }) }
```

These findings are also **today-runnable** — they're per-PR, no
baseline needed.

### Bundle size delta (Phase 5)

PR-time analysis. Reads the Next.js `.next/app-build-manifest.json`
after a `next build`. Compares the per-route bundle size against a
baseline JSON committed at `fixtures/bundle-baseline-v1.json`. If
the baseline doesn't exist yet, emits `NO_BASELINE` with the
current measurement — operator commits the file to bake the
baseline.

## Graduation criteria (shadow → production)

Graduation requires ALL of:

1. **Hard gate met** — ≥200 visits over a 14-day window.
2. **Baselines baked** — `fixtures/pipeline-rtt-baseline-v1.json`,
   `route-ttfb-baseline-v1.json`, `bundle-baseline-v1.json` all
   populated.
3. **One full shadow report reviewed by operator** — operator
   confirms the report shape is acceptable for the
   production-path audience.
4. **Operator approval** — explicit "graduate the performance
   auditor" instruction. Edit `README.md` + this file's status
   block in the same PR.

Until all four are done, the agent stays in shadow.
