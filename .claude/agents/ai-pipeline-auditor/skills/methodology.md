# Methodology — AI Pipeline Auditor

> **Status: design only.** Concrete query bodies + thresholds
> are deferred to activation when real pilot data exists to
> baseline against. This doc names the methodology + the metrics;
> baselines come from real visits.

## Operating principle

Read-only against the live database + ai_call telemetry + eval
results. Never invokes a pipeline run; never modifies a row.
Every per-layer audit produces one of:

- **OK** — observed value within expected band
- **DRIFT** — observed value outside expected band (severity in
  `finding-classes.md`)
- **NO_DATA** — insufficient samples to compute (e.g. fewer than
  5 visits exercised this layer this week)
- **SCHEMA_GAP** — the column / row this audit depends on doesn't
  exist or is unpopulated (a real finding — pre-flight to fix
  before the audit can run)

The agent surfaces all four; only DRIFT counts as a finding.
NO_DATA is informational; SCHEMA_GAP is a blocker.

## Audit phases

Each full run executes phases in order. Later phases depend on
earlier ones, so a SCHEMA_GAP in Phase 0 stops the run.

### Phase 0 — schema sanity

Confirms the database shape the auditor depends on still exists.
Per-table presence + per-column presence checks. Examples:

- `transcribe_visits.transcriptionProvider` (PR-L follow-up
  column) — populated for visits processed after
  2026-05-06T08:35Z; older rows are NULL (legacy, expected).
- `ai_calls.promptHash` — populated for every row from PR-N era
  forward; missing on legacy rows is a SCHEMA_GAP marker, not a
  finding.
- `ai_calls.costUsdCents` — required for cost analysis; NULL on
  any non-legacy row blocks the cost phase.
- `audit_logs.action` — enum value `TRANSCRIPTION_PROVIDER_FALLBACK`
  (PR-L follow-up) must exist in the Postgres enum or fallback-rate
  computations short-circuit.

Phase 0 emits `schema-ok` events per table or one
`SCHEMA_GAP` finding per missing column.

### Phase 1 — per-layer correctness

For each layer in the visit pipeline (L1 transcribe, L1b
dictation, L2 speaker-roles, L3 entities, L4 Rx, L5 ICD/CPT, L6
polish, L7 SOAP-render), the auditor computes:

- **Coverage:** how many visits in the audit window exercised
  this layer? (Some visits skip layers — voice_dictation skips
  L2 diarization, for example.)
- **Accepted-rate proxy:** for layers with a clear
  acceptance signal (SOAP-doctor-edit-distance, Rx-doctor-
  override, ICD-doctor-bump), the rate at which the doctor
  shipped the layer's output unchanged.
- **Output shape sanity:** does every row's output column carry
  the expected non-null fields? Empty `soapDraft` on a READY
  visit is a finding.

Per-layer baselines come from the **first 100 real READY visits**
(the activation seed sample). The first audit after activation
publishes the baseline tables to `fixtures/`.

### Phase 2 — cost analysis

Per-visit cost is the sum of `ai_calls.costUsdCents` joined to
`transcribe_visits.id`. The auditor rolls this up per layer +
per provider + per visit-type (audio_upload vs voice_dictation
vs text_notes).

Metrics:

- **Median cost per visit per provider** in the audit window vs.
  the baseline window (default: trailing 7 days vs. trailing
  30 days excluding the most recent 7).
- **Cost variance.** A layer whose cost has high variance (p95 >
  3× median) likely has a runaway path — usually a long-context
  retry that's worth investigating.
- **Cost-per-quality.** For the layers with an accepted-rate
  proxy: cents per accepted output. A layer that's cheap but
  rejected often is more expensive than a layer that's
  expensive but accepted.

Drift thresholds (initial; tune at activation):

- 30% sustained over 7 days → P2 cost drift
- 100% sustained over 24h → P1 cost runaway

### Phase 3 — eval coverage

For each layer + each model assignment, the auditor checks:

- **Eval set size.** How many fixtures in the eval suite for this
  layer + model? Below the layer's minimum (TBD per layer at
  activation) is a coverage gap.
- **Last-run staleness.** When did the eval suite last run? > 30
  days is P2 staleness.
- **Pass rate trend.** Last 5 runs' pass rate. Monotonic decrease
  > 10% across 5 runs is a P1 quality cliff.

Note: eval suites for QuillMD live at
`apps/transcribe-md/scripts/llm-mdm-smoke.ts` (Path-C smoke for
Phase 5.2 SOAP Coding Coach) + future per-layer suites that
the activation backlog plans to add. The auditor reads results
from wherever telemetry lands — see `data-sources.md` §3.

### Phase 4 — provider fallback rate

The PR-L follow-up shipped
`audit_logs.action = TRANSCRIPTION_PROVIDER_FALLBACK` rows
emitted by Layer-1 + Layer-1b when the orchestrator falls back
from Deepgram to Whisper. The auditor computes:

- **Fallback rate**: count of `TRANSCRIPTION_PROVIDER_FALLBACK`
  rows divided by count of L1/L1b invocations in the same window
- **Burst detection**: is the fallback rate spiked in a short
  window (e.g. >10 fallbacks in 1h) suggesting a Deepgram outage?
- **Sustained signal**: is the rate above the 5% threshold for
  >24h, suggesting an audio-quality regression on the input
  side?

P1 thresholds:

- Fallback rate > 5% sustained over 24h
- Burst > 10 fallbacks in any 1h window
- Whisper P1 secondary failure (both providers fail in the same
  visit) — every occurrence is a finding regardless of rate

### Phase 5 — prompt drift

For each layer, the auditor groups `ai_calls` by `promptHash` +
computes the accepted-rate per group. A new `promptHash` that
appears in the audit window is OK; a new `promptHash` whose
accepted-rate is >10% below the prior dominant hash's
accepted-rate is a P1 finding ("prompt change degraded
quality").

Note: this is the **only** prompt-quality signal the auditor
emits. Wording review is subjective and out of scope.

### Phase 6 — model-assignment review

When a layer's accepted-rate drops sustained over 7 days, the
auditor surfaces:

- Which models served this layer in the window
- Each model's accepted-rate
- Each model's cost per accepted output
- Whether a different model with a better rate exists in
  `ai_calls` for similar visit shapes

The auditor does NOT recommend "switch to model X". It surfaces
the data; a human decides.

### Phase 7 — orphan-assignment + dead-code detection

Read-only static + telemetry signals:

- Model names in code (`packages/ai/src/model-client.ts` etc.)
  that haven't been called in 30+ days → P3 orphan
- Layers with `confidenceScores` columns that are always NULL on
  recent visits → P3 (column may be unused / unpopulated)
- AuditAction enum values that haven't been emitted in 30+ days
  → P3 orphan action

## Querying conventions

- All queries use `EXPLAIN (ANALYZE, BUFFERS) OFF` so the
  auditor never burns query-planner time on ANALYZE; but every
  query carries a `LIMIT` cap matching the audit window so a
  pathological query can't lock a table.
- Audit window default: trailing 7 days. CLI flag at activation
  time will allow `--window 30d` for trend analysis.
- `transcribe_visits.deletedAt` IS NOT NULL filter applied to
  every query — the auditor never reads soft-deleted rows.
- All cost / latency rollups use **median + p95**, not mean. AI
  cost distributions are heavy-tailed; mean is misleading.

## Reporting format

Output is one NDJSON record per phase event + a final aggregated
markdown report at
`docs/ai-pipeline-audit-reports/<UTC-timestamp>.md`. The
markdown follows `qa-interaction-auditor/skills/reporting-format.md`'s
shape (severity-grouped findings + per-finding "what the data
says" + "why it matters" + "suggested investigation").

Per-finding fields:

- `severity` — P1 / P2 / P3
- `phase` — which audit phase emitted (0–7)
- `layer` — L1, L1b, L2, ..., L7, or `cross-layer` for
  pipeline-wide findings
- `metric` — the specific drift / coverage / fallback metric
- `observed` — the value observed (cost cents, fallback rate,
  accepted-rate, etc.)
- `expected` — the baseline + threshold band
- `window` — UTC start/end of the data window
- `sample_count` — how many rows the metric was computed over
- `closure_criteria` — what condition would close this finding
  (e.g. "fallback-rate < 2% sustained over 7 days" closes a
  fallback-rate P1)

## What the methodology explicitly does NOT do

- **No active probing.** The auditor never runs a fixture
  through the live pipeline to test it. Production observation
  only.
- **No PHI summarization.** Free-text fields (`transcriptText`,
  `soapDraft`) are read-only at the metadata level (length,
  presence) — never their content.
- **No model substitution recommendations.** Findings name the
  drift + the band; a human decides on remediation.
- **No automatic mitigation.** The auditor never flips an env
  var, never restarts a worker, never quarantines a visit.
  Read-only.

## Open questions for activation

These get resolved when real data lands; capturing here so
future-Lead has the question set:

1. **Layer-by-layer baseline cost table**: run a 100-visit
   sample, compute median + p95 + variance per layer, ship as
   `fixtures/cost-baseline-v1.json`. Update on cadence.
2. **Per-layer expected-latency table**: same shape, separate
   file.
3. **Eval-run telemetry shape**: `eval_runs` table doesn't exist
   yet (verify at activation). Either it lands as a new table
   or the auditor reads from a different source — see
   `data-sources.md` §3 for the open-question disposition.
4. **Activation seed sample size**: 100 visits is the proposal;
   may need to be larger for noisy layers (L4 Rx in particular
   has high specialty-driven variance).
