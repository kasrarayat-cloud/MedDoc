# Activation criteria — AI Pipeline Auditor

> **Status: design only.** This document describes when the
> agent is allowed to run + what activation involves.

## Hard gate

The agent cannot produce signal until the underlying data has
shape. **The activation gate is:**

```
SELECT COUNT(*), COUNT(DISTINCT "userId")
FROM transcribe_visits
WHERE status = 'READY' AND "deletedAt" IS NULL;
```

**Threshold:** `count >= 20 AND distinct_user_count >= 3`.

### Why ≥20 visits, ≥3 doctors

- **Below 20 visits:** Median + p95 cost / latency rollups have
  too much variance. A single outlier visit (long audio, retry
  cascade) skews everything. Findings would be noise.
- **Below 3 doctors:** Per-doctor specialty/prompt variance
  dominates. The auditor's specialty-spread phase needs at least
  3 distinct doctors (typically across at least 2 specialties)
  to compute a meaningful spread.

The threshold is a soft floor, not a hard cap. Signal quality
keeps improving up to ~100 visits across ~10 doctors. Activation
at the floor is fine; the first reports just publish weaker
baselines that the next runs tighten.

## Pre-activation safe operations

These can run **before** the gate is met. They produce no
findings — only "agent can run" / "agent is blocked because X"
status:

### Schema sanity check (Phase 0 standalone)

Reads `packages/db/prisma/schema.prisma` + queries `\d
transcribe_visits` etc. against the live DB. Confirms every
column the auditor depends on (`data-sources.md` §1) exists.

**Acceptance.** Zero `SCHEMA_GAP` markers. If any column is
missing, surface as a real finding (regardless of activation
gate) — schema gaps block the eventual activation run.

Example output (pre-activation):

```
schema-ok: transcribe_visits (12/12 columns present)
schema-ok: ai_calls (10/10 columns present)
schema-ok: audit_logs (7/7 columns present)
schema-ok: api_usage_events (8/8 columns present)
SCHEMA_GAP: eval_runs table does not exist (see data-sources.md §3)
```

### Eval-suite presence check

Reads `apps/transcribe-md/scripts/llm-mdm-smoke.ts` + future
suites under `packages/ai/eval-suites/`. Reports per-layer
coverage (count of fixtures + last-modified date).

**Acceptance.** Pre-activation, partial coverage is OK; the
report flags layers without coverage so the eval-suite-build
backlog stays prioritized.

### Pipeline shape sanity

Reads `apps/transcribe-md/src/worker.ts` + per-layer files at
`apps/transcribe-md/src/worker/layers/*.ts`. Confirms the layer
list the auditor expects (L1, L1b, L2, L3, L4, L5, L6, L7) is
the actual layer list. If a layer was added or removed without
this doc updating, surface.

**Acceptance.** Layer list matches the auditor's expectations.
Drift is a doc bug, not a finding — fix the doc.

## Activation runbook

When the hard gate is met (operator confirms via the SELECT
above), activation is the following sequence:

### Step 1 — Build baseline tables

Run a 100-visit baseline pass against the activation seed
sample (the first 100 READY visits). This produces:

- `fixtures/cost-baseline-v1.json` — per-layer median + p95
  cost; per-layer per-provider rollups
- `fixtures/latency-baseline-v1.json` — per-layer median + p95
  latency
- `fixtures/accepted-rate-baseline-v1.json` — per-layer
  accepted-rate (with sample-count caveat for low-volume
  layers)
- `fixtures/specialty-spread-baseline-v1.json` — per-layer
  per-specialty accepted-rate spread

Bake these into the auditor's expected-band defaults. The
absolute thresholds in `finding-classes.md` (30%, 50%, etc.)
remain — they're **percentage drifts from baseline**, so the
baseline is the load-bearing input.

### Step 2 — Wire eval-run telemetry

Pick one of the two options in `data-sources.md` §3 (new
`eval_runs` table OR hand-rolled JSON snapshots). Document the
chosen path in this file under "Eval telemetry shape (chosen)".
Implement the auditor's eval-coverage phase against that shape.

### Step 3 — Author scripts

Per `methodology.md`'s phase list:

```
scripts/audit-phase-0-schema.mjs
scripts/audit-phase-1-correctness.mjs
scripts/audit-phase-2-cost.mjs
scripts/audit-phase-3-eval-coverage.mjs
scripts/audit-phase-4-fallback.mjs
scripts/audit-phase-5-prompt-drift.mjs
scripts/audit-phase-6-model-assignment.mjs
scripts/audit-phase-7-orphans.mjs
scripts/audit-all.mjs        ← orchestrator (mirrors qa-agent's sweep-all.mjs)
scripts/lib/audit-base.mjs   ← shared helpers (DB connection, NDJSON emit, etc.)
```

Pattern matches `qa-interaction-auditor/scripts/` shape — one
phase script per file + one orchestrator. NDJSON output stream
+ a final aggregated markdown report at
`docs/ai-pipeline-audit-reports/<UTC-timestamp>.md`.

### Step 4 — Add `SKILL.md`

Create `SKILL.md` in this directory with:

```yaml
---
name: ai-pipeline-auditor
description: Audits the QuillMD AI pipeline (transcribe → SOAP → coding → Rx) for cost / quality / coverage / model-assignment drift. Read-only against transcribe_visits + ai_calls + audit_logs + eval results. PHI-safe: structured fields only, never reads transcript / SOAP body.
---

# QuillMD AI Pipeline Auditor

## Identity

I am the QuillMD AI Pipeline Auditor. ...
```

Mirror the qa-interaction-auditor's SKILL.md shape. The skill
system reads the frontmatter on session start; its presence is
how Lead becomes able to invoke this agent.

### Step 5 — Add a Postgres read-only role (defense-in-depth)

Create a Postgres role (`ai_pipeline_auditor`) with SELECT-only
permissions on the tables in `data-sources.md` §1. Update the
agent's connection to use that role's credentials. Even though
all queries are SELECT, having the role enforced is the right
posture; a typo in a future query that accidentally writes
fails immediately rather than producing a partial mutation.

### Step 6 — Flip status

Update `.claude/agents/README.md` to flip this agent from
DORMANT to active. Update this document's status block at the
top to reflect the activation date + the operator who
activated.

### Step 7 — First report

Run `scripts/audit-all.mjs` with `--baseline-build` flag (only
on first run) to bake the baselines + produce the first audit
report. Review the report; ship as
`docs/ai-pipeline-audit-reports/v0-baseline-<UTC>.md`.

## Pre-pilot polish backlog

These items are captured here so the pre-activation scope is
clear and future-Kasra has a tracked list. None are
BAA-blocking.

1. **Build per-layer baseline cost table** — needs real visits
   to derive (Step 1 above). Captured at design time so the
   activation gate doesn't surprise.
2. **Build per-layer expected-latency table** — same shape,
   separate file.
3. **Wire eval-run telemetry into a queryable shape** — pick
   between new `eval_runs` table vs. hand-rolled JSON snapshots
   (Step 2 above).
4. **Author the per-phase audit scripts** — eight phase
   scripts + one orchestrator (Step 3). Implementation-only;
   methodology is already designed.
5. **Add the agent's own walker for "is the schema the agent
   depends on still in shape?"** — analogous to the qa-agent's
   site-map.md sanity check. Keeps the auditor honest if the
   schema drifts.
6. **Postgres read-only role** — defense-in-depth; SELECT-only
   role for the auditor's connection (Step 5).
7. **Eval suite for at least one layer per group** — clinical
   layers (L4, L5) need explicit evals before the
   eval-coverage phase emits non-trivial findings. The Phase
   5.2 SOAP Coding Coach Path-C smoke is the prior art.
8. **Specialty taxonomy lookup** — `transcribe-md/src/lib/
   specialties.ts` has 8 hardcoded entries. The auditor's
   specialty-spread phase joins on `transcribe_visits.specialty`;
   if the taxonomy expands or moves to a DB table, the audit
   query needs to follow.

## What activation does NOT require

- **A BAA from any new vendor.** The auditor uses existing data
  + existing models; no new vendor relationship.
- **A schema migration.** All required columns exist as of
  PR-L follow-up (`transcriptionProvider`,
  `TRANSCRIPTION_PROVIDER_FALLBACK` enum) + the existing
  `errorDetails` (T-M17.1) and `audioConfidenceStats`
  (Round 3 quality fix-pack Q0-5) columns. The only schema
  question is `eval_runs` — Step 2 above resolves it.
- **A cost budget approval.** The auditor's run is itself
  ~zero-cost (a few dozen SELECT queries). It does NOT itself
  call any AI provider. Operator can run it without budget
  worry.
- **A new container.** The auditor runs as a one-off Node
  script (mirrors the qa-agent pattern). No long-running
  process; spawned by the operator on demand.

## Decision log (filled at activation)

| Date | Decision | Rationale |
|---|---|---|
| TBD | Eval telemetry shape | (eval_runs table vs JSON snapshots) |
| TBD | Activation operator | (who pressed the button) |
| TBD | Activation seed sample size | (default 100; tune up if noisy) |
| TBD | Postgres role created | (defense-in-depth) |
| TBD | First baseline run | (sha + report path) |

When activation lands, fill the rows. Each row is a one-line
summary; the linked PR / commit carries the detail.
