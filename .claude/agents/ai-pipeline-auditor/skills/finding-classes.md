# Finding classes — AI Pipeline Auditor

> **Status: design only.** Concrete numeric thresholds shown
> here are **initial proposals**; baselines come from the
> activation seed sample (first 100 READY visits) and replace the
> proposed thresholds in the auditor's first published baseline.

## Severity definitions

| Severity | Meaning | Operator action expected |
|---|---|---|
| **P1** | Active production risk: cost runaway, quality cliff, eval coverage gap on shipped code, sustained fallback rate. | Same-day investigation. Block further changes to the affected layer until resolved. |
| **P2** | Drift / hygiene: cost or latency drift below P1 thresholds, eval staleness, audit-row gap. | Triage within the week. May indicate a P1 in formation. |
| **P3** | Code-quality / future-risk: dead model assignments, prompt-hash explosion, hardcoded specialty. | Backlog. Resolve when the affected area is being touched. |

## Per-finding shape

Every finding emits these fields. All are mandatory:

```json
{
  "severity": "P1",
  "phase": 4,
  "layer": "L1",
  "metric": "transcription_provider_fallback_rate_24h",
  "observed": 0.084,
  "expected": { "max": 0.05 },
  "window": { "start": "<UTC>", "end": "<UTC>" },
  "sample_count": 178,
  "title": "Whisper-fallback rate sustained above 5% (8.4% over last 24h)",
  "what_the_data_says": "...",
  "why_it_matters": "...",
  "suggested_investigation": "...",
  "closure_criteria": "fallback-rate < 2% sustained over 7 days"
}
```

The `title` is one line, severity-grouped at the top of the
report; the prose fields are the per-finding drilldown. No
PHI, no `<visit-id>` lists in the title — those go in the
drilldown if they aid investigation.

## P1 — active production risk

### P1.1 Cost runaway

**Trigger.** Any layer's per-visit cost exceeds 2× the baseline
median for >5 consecutive visits.

**Why P1.** A 2× cost spike on a hot layer is either (a) a runaway
retry loop, (b) a context-window blowup, or (c) a provider
pricing change none of us noticed. Each scenario warrants
same-day investigation; left to roll, the monthly cost surprise
is multiplicative.

**Closure.** Per-visit cost back within 30% of baseline median for
5 consecutive visits.

### P1.2 Quality cliff

**Trigger.** Accepted-rate drops >25% week-over-week on any layer
with a defined accepted-rate proxy (SOAP edit-distance, Rx
override, ICD bump).

**Why P1.** Accepted-rate is the closest pre-pilot signal we have
to "doctor finds the output usable." A 25% week-over-week drop
is usually a model-version change, a prompt regression, or an
upstream input-quality issue. None can wait.

**Closure.** Accepted-rate within 5% of prior week's level for 7
consecutive days.

### P1.3 Eval coverage gap on shipped code

**Trigger.** A model assignment present in `model-client.ts` (or
equivalent) has zero eval fixtures associated.

**Why P1.** "Zero coverage" means a change to that assignment is
shipped blind. The first time we know it regressed is when the
doctor complains.

**Closure.** Eval suite created with at least the per-layer
minimum fixtures (TBD per layer at activation; likely ≥10 for
clinical layers and ≥3 for utility layers).

### P1.4 Provider fallback rate spike

**Trigger (sustained).** Fallback rate (Whisper invocations vs.
total L1+L1b invocations) > 5% sustained over 24h.

**Trigger (burst).** > 10 fallbacks in any 1h window.

**Trigger (secondary failure).** Both Deepgram + Whisper fail in
the same visit — every occurrence regardless of rate.

**Why P1.** Sustained fallback signals a Deepgram outage or an
audio-quality regression upstream (e.g. a browser update broke
the recording MIME). Burst is a partial outage. Secondary
failure means a visit can't transcribe at all — a doctor's
work is blocked.

**Closure.**
- Sustained → fallback rate < 2% for 7 consecutive days
- Burst → no further bursts in 24h after operator-confirmed fix
- Secondary failure → root-caused + a regression test added

## P2 — drift / hygiene

### P2.1 Cost drift

**Trigger.** Per-layer per-visit cost rolls 30% above baseline
median, sustained over 7 days, but below the P1 2× threshold.

**Why P2.** Slow cost creep is usually a "fine-tuning" change
that compounded — a retry-budget bump, a context-window
expansion, an additional cache-disabled call path. Worth
fixing before it tips P1.

**Closure.** Cost back within 15% of baseline for 7 consecutive
days.

### P2.2 Latency drift

**Trigger.** Per-layer p95 latency rolls 50% above baseline,
sustained over 7 days.

**Why P2.** Latency drift is a UX cliff before it's a cost
cliff. A doctor waiting 12s for a transcription that used to
take 6s churns the queue + frustrates everyone.

**Closure.** p95 latency within 20% of baseline for 7
consecutive days.

### P2.3 Eval staleness

**Trigger.** Any eval set unrun for > 30 days.

**Why P2.** Stale evals mean we have no signal on whether the
last 30 days of changes regressed quality. Re-running is
cheap; the cost of a regression that wasn't caught is not.

**Closure.** Eval set re-run within the window.

### P2.4 Audit-row gap

**Trigger.** A visit reaches `status=READY` without the expected
audit_logs rows (`SOAP_GENERATED`, `RX_DRAFTED` per layer).

**Why P2.** Audit-row gaps are the upstream signal of compliance
findings. The HIPAA §164.312(b) story is "every PHI mutation
audited"; if a layer is shipping output without an audit row,
we're a sweep away from a compliance incident.

**Closure.** Per-layer audit emit point fixed + backfill of
missing rows for affected visits (or accept the gap with an
explicit waiver in `docs/COMPLIANCE_REGISTER.md`).

### P2.5 Token-count anomaly

**Trigger.** Any layer's input or output token count drifts
outside the expected range (P1 baseline ±50%).

**Why P2.** Token-count anomalies usually mean (a) a prompt
template change wasn't caught, (b) an unexpected context blob
got concatenated (regression), or (c) the provider's tokenizer
behavior changed under us (rare but real).

**Closure.** Token count back in band for 7 consecutive days OR
operator-confirmed expected change documented in commit history.

### P2.6 Mid-pipeline failure spike

**Trigger.** Visits transitioning to `status=FAILED` within a
specific layer (read from `audit_logs` `errorCode` or
`reviewReason`) > 5% over 24h.

**Why P2.** A specific layer failing at a higher rate than the
pipeline average is a layer-specific regression; the doctor
sees it as "my visit got stuck at L4 again."

**Closure.** Layer-specific failure rate back below 2% over 7
consecutive days.

## P3 — code-quality / future-risk

### P3.1 Dead model assignments

**Trigger.** A model name in code that hasn't been called in 30+
days.

**Why P3.** Dead assignments accumulate. A future operator
reads the code, assumes the assignment is live, and either
mistunes it or fails to remove it during a cleanup. Tagging as
P3 captures it for the next cleanup cycle.

**Closure.** Either remove the assignment or document why it
exists (e.g. dev-fixture path, fallback for a provider's
beta-tier).

### P3.2 Prompt-hash explosion

**Trigger.** A layer producing > 10 distinct `promptHash` values
per week.

**Why P3.** > 10 distinct hashes / week suggests the prompt is
being mutated dynamically (per-visit string interpolation
without a stable template). Fine in some cases (specialty-
specific overlays) but should be consciously templatized so
hash → variant is auditable.

**Closure.** Prompt templatized + hash → variant mapping
documented in code comment.

### P3.3 Hardcoded specialty

**Trigger.** A layer that should branch on specialty but doesn't
— detected via a per-specialty accepted-rate spread > 30%
(specialty A accepted at 90%, specialty B at 55%, etc.) on the
same model + same prompt.

**Why P3.** A 30%+ spread on the same prompt usually means the
prompt is implicitly specialty-A-shaped + specialty B is
getting suboptimal output. Worth a specialty-aware variant.

**Closure.** Specialty-aware branch added OR explicit
documentation that the spread is acceptable.

### P3.4 Orphan AuditAction

**Trigger.** AuditAction enum value present in the Prisma enum
that hasn't been emitted in 30+ days.

**Why P3.** Same shape as dead model assignments — if it's not
being emitted, either remove it or document the reason it's
kept (e.g. "emitted only on quarterly admin actions"). Reduces
the "what does this enum value mean" surface for future
contributors.

**Closure.** Action removed OR purpose documented in the enum's
inline comment.

### P3.5 Confidence-score column unused

**Trigger.** `confidenceScores` (or any column the pipeline
populates) is NULL on > 90% of recent READY visits.

**Why P3.** Suggests the layer that's supposed to write the
column isn't actually doing so. Either the pipeline is missing
a step or the column is dead.

**Closure.** Either fix the layer to populate the column, or
remove the column.

## What's NOT a finding

The auditor explicitly does NOT emit findings for:

- **Wording changes to prompts.** Subjective. Out of scope.
- **Model preferences ("Sonnet is better than Haiku for this").**
  The auditor surfaces accepted-rate by model + visit shape; it
  doesn't recommend a swap.
- **Doctor edit patterns.** The phase 5.x edit-tracking pipeline
  has its own surface; this auditor sees only the metadata
  (edit distance, confidence, etc.), not patterns.
- **Free-text content quality.** This is doctor-judgment
  territory; the auditor doesn't read body text.
- **Performance optimization opportunities.** "Layer L4 could
  cache this prompt prefix" is engineering work, not an audit
  finding.
- **Visits in non-READY states.** Mid-pipeline visits don't
  carry the full audit trail yet; the auditor only inspects
  READY rows. Stuck-visit detection lives in the QA agent +
  T-M16.4 stuck-visit UI banners.

## Reading the report

The aggregated markdown report is severity-grouped:

```
## P1 — active production risk (N)
  - <title> — phase X — layer L<n> — metric <name>
  - ...
## P2 — drift / hygiene (N)
  - ...
## P3 — code-quality / future-risk (N)
  - ...
## NO_DATA + SCHEMA_GAP (informational)
  - ...
```

A clean run produces "0 P1 / 0 P2 / 0 P3" + a list of NO_DATA
informational entries. Reports retain forever (compliance
trace); the operator references them when investigating
quarterly cost drift or doing post-mortem on a quality
regression.
