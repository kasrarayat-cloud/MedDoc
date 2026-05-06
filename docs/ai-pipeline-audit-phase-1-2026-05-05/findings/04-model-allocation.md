# Finding 04 — Model allocation

Per the quality-over-cost principle, this domain is exclusively
about places where a STRONGER model is warranted. The reverse
direction (downgrading) is out of scope.

---

## Current model map

| Layer | Purpose | Model | Temp | maxTokens |
|---|---|---|---|---|
| L1 | Deepgram transcription | nova-3-medical | n/a | n/a |
| L1b | Deepgram dictation transcription | nova-3-medical | n/a | n/a |
| L2 | Speaker role classification | claude-sonnet-4-6 | (default) | 2048 |
| L3 | Entity extraction | claude-sonnet-4-6 | 0.2 | 6144 |
| L4 | SOAP draft generation | claude-sonnet-4-6 | 0.2 | 8192 |
| L5 | Self-critique | claude-sonnet-4-6 | 0.2 | 4096 |
| L6 | Final polish | claude-sonnet-4-6 | 0.2 | 8192 |
| L7a | ICD-10 coding | claude-sonnet-4-6 | 0.1 | 3072 |
| L7b | CPT/E&M coding | claude-sonnet-4-6 | 0.1 | 3072 |
| L7c | Rx drafting + warnings | claude-sonnet-4-6 | 0.1 | 3072 |
| L7d | Referral letters | claude-sonnet-4-6 | 0.3 | 2048 |
| L7e | Patient summary | claude-sonnet-4-6 | 0.3 | 2048 |

**Every layer uses claude-sonnet-4-6.** Opus 4.7 is not used
anywhere in the pipeline.

---

## 04.1 — Opus 4.7 is not used anywhere; this is a structural quality cap

**Severity:** Q0 (quality-blocking ceiling)
**Layer affected:** L4, L5, L7c (primary candidates)
**Quality dimension:** accuracy, completeness, safety, specialty-fit

### What's happening today

Per the table above, every layer hits Sonnet 4.6.
`packages/ai/src/anthropic.ts:14` imports
`claudeSonnet46CostCents`; the cost calculation is hardcoded
to Sonnet 4.6 pricing.

There is no code path that calls Opus 4.7. The model parameter
is plumbed end-to-end (`model: args.model`) so the
infrastructure supports it — but no caller passes it.

### Why this is a quality issue

Opus 4.7 (the most capable model in the family per
Environment context) catches more in:
- Complex clinical reasoning (multi-comorbidity visits)
- Subtle hallucination detection during critique
- Edge cases in coding that the current allowlist filter
  doesn't reach
- Pediatric / psychiatry / cardiology where the prompt asks
  for structured score computation and risk assessment

A pipeline where the highest-stakes generation steps run on
the second-strongest model is structurally capped. Doctors
relying on the AI's clinical judgment in psychiatry suicide-risk
assessment or pediatric Rx are getting Sonnet's judgment, not
Opus's.

### Headroom

Specific layers where Opus 4.7 should be considered:

#### Layer 4 — SOAP generation (high stakes, high token budget)

This is the doctor-facing artifact. Every nuance — when to use
"Per patient, …", how to render "[not documented]", how to
phrase a differential — comes from this layer. Opus 4.7 will:
- Hold the L4 prompt's discipline rules more reliably under
  long inputs (45-min visits with 8000-token transcripts)
- Produce more clinically natural prose (matches doctor-edit
  patterns more closely)
- Catch when entities and transcript disagree (Finding 01.5)
  and handle the conflict more gracefully

**Recommendation: Opus 4.7 for L4.**

#### Layer 5 — Self-critique (the second-opinion layer)

This is the audit pass. The whole point is to catch what L4
missed. Using the same model for both the writer and the
auditor means systematic blind spots compound.

Standard practice in dual-model setups: critique uses the
stronger model. Even when the writer is also strong, having
a stronger reviewer catches more.

Bonus: with Opus 4.7 critique + tightened red-flag table
(Finding 01.3), the visit's `safe_to_sign_without_review`
boolean becomes meaningfully more reliable. Today it's a
binary based on Sonnet's own judgment — Opus would tighten
the gate.

**Recommendation: Opus 4.7 for L5. Highest single-layer ROI in this audit.**

#### Layer 7c — Rx drafting + safety warnings

Drug-drug interactions, dose ranges, allergy cross-reactivity,
contraindication detection — all come from the model's
training-time knowledge of pharmacology. Sonnet 4.6 is good;
Opus 4.7 is better and catches:
- Less-common drug interactions (e.g., SSRI + tramadol →
  serotonin syndrome)
- Subtle contraindications (e.g., metformin in CKD stage 4)
- Pediatric-specific risks (Reye syndrome with aspirin)

Combined with the deterministic dose validator backstop
(once wired in — Finding 06.5), the safety floor is much higher.

**Recommendation: Opus 4.7 for L7c.**

#### Layers where Sonnet 4.6 is the right model (no upgrade)

- **L1 / L1b** — Deepgram, not a Claude call
- **L2** — Speaker classification is a relatively shallow task;
  Sonnet handles 99% of cases. Headroom is in prompt expansion
  + sample-size bump, not model upgrade.
- **L3** — Entity extraction is structured-output with good
  schema validation + retry. Sonnet's 5% schema-fail rate
  (per `model-client.ts:30` comment) is acceptable when paired
  with the 2-retry policy. Could go to Opus for psychiatry
  specifically if the structured-score extraction (PHQ-9 etc)
  is added — but Sonnet should be sufficient for the generic
  schema.
- **L6** — Polish is a constrained edit task ("apply these
  fixes"). Sonnet is right.
- **L7a / L7b** — Coding is shallow once allowlists fire.
  Sonnet is right.
- **L7d** — Referral letters are short prose. Sonnet is right.
- **L7e** — Patient summary is constrained prose with
  Flesch-Kincaid backstop. Sonnet is right.

### Recommended fix

Three sub-PRs, each independently shippable:

1. **PR-Q1.A**: Upgrade L4 to Opus 4.7. Single-line change in
   `apps/transcribe-md/src/worker/layers/04-generate-soap.ts:17`:
   ```typescript
   const MODEL = 'claude-opus-4-7';
   ```

2. **PR-Q1.B**: Upgrade L5 to Opus 4.7. Same one-line change in
   `apps/transcribe-md/src/worker/layers/05-self-critique.ts:20`.

3. **PR-Q1.C**: Upgrade L7c (Rx drafting) to Opus 4.7. Same in
   `apps/transcribe-md/src/worker/layers/07c-rx-drafting.ts:14`.

**Critical companion change**: extend `packages/ai/src/pricing.ts`
+ `packages/ai/src/anthropic.ts` to compute cost per model. Today
the cost calculation hardcodes
`claudeSonnet46CostCents(input, output)` regardless of which model
ran. The cost-tracking will be off if Opus calls land but the
math says Sonnet — operationally minor but should be done at the
same time as the model upgrade so AiCall cost rows are accurate.

### Estimated PR scope
**Small for each layer upgrade** (one-line model constant change
+ pricing.ts extension). **Medium when bundled** as a single
"Q1 model upgrades + per-model pricing" PR.

---

## 04.2 — L2 model temperature is undefined → SDK default (~1.0)

**Severity:** Q2
**Layer affected:** L2
**Quality dimension:** consistency, determinism

### What's happening today

`02-speaker-roles.ts:138-149` calls `modelClient.complete` without a
`temperature` argument. `model-client.ts:43` documents:

> "Sampling temperature 0-1. Medical layers pin this low for
>  determinism; undefined = provider default."

Anthropic's SDK default is around 1.0 (per Anthropic docs). For
speaker role classification, that's high — confidence values may
swing run-to-run on borderline cases.

### Why this is a quality issue

L2's `lowestConfidence` drives whether the visit gets `needsReview`.
A visit running at temp 1.0 may oscillate between confidence 0.65
(needs review) and 0.75 (clean) on consecutive runs of the same
audio. Inconsistent.

### Recommended fix

Add `temperature: 0.1` to the L2 model call (matching L7a/L7b
discipline).

### Estimated PR scope
**Trivial** — one-line addition.

---

## 04.3 — Cost-table assumption breaks if Opus is added without companion update

**Severity:** Q2 (operational, not quality — but blocks Finding 04.1)
**Layer affected:** packages/ai
**Quality dimension:** observability

### What's happening today

`packages/ai/src/anthropic.ts:14, 102-105`:

```typescript
import { claudeSonnet46CostCents } from './pricing';
...
costUsdCents: claudeSonnet46CostCents(
  response.usage.input_tokens,
  response.usage.output_tokens
),
```

Always Sonnet's price, regardless of the `model` parameter.

### Why this matters for quality work

Finding 04.1 recommends Opus 4.7 in three layers. Without a
per-model cost table, every Opus call gets logged with Sonnet's
price, the AiCall + ApiUsageEvents tables drift, and the admin
dashboard shows incorrect numbers. Quality recommendations are
operationally cleaner if cost tracking matches reality.

### Recommended fix

`packages/ai/src/pricing.ts` — extend with per-model functions:

```typescript
export function claudeOpus47CostCents(input: number, output: number): number {
  // Pull cents-per-million from env: CLAUDE_OPUS_47_INPUT_CENTS_PER_M, etc.
  // Default to today's published list price.
}

export function claudeCostCents(model: string, input: number, output: number): number {
  switch (model) {
    case 'claude-opus-4-7': return claudeOpus47CostCents(input, output);
    case 'claude-sonnet-4-6': return claudeSonnet46CostCents(input, output);
    default: return 0; // unknown model → 0 (don't fabricate cost)
  }
}
```

`anthropic.ts` switches the call site to `claudeCostCents(args.model, ...)`.

### Estimated PR scope
**Small** — companion to PR-Q1 above; ship together so logs stay accurate.

---

## 04.4 — Opus 4.7 schema-fail retry could fall BACK to Opus, not stay at lower-quality model

**Severity:** Q3 (preempt before it becomes a finding once Opus lands)
**Layer affected:** model-client
**Quality dimension:** robustness

### What's happening today

`model-client.ts:74-95` retries with the same model + retry context
appended. Schema-fail rate per the comment is 5% per call.

### Why this is a future quality issue (after Finding 04.1 lands)

Once L4/L5/L7c run Opus 4.7, the retry-on-schema-fail loop should:
1. Stay on Opus on retry (the retry isn't because Opus is too
   weak — it's because the model-output format failed parsing
   and the retry context helps the model self-correct).
2. NEVER fall back to Sonnet 4.6 as a "last resort" — that
   defeats the purpose of upgrading.

The current code already does (1) correctly — same model on
retry. But this is worth documenting so future changes don't
"helpfully" add a fallback.

### Recommended fix

Comment on `model-client.ts:74` documenting the no-fallback
discipline:

```typescript
// Quality discipline: retry uses the SAME model. Never silently
// fall back to a weaker model on schema-fail — the retry context
// is the recovery mechanism, not a model-quality fallback. If
// the retry loop exhausts, propagate the failure; the worker's
// per-attempt retry budget gives BullMQ another chance with the
// same strong model.
```

### Estimated PR scope
**Trivial** — doc comment. Codify the principle.
