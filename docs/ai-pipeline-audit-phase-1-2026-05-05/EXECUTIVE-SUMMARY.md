# AI Pipeline Quality Audit — Phase 1 (Structural)

**Date:** 2026-05-05
**Scope:** `apps/transcribe-md/src/worker/*` + `packages/ai/src/*`
**Method:** Read-only audit. No model calls, no test runs.
**Mode:** Quality > cost. Cost is not a recommendation axis.

---

## Headline numbers

- **Total sub-findings:** 69 across 10 domains
- **Severity breakdown:**
  - **Q0 (quality-blocking):** 5
  - **Q1 (significant headroom):** ~19
  - **Q2 (minor improvement):** ~30
  - **Q3 (nice-to-have / positive observations):** ~15

The pipeline is well-architected at the structural layer: PR-D
guards, allowlist filters, retry-on-schema-fail, T-M13
checkpoint resumability, audit-row emit on rejections, and
Promise.allSettled L7 fan-out are all the right patterns. The
quality headroom is concentrated in:
1. Wiring deterministic safety backstops that are shipped but
   not called
2. Allocating the strongest model where it matters
3. Specialty-aware structured outputs for pilot specialties
4. Context propagation across late layers

---

## Top 3 highest-impact recommendations

### 1. Wire `validateRxDose` into L7c — and plumb patient context through

The deterministic dose-range validator from Round 3 PR-D is
**inert in production**. `grep -rln validateRxDose` finds the
function only in tests, docs, and the AI package's index;
nothing in the worker calls it. The safety floor that the audit
finding A06-P0-004 was supposed to provide isn't running.

A single Medium-scope PR fixes this: pull patient (DOB +
weight + allergies) into the worker's visit fetch, thread
into L7c, parse the model's strength/sig into mg/day, run
`validateRxDose` after the model output, append warnings,
emit corresponding audit rows.

This is the highest-impact single fix in the audit.

### 2. Use Opus 4.7 on L4 SOAP gen, L5 critique, and L7c Rx safety

Every layer in the pipeline today calls Sonnet 4.6. Opus 4.7
isn't called anywhere — the pipeline is structurally capped at
the second-strongest-model tier on layers where the strongest
model would catch substantively more:
- L4 SOAP — the doctor-facing artifact
- L5 critique — the second-opinion / audit pass
- L7c Rx — drug-drug interactions, contraindications,
  allergy-cross-reactivity

The fix is three one-line model-constant changes plus a
companion PR extending `pricing.ts` to compute cost per model
(today's hardcoded Sonnet pricing would log Opus calls
incorrectly otherwise). Small total scope, high quality
ceiling lift.

### 3. Specialty-aware structured outputs for psychiatry, cardiology, pediatrics

The L3 entity schema is specialty-blind. A psychiatrist
verbally completing a PHQ-9 with a patient gets the score as
free-text in `assessment_discussed`, not as a structured
field. Same for GAD-7, MSE components, suicide-risk
assessment, NYHA class, ejection fraction, pediatric growth
percentiles. The pilot specialties literally cannot trend their
canonical outcome measures across visits today.

The fix is a per-specialty L3 schema extension plus matched L4
rendering. Larger scope (best split per specialty) but unlocks
the specialty-pilot value proposition.

---

## Phase 2 recommendation: build the synthetic eval suite

**Recommend Phase 2 next, NOT a fix-pack first.**

Reasoning: most of the recommendations here change prompts,
schemas, or model selection. Without a regression suite, every
fix is a fingers-crossed deploy. The existing pipeline tests
(`__tests__/`) cover Zod schema correctness but not end-to-end
output quality.

Phase 1 surfaced 15 high-leverage scenarios that Phase 2
should target:

1. Pediatric Rx dose stress test
2. Penicillin allergy + amoxicillin Rx
3. Conflicting allergy claims
4. Bilingual code-switching visit
5. 3-speaker pediatric (caregiver-mediated) visit
6. Single-speaker audio uploaded as conversation
7. Heavy-accent / low-confidence audio
8. Psychiatry visit with verbal PHQ-9
9. Cardiology visit with echo + stress test
10. Visit with prompt-injection attempt
11. Empty / silent audio (positive control)
12. Differential / rule-out mention
13. Negation / ROS-negative documentation
14. Long visit (45 min, multi-comorbidity)
15. Anthropic content-moderation refusal candidate

Each gets a canonical expected output (or expected-failure-
with-audit-row), a scoring rubric, and a regression target.
The eval suite then becomes the gate that lets fix-packs ship
with confidence — including the Opus 4.7 upgrade, where we'd
otherwise be guessing whether quality actually moved.

If Kasra prefers a fix-pack first, Fix-pack 1 (safety floors —
including `validateRxDose` wiring) is the lowest-risk batch
and should ship regardless of the eval-suite timing. See
`findings/10-recommendations.md` for the full PR sequence.

---

## Estimated improvement potential

If all Q0 + Q1 findings are addressed:

- **Pediatric Rx safety:** dramatically improved (deterministic
  validator + peds-aware prompt + patient-context plumbing)
- **Psychiatry SOAP fidelity:** significantly improved
  (structured PHQ-9/GAD-7/MSE/safety + Opus 4.7)
- **Cardiology SOAP completeness:** significantly improved
  (echo/stress/Holter coding + NYHA/EF structure)
- **Multilingual / accent / mode-mismatch robustness:**
  significantly improved (language detection, confidence
  surfacing, mode-detection redirect)
- **Coding accuracy:** moderately improved (allowlist
  expansion, confidence floor, specificity guardrail)
- **Critique reliability:** significantly improved (Opus 4.7,
  red-flag enumeration, temperature tightening)
- **Run-to-run consistency:** significantly improved
  (temperature tightening + few-shot exemplars + tool-use mode
  for JSON layers)

Qualitative summary: **significant** improvement potential
across the safety, accuracy, and specialty-fit dimensions. The
pipeline is shippable today; the recommendations turn it from
"shippable" into "competitive."

---

## Where this audit ends

This is **Phase 1 (structural)** — read-only review of code
and prompts. Phase 2 (synthetic eval suite) is recommended
next. Phase 3 would be live-traffic measurement (sample real
visits, score against the eval rubric, identify drift) once
the pilot is live.

Audit directory: `/opt/meddoc-pro/docs/ai-pipeline-audit-phase-1-2026-05-05/`

| File | Findings | Domain |
|---|---|---|
| `findings/01-prompt-quality.md` | 11 | Prompt drift, examples, contradictions |
| `findings/02-failure-modes.md` | 13 | Degraded-input scenarios |
| `findings/03-specialty-fit.md` | 8 | Per-specialty alignment |
| `findings/04-model-allocation.md` | 4 | Where Opus 4.7 is warranted |
| `findings/05-prompt-delimiter-coverage.md` | 5 | Post-PR-J injection coverage |
| `findings/06-output-validation.md` | 9 | Schemas, retries, deterministic backstops |
| `findings/07-context-flow.md` | 6 | Cross-layer info propagation |
| `findings/08-determinism-and-temperature.md` | 6 | Per-layer temp + reproducibility |
| `findings/09-error-handling.md` | 7 | 429 / 5xx / refusal / timeout paths |
| `findings/10-recommendations.md` | synthesis | Prioritized roadmap + PR sequence |
