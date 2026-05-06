# AI Pipeline Auditor

> **Status: DORMANT (designed, not activated).** This agent ships
> as a design artifact only — directory structure, methodology,
> finding-class taxonomy, and activation criteria. **No
> `SKILL.md` is present**, which means Lead cannot accidentally
> invoke this agent via the skill system. Activation is an
> explicit operator action after the pilot-data threshold below
> is met. See `skills/activation-criteria.md`.

A planned agent that audits the QuillMD AI pipeline (transcribe →
SOAP → coding → Rx → referral → patient-summary) for
correctness, cost efficiency, eval coverage, and model-assignment
appropriateness. Designed to run **read-only against the live
database** + ai_call telemetry + eval-suite results.

## Why a separate agent (not part of qa-interaction-auditor)

`qa-interaction-auditor` walks UI surfaces — clicks, forms, audit
rows, DB diffs after click. The bugs it catches are
**front-end-shaped** (orphan dispatchers, pretend-success
fallbacks, parser/renderer mismatches). It runs Playwright in a
headless browser and never reads ai_call telemetry.

This agent is **back-end-shaped**. It reads:

- `transcribe_visits` — pipeline state per visit (status, costs,
  `transcriptionProvider`, `soapVersion`, `needsReview`,
  `reviewReason`)
- `ai_calls` — per-call telemetry: provider, model, `promptHash`,
  `latencyMs`, `costUsdCents`, success, errorCode
- `audit_logs` — action stream (`SOAP_GENERATED`, `RX_DRAFTED`,
  `TRANSCRIPTION_PROVIDER_FALLBACK`, etc.)
- `api_usage_events` — provider-level cost rollups for budget vs.
  actual reconciliation
- `eval_runs` (or wherever LLM-as-judge results land — see
  `data-sources.md` §3) — per-eval-set pass rates over time

Different surface, different skills, different findings. One
agent per shape keeps the SKILL.md / methodology / reporting
format coherent.

## What it audits (high level — see `skills/` for detail)

- **Per-layer correctness drift.** Each pipeline layer (L1, L1b,
  L2, L3, L4, L5, L6) has expected output shape, expected cost
  range, expected latency range. Auditor surfaces drift.
- **Cost analysis.** Total cost per visit vs.
  Anthropic/OpenAI/Deepgram budget; cost-per-output-quality
  (cents per accepted SOAP, cents per accepted Rx). Drift > 30%
  is a P2 finding; drift > 100% sustained is P1.
- **Eval coverage.** For each model assignment, what's the eval
  set size + last-run pass rate? Eval staleness (>30 days since
  last run) is P2.
- **Model-assignment review.** When a layer's accepted-rate
  drops, is the right model assigned? Auditor doesn't pick the
  model; it surfaces the gap so a human decides.
- **Prompt drift detection.** Auditor doesn't review wording
  (subjective). It tracks `promptHash → accepted-rate` over time;
  a prompt change that drops accepted-rate >10% is P1.
- **Provider fallback rate.** Whisper-fallback rate sustained
  above 5% over 24h is P1 (signal of Deepgram outage or audio
  quality regression).

Full taxonomy at `skills/finding-classes.md`.

## Activation gate

**≥20 real visits across ≥3 distinct doctors** in
`transcribe_visits` with `status=READY`. Below this threshold
the agent's findings would be stylistic rather than behavioral —
not enough signal to distinguish "this is how the pipeline
behaves" from "this is what one doctor's idiosyncratic visits
look like." Until the threshold is met, the design doc is the
artifact.

When the threshold is met, the operator (Kasra) explicitly
activates by:

1. Adding a `SKILL.md` to this directory with the appropriate
   `name:` + `description:` frontmatter (Lead's skill system reads
   it on next session start).
2. Implementing the scripts in `scripts/` per the methodology
   (`skills/methodology.md` lists the per-layer audit queries and
   their expected output shapes).
3. Creating an entry in `.claude/agents/README.md` flipping this
   agent's status from DORMANT → active.

See `skills/activation-criteria.md` for the full activation
runbook + the pre-pilot polish backlog.

## How Lead WILL invoke this agent (post-activation)

Trigger phrase (when active): **"Run the AI pipeline audit"** —
mirroring the qa-interaction-auditor convention.

Same kind of NDJSON output stream + aggregated markdown report
written to `docs/ai-pipeline-audit-reports/<UTC-timestamp>.md`.

## Directory layout

```
.claude/agents/ai-pipeline-auditor/
├── README.md                      ← you are here
├── skills/
│   ├── methodology.md             ← how the auditor works
│   ├── finding-classes.md         ← P1/P2/P3 taxonomy
│   ├── data-sources.md            ← which tables/files the auditor reads
│   └── activation-criteria.md     ← when this agent is allowed to run
├── scripts/
│   └── .gitkeep                   ← empty pre-activation
└── fixtures/
    └── .gitkeep                   ← empty pre-activation
```

Mirrors `qa-interaction-auditor/` structure. The parallel layout
is intentional — future agents land in the same skeleton.

## What this agent does NOT do

- **Read free-text PHI.** Never reads `transcriptText`,
  `soapDraft` body, or audio data. Findings reference visits by
  ID; doctors investigate the underlying content. The auditor
  never summarizes free-text.
- **Block the pipeline.** Read-only. Findings surface to a
  report; the doctor / operator decides what to do. The pipeline
  itself never sees this agent.
- **Touch `apps/meddoc-pro`.** Out of scope per memory #9.
- **Pick models for you.** When a finding says "L4 accepted-rate
  dropped on Haiku for polypharmacy visits", it does NOT
  recommend "switch to Sonnet". A human reads the finding +
  decides.

## Reading order

If you're picking this up to activate it, read in this order:

1. `skills/activation-criteria.md` (am I even allowed to run this
   yet?)
2. `skills/data-sources.md` (what does the agent read?)
3. `skills/methodology.md` (how does the agent compute drift /
   coverage / cost?)
4. `skills/finding-classes.md` (what does the agent emit?)

Then implement scripts under `scripts/` per `methodology.md`.
