# Finding 08 — Determinism + temperature

For every model call, current temperature settings + whether
the choice supports clinical safety.

---

## Current temperature map

| Layer | Purpose | Temperature | Verdict |
|---|---|---|---|
| L2 | Speaker role classification | (default ≈1.0) | **TOO HIGH** — Q2 |
| L3 | Entity extraction | 0.2 | OK |
| L4 | SOAP draft generation | 0.2 | OK (could be 0.1 for tighter consistency) |
| L5 | Self-critique | 0.2 | **could be 0.1** for tighter audit |
| L6 | Final polish | 0.2 | OK |
| L7a | ICD coding | 0.1 | ✓ Right |
| L7b | CPT coding | 0.1 | ✓ Right |
| L7c | Rx drafting | 0.1 | ✓ Right |
| L7d | Referral letters | 0.3 | **too warm for billing-adjacent** — Q3 |
| L7e | Patient summary | 0.3 | OK (creative prose for patient) |

Anthropic does not expose deterministic seeds, so true
determinism is not available. Lower temperature is the best
proxy.

---

## 08.1 — L2 speaker classification has no explicit temperature → SDK default ~1.0

**Severity:** Q2
**Layer affected:** L2
**Quality dimension:** consistency, reproducibility

(Already covered in Finding 04.2 — listed here for the
temperature audit cross-reference.)

### Recommended fix

Set `temperature: 0.1` on the L2 model call.

---

## 08.2 — L5 critique at temp 0.2 — should be 0.1 for consistent audit results

**Severity:** Q2
**Layer affected:** L5
**Quality dimension:** consistency, reliability

### What's happening today

`05-self-critique.ts:133` — `temperature: 0.2`.

### Why this is a quality issue

L5 is the audit pass. The same SOAP audited twice should produce
the same critique. At temp 0.2, the model sometimes flags an
issue and sometimes doesn't. Issue counts can swing 1-2 between
runs. That oscillation drives `safe_to_sign_without_review`
between true and false on borderline visits — meaning two
runs of the same input give two different "needs review" gates.

### Recommended fix

Lower L5 to `temperature: 0.1`. Pair with the Opus 4.7 upgrade
recommendation (Finding 04.1) — strong model + low temp is
the canonical "audit pass" config.

### Estimated PR scope
**Trivial** — one-line change.

---

## 08.3 — L7d referrals at 0.3 — billing-adjacent should be tighter

**Severity:** Q3
**Layer affected:** L7d
**Quality dimension:** consistency

(Already covered in Finding 01.11 — listed here for the
temperature audit.)

### Recommended fix

Lower L7d to `temperature: 0.1`. Referral letters benefit from
deterministic phrasing.

---

## 08.4 — Anthropic doesn't expose seeds; dependence on temperature alone

**Severity:** Q3 (informational)
**Layer affected:** packages/ai/anthropic.ts (architectural)
**Quality dimension:** reproducibility

### What's happening today

The Anthropic SDK doesn't expose a `seed` parameter. Even at
temperature 0, the same prompt may produce slightly different
outputs across runs due to internal sampling stochasticity.

OpenAI's API exposes a `seed` parameter for reproducibility.

### Why this is a quality issue

For audit + investigative purposes ("why did the same SOAP
get a different critique today vs yesterday?"), we can't
deterministically reproduce a model run.

### Mitigations available today

1. Persist the full prompt + the full output in `AiCall.errorDetails`
   (we do persist on failure). Doesn't make runs reproducible
   but provides a forensic trail.

2. Anthropic does support `prompt_caching` which gives a
   different reproducibility benefit (cache identical prompts
   for X minutes). Not a determinism feature.

### Recommended fix

Document the limitation in `packages/ai/anthropic.ts` near the
temperature setting. If reproducibility ever becomes
critical, switch the relevant layer's provider to OpenAI for
the seed parameter (would require re-prompting + cost-table
updates).

### Estimated PR scope
**Trivial** — comment-only.

---

## 08.5 — Dose-validator + allowlists are deterministic; this is the right pattern

**Severity:** Q3 (positive observation)
**Layer affected:** L7a / L7b / L7c (when validators wired)
**Quality dimension:** safety

### What's happening today

ICD allowlist (L7a), CPT allowlist (L7b), and dose-validator
(L7c — once wired per Finding 06.1) provide a deterministic
floor under the model's stochastic output. This is the gold
standard for clinical-safety AI:

> Stochastic generation + deterministic validator = both
> creative output AND safety floor.

### Worth amplifying

Beyond the existing validators, three more deterministic
checks would extend the pattern:

1. **SOAP structural validator** (Finding 06.2) — checks for
   required `## Subjective / ## Objective / ## Assessment /
   ## Plan` headings.

2. **Allergy class match in L7c** (already deterministic in
   `validateRxDose`, just needs to fire — Finding 06.1).

3. **Dose-sig parser → mg/day computation** (needed for
   `validateRxDose` to do numeric checks — Finding 06.1).

Each of these is a small deterministic backstop. Together,
they push the safety floor up significantly without
constraining the creative-output side.

---

## 08.6 — Some retries inject "previous output + zod errors" — could be more aggressive on safety layers

**Severity:** Q3
**Layer affected:** model-client / L7c
**Quality dimension:** robustness

### What's happening today

`model-client.ts:74-95` retries up to 2 times on schema-fail or
JSON-parse-fail, with the previous output + zod errors injected
into the retry context.

For most layers this is the right trade-off. For safety-critical
L7c, more retries could be warranted: if the Rx output fails
schema, we'd rather burn another attempt than silently propagate
the failure.

### Why this is a (low) quality issue

After 2 retries, a SCHEMA_FAIL from L7c lets the BullMQ retry
budget take over (3 attempts × 2 schema retries = 6 model
attempts before final fail). Sufficient in practice — the
5% per-call failure rate compounded across retries gives a
~0.0001% chance of all 6 failing.

### Recommended fix

No change. The retry budget is already generous for
safety-critical layers because the BullMQ outer retry layers
on top of the schema retry.

Document this combinatorial in `model-client.ts` so future
changes don't reduce the BullMQ retries thinking it's
duplicative:

```typescript
// Quality discipline: this 2-retry budget compounds with
// BullMQ's per-job retry budget (default 3 attempts). For
// safety-critical layers (L7c Rx), the effective retry
// envelope is 3 × 2 = 6 attempts per visit before the visit
// goes FAILED. Don't reduce either side without preserving
// the combined budget.
```

### Estimated PR scope
**Trivial** — comment.
