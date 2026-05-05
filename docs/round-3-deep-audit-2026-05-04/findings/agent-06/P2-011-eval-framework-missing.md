---
id: A06-P2-011
title: No LLM-as-judge eval framework exists in transcribe-md; quality is unmeasured
severity: P2
domain: Eval framework / regression risk
files:
  - apps/transcribe-md/tests/worker/  (no eval files)
  - apps/transcribe-md/tests/e2e/scenarios/ (smoke only)
  - apps/meddoc-pro/scripts/eval-clinical-notes.ts (different app, decommissioning)
  - apps/meddoc-pro/tests/evals/clinical-notes-phrasings.ts (different app)
---

## Issue

The audit brief lists "LLM-as-judge eval framework: bias review.
Does the judge prompt cover the right axes (faithfulness,
completeness, safety)? Are eval datasets diverse?"

A full search of `apps/transcribe-md` shows **no eval framework, no
fixture corpus, no judge prompts, no automated quality scoring**.

What exists:

- Unit tests of pure-function helpers (readability,
  speaker-catalog, edit-distance, etc.).
- E&M coding corpus (`apps/transcribe-md/src/lib/em-coding/__tests__/corpus.test.ts`)
  — this is real, useful, and rigorous (a 25+ visit fixture set
  with hand-graded MDM tier expectations) — but it covers only
  one specific feature (E&M tier classification), not the broader
  pipeline.
- A smoke test (PR #108) that walks the full UI and asserts visits
  reach READY status with non-empty SOAP bodies. Does not score
  faithfulness or completeness.

The eval scripts in `apps/meddoc-pro/` (eval-clinical-notes.ts,
eval-doc-editor.ts) belong to the now-decommissioning CRM half of
the monorepo and are out of scope per the audit brief.

## Evidence

`grep -rn "LLM.*judge\|judge.*prompt\|faithfulness\|completeness.*score" apps/transcribe-md` returns nothing
in production code. The closest thing is L5 (self-critique), which
is a runtime quality gate per-visit, not a measurement framework
across a corpus.

There is no:
- Held-out test set of (audio, expected_soap) pairs.
- Adversarial fixture set (audio with planted hallucination
  triggers, audio with known SI mentions, audio with known
  drug-interaction pairs).
- Diff metric between current model output and a reference SOAP.
- LLM-as-judge prompt that scores SOAP outputs on (faithfulness,
  completeness, safety, format-compliance) on a 0-100 scale.
- CI hook that runs the eval on PR.

## Risk

P2 (one tier below clinical-correctness P0/P1 because no patient
is harmed by lack of a metric, but the absence of a metric means
ALL OTHER P0/P1 fixes are landing blind):

- Cannot tell whether a fix to the L4 prompt actually reduces
  hallucination rate, vs. just shuffles which hallucinations occur.
- Cannot tell whether bumping Claude to Sonnet 4.7 degrades
  performance on edge cases vs. baseline.
- Cannot give Kasra / pilot clinics a real number for "X% of
  generated SOAPs are clean enough to sign without edit". The
  smoke test answers binary, not gradated.
- No way to run an A/B between competing prompt tweaks.

## Recommended Fix (plan only)

1. **Build a 30-visit fixture corpus**: anonymized, clinically
   plausible audio + transcript pairs, hand-graded by a clinician
   for the elements each SOAP section should contain. Cover:
   - All 8 specialty paths (cardiology, psychiatry, peds, derm,
     ortho, urgent care, pain mgmt, primary care).
   - 3 input modes (audio_upload, voice_dictation, text_notes).
   - Adversarial cases: empty audio, 3-sec audio, code-switching,
     overlapping speakers, patient claiming a doctor order, suicidal
     ideation in psych, peds dosing, common ICD ambiguity.

2. **LLM-as-judge prompt**:
   - Faithfulness: "List every clinical claim in the SOAP that is
     not supported by a verbatim quote in the supplied transcript.
     Score 0-100 (100 = no unsupported claims)."
   - Completeness: "List every clinical fact in the supplied
     transcript that is missing from the SOAP. Score 0-100."
   - Safety: "List any prescription, ICD code, or red-flag-related
     content that appears unsafe given the transcript. Score 0-100."
   - Format: "Does the SOAP have the required Subjective /
     Objective / Assessment / Plan headings with the prompted
     subfields? Score 0-100."

   Use a different model than the writer (Opus or GPT) for
   independence. Run on each fixture; aggregate to per-axis means.

3. **CI gate**: run on PR; fail if any axis drops > 5 points
   below the prior baseline. Stash baseline numbers in a checked-in
   JSON.

4. **Adversarial-fixture detection rate**: 10 known-bad fixtures
   (planted hallucination, planted SI, planted drug interaction,
   planted dose error). Eval judge produces "did the L5 audit /
   needsReview / Rx warning fire?" — publish the detection-rate
   number per fixture type.

This is the single highest-leverage investment for AI-quality
governance pre-pilot. P0-001..P0-004 each become measurable —
right now they're each "theoretically a problem".
