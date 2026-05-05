---
id: A06-P3-014
title: Patient summary "8th-grade" claim is checked but not enforced; high-grade summaries still ship
severity: P3
domain: Polish / readability claim accuracy
files:
  - apps/transcribe-md/src/worker/layers/07e-patient-summary.ts (lines 18-21, 107-117)
  - apps/transcribe-md/src/worker/layers/readability.ts
---

## Issue

L7e (patient summary) asks the model to "Aim for 8th-grade reading
level or lower" in the prompt, then computes Flesch-Kincaid grade
locally and stores the result on `confidenceScores.patient_summary
.metadata.flesch_kincaid`. **It does NOT regenerate or block when
the grade exceeds the threshold.**

```ts
// 07e-patient-summary.ts:108-117
const grade = fleschKincaidGrade(result.summary);
const flagged = grade > HIGH_GRADE_THRESHOLD;  // threshold = 10

await prisma.transcribeVisit.update({
  where: { id: input.visitId },
  data: { patientSummary: result.summary },
});

return { summary: result.summary, fleschKincaid: grade, flagged };
```

A grade-12 summary lands in the DB, the `flagged: true` propagates
to confidenceScores, the doctor MAY see a UI hint — but the
patient summary is delivered (printed, emailed, shown in patient
portal) at the high grade level regardless.

## Evidence

- `HIGH_GRADE_THRESHOLD = 10` (line 21) — the layer's own threshold
  is grade 10, not 8 (which is the prompt's target). So the layer
  flags only the *very* high-reading-level outputs and tolerates
  9-10 silently.
- The prompt comment at line 8 explicitly states: "We do NOT
  regenerate when the grade is too high — flagging is the job of
  this layer, rewriting is the doctor's (or a future T-M6.5
  auto-rewrite pass)."
- No mention in the visit-detail UI of a "patient-summary
  readability flagged" warning beyond the JSON field that may or
  may not be displayed (search for `flesch_kincaid` in the UI
  code — sparse).
- Marketing claim in `apps/marketing` (out of scope for this audit
  but noted): if a marketing page says "We deliver patient summaries
  at an 8th-grade reading level" — that's false on the failed-flag
  cases.

## Risk

P3 because:

- No clinical harm — patients can read summaries that are above
  their level, they just understand less of them.
- Health-literacy guidelines (CDC, NIH) recommend patient-facing
  materials at 6th-8th grade. A grade-12 summary on a diabetes
  diagnosis is not clinically actionable for ~half of US adults.
- The product positioning ("plain English") is undermined by
  shipping high-grade summaries silently.

## Recommended Fix (plan only)

1. **Auto-rewrite pass**: when `grade > 10`, do ONE retry of L7e
   with the prompt text:
   `"The previous summary was at grade ${grade}. Rewrite at 8th
   grade or below. Specifically: shorter sentences, common words
   instead of clinical synonyms, no abbreviations."`

2. **Threshold alignment**: lower `HIGH_GRADE_THRESHOLD` from 10
   to 8 to match the prompt target.

3. **Cap retries at 1**: if retry still produces > 10, persist the
   flagged version, set the visit's `needsReview` with reason
   "Patient summary readability above target — manual edit
   recommended."

4. **UI surface**: render the FK grade explicitly in the Extras
   tab so doctors know when to manually simplify.

5. **Anti-claim guard**: if/when marketing claims an 8th-grade
   guarantee, downgrade to "8th-grade target" until (1) ships.
