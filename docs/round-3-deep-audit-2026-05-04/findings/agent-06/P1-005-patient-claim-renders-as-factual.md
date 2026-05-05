---
id: A06-P1-005
title: Adversarial patient statements ("doctor said take 10x dose") not deterministically distinguished
severity: P1
domain: AI safety / source attribution / medication-error risk
files:
  - apps/transcribe-md/src/worker/layers/04-generate-soap.ts (lines 67-78)
  - apps/transcribe-md/src/worker/layers/02-speaker-roles.ts
  - apps/transcribe-md/src/worker/layers/03-extract-entities.ts (lines 233-273)
---

## Issue

The L4 SOAP-generation prompt has one soft instruction for source
attribution:

```
- When information came exclusively from the patient, prefix with
  "Per patient, …" so the source is clear on downstream review.
```

This is **the only mechanism** in the pipeline that distinguishes
"patient claim" from "doctor order". It is a prompt suggestion. There
is no deterministic post-processing that:

- Cross-references a "Plan" item against speaker attribution to ensure
  doctor-attributed orders only appear in the Plan.
- Flags patient utterances that propose dosing/medication changes when
  the doctor never affirmed.
- Detects "the doctor said …" (patient quoting doctor) vs. "I said …"
  (doctor speaking) for downstream rendering.

## Evidence

1. **L2 speaker map** (`02-speaker-roles.ts`) classifies speakers as
   `doctor | patient | family | other | unknown`. The classification
   is itself a Claude call (line 138). With confidence `< 0.7` the
   visit goes to needsReview (line 27, 155) — but **the SOAP is still
   generated**.

2. **L3 entity extraction** (`03-extract-entities.ts:283-296`) requires
   `evidence_quote` and `speaker` for each entity, but downstream
   layers don't preserve speaker attribution into the SOAP itself —
   the SOAP is markdown prose, not a structured object.

3. **L4 prompt** (`04-generate-soap.ts:67-78`):
   ```
   - When information came exclusively from the patient, prefix with
     "Per patient, …"
   ```
   The model's adherence is unverified. There's no postprocessing
   that scans the Plan section for medication doses and verifies
   the supporting evidence_quote came from a `speaker: 'doctor'`.

4. **Adversarial scenario from the brief**: patient says *"my last
   doctor said to take ten of them at bedtime"*. The transcript
   contains that sentence verbatim, attributed to the patient
   speaker. L3 extracts a medication entity with `evidence_quote:
   "ten of them at bedtime"`, `speaker: 'Patient #1'`. L4 may put
   "10 mg at bedtime" in the Subjective (good — attributed) OR the
   model may helpfully roll it forward into the Plan section without
   the prefix (bad — silent fabrication of an order). The pipeline
   has no defense against the second outcome.

5. **L7c (Rx drafting)** consumes the SOAP `Plan` section. If a
   patient-claimed dose ended up in the Plan, L7c will draft an
   actual prescription line. The doctor sees a finished Rx with the
   patient's claimed dose and may sign it.

## Risk

P1 (one tier below P0 because it requires both a transcription event
AND a model misattribution AND a doctor not catching it on review).
The harm if it lands is direct medication error — a 10x dose
prescription on a Sched II controlled substance is a fatal-overdose
risk on opiates, a hypoglycemic-coma risk on sulfonylureas, etc.

The pipeline's defense in depth is: (a) attribution in the prompt
(soft); (b) the doctor's review of the SOAP before signing (human);
(c) the Rx warning rail's out-of-range check (also model-generated,
see P0-004). All three layers are probabilistic.

## Recommended Fix (plan only)

1. **Speaker-attributed Plan rendering**: change L4's output schema
   from raw markdown to a structured `{ subjective: ..., plan: [{
   item: string, attribution: 'doctor' | 'inferred' | 'patient' }]
   }`. The renderer drops `attribution: 'patient'` items from the
   Plan (or surfaces them in a separate "Patient-reported intent"
   subsection that does NOT feed L7c).

2. **L7c input filter**: even with the current text-based SOAP,
   pre-process the Plan section before sending to L7c. Use the L3
   entities — for each `medications[i]` referenced in the Plan,
   verify `entities.medications[i].speaker === 'doctor'` (or empty
   for dictation/text mode). If a medication appears in the Plan
   that was attributed to the patient in L3, drop it before L7c
   sees it.

3. **Audit trail**: persist the attribution-decision per Plan item
   so the Pipeline tab can show "the doctor's plan was X; the
   patient also mentioned Y but it was not auto-prescribed."

This complements P0-004 (interaction/allergy DB). Together they
form a deterministic backstop on the Rx path.
