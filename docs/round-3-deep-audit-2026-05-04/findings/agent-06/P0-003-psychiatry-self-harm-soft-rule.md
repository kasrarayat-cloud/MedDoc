---
id: A06-P0-003
title: Psychiatry self-harm screening is a prompt suggestion, not a hard gate
severity: P0
domain: AI safety / clinical red-flag escalation
files:
  - apps/transcribe-md/src/worker/prompts/specialty-guidance.ts (lines 22-29)
  - apps/transcribe-md/src/worker/layers/05-self-critique.ts (lines 53-63, 144-162)
  - apps/transcribe-md/src/worker/layers/06-polish.ts (lines 36-99)
---

## Issue

The psychiatry-specialty workflow has zero deterministic safety checks
for suicidal/self-harm ideation. Every layer that touches the topic
relies on the model:

1. **L4 (SOAP draft)** — the psychiatry guidance string ASKS the model
   to "Document risk assessment (suicidal/homicidal ideation)
   explicitly even if negative". An ASK, not a gate.

2. **L5 (self-critique)** — has a CRITICAL severity rule for "missing
   red-flag screening" generically (line 60). Whether the auditor
   model decides a transcript without explicit SI questioning
   constitutes a missing red-flag is itself a model judgment.

3. **L6 (polish)** — `isStructurallyFixable` (lines 144-162)
   correctly flags red-flag-screening issues as UNFIXABLE, so the
   visit gets `needsReview: true` and a banner reason. Good. **But
   nothing prevents signing.** The doctor sees a banner; they can
   click sign past it.

4. **No keyword-trigger** — there is no code path that scans the
   transcript for tokens like "suicidal", "kill myself", "want to
   die", "self-harm", "cutting", "overdose", "no reason to live"
   and forces a hard-stop / surfaces a CRITICAL warning regardless
   of what the model says.

## Evidence

- `specialty-guidance.ts:22-29` — the psychiatry guidance is one
  paragraph of soft prompt text. No structured risk-assessment
  schema is required of the SOAP output.
- `05-self-critique.ts:53-63` — red-flag examples in the prompt are
  generic ("chest pain without SOB/radiation/diaphoresis screen;
  new-onset headache without red-flag questions; pediatric fever
  without hydration/activity check"). Suicidal-ideation screening is
  NOT specifically called out.
- `05-self-critique.ts:151-162` — the unfixable-classifier looks for
  the strings 'red flag' / 'red-flag' / 'screening missing' /
  'missing red'. If the L5 auditor model phrased an issue as
  "Mental status exam omits suicide risk assessment", the substring
  'red' appears nowhere — the issue routes to the FIXABLE bucket
  and L6 will silently re-render the SOAP without the screening
  question.
- The Rx warning rail (Phase 5.1) has no dedicated path for
  psychiatric-medication interactions or for benzodiazepine + opioid
  co-prescribing (a high-suicide-risk co-Rx pattern).
- No auto-attached crisis-resources blurb (988, local emergency
  numbers) in the patient-summary layer for psychiatry visits.

## Risk

P0 because the failure mode is:

> **Patient endorses passive suicidal ideation in a psychiatry visit
> → SOAP fails to document it → doctor signs the note → patient
> leaves clinic with no safety plan → adverse outcome.**

This is the textbook "AI scribe lawsuit waiting to happen". A real
clinical incident in a pilot clinic is a project-ending event AND a
patient-harm event. The smoke test does not cover psychiatry; the
specialty-catalog test only verifies that "psychiatry" exists in the
guidance dict.

The current architecture treats SI as a red-flag like any other,
which is exactly wrong: it is a **mandatory documentation element**
in psychiatry, not a discretionary one. The pipeline should refuse
to produce a SIGNED-eligible note from a psychiatry visit if SI
screening is not documented.

## Recommended Fix (plan only)

Three layered defenses:

1. **Keyword trigger** in `worker.ts` after L1 / L1b: if `specialty
   === 'psychiatry'` AND the transcript contains any of a curated
   self-harm vocabulary list (`suicidal`, `kill myself`, `want to
   die`, `end my life`, `self-harm`, `overdose [intent]`, `no
   reason to live`, `worthless`, `better off without me`, etc.),
   set `needsReview: true` with a CRITICAL banner reason that says
   *"Patient discussed self-harm. Verify safety-plan documentation
   before signing."* and emit a CRITICAL Rx-warning row (so the
   warning rail surfaces in the UI even if Rx is empty).

2. **Schema-required SI assessment field** for the psychiatry
   template: extend `ExtractedEntities` (or add a psychiatry-specific
   `mse_risk_assessment` field to the L3 entities) that is
   non-optional when `specialty === 'psychiatry'`. If empty, the
   visit cannot reach READY status — it goes to a new
   `NEEDS_RISK_DOC` state that demands the doctor manually fill it.

3. **L7e patient-summary** for psychiatry should always append a
   crisis-resources block (988, "If you are having thoughts of
   harming yourself, call or text 988 …") when the keyword trigger
   from (1) fired. Not negotiable; not driven by the model;
   appended unconditionally.

Cross-link: this overlaps with Agent 04's prompt-injection scope —
the keyword trigger above is technically a deterministic content
screen, but it's a safety floor not a security boundary.
