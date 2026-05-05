---
id: A06-P0-001
title: No code-side guard against empty/silent transcript producing fabricated SOAP
severity: P0
domain: AI safety / no-fabrication
files:
  - apps/transcribe-md/src/worker.ts (lines 256-269, 314-447)
  - apps/transcribe-md/src/worker/layers/01-transcribe.ts (lines 90-103)
  - apps/transcribe-md/src/worker/layers/03-extract-entities.ts (lines 362-403)
  - apps/transcribe-md/src/worker/layers/04-generate-soap.ts (lines 27-112)
---

## Issue

The "empty audio → empty SOAP" guarantee that Phase F of the smoke test
asserts is **enforced exclusively by prompt instruction**, not by any
deterministic code path. Every link in the pipeline accepts an empty
transcript without stopping, and the only thing standing between
"silent recording" and a fabricated SOAP note is Claude's adherence to
the "do NOT invent" sentence in the L4 system prompt.

## Evidence

1. **L1 (Deepgram)** — `runLayer1Transcribe` writes whatever Deepgram
   returns to `transcriptText` without checking length:

   ```ts
   // apps/transcribe-md/src/worker/layers/01-transcribe.ts:90-97
   await prisma.transcribeVisit.update({
     where: { id: input.visitId },
     data: {
       transcriptRaw: result.raw as unknown as object,
       transcriptText: result.transcript,   // could be ''
       audioDurationSec: result.durationSec, // could be 0
     },
   });
   ```

   No `if (result.transcript.trim().length === 0) throw …`. A 3-second
   silence file legitimately produces `transcript: ''` and the layer
   reports success.

2. **L1b (single-speaker dictation)** — same issue at line 74-82.

3. **L2 (speaker roles)** — when Deepgram returns no utterances,
   the layer writes a single-speaker `'doctor'` fallback with
   `confidence: 0.5` and proceeds (lines 82-102 of `02-speaker-roles.ts`).
   It sets `needsReview: true` but **does not stop the pipeline** —
   downstream layers will still run.

4. **L3 (entity extraction)** is called on the empty transcript with
   no guard (`worker.ts:373-383`):
   ```ts
   const l3 = await runLayer3ExtractEntities({
     ...
     mode: 'conversation',
     utterances,        // []
     speakerMap,        // either fallback or empty
   });
   ```
   The Claude prompt is asked to extract entities from `""` and
   instructed (`03-extract-entities.ts:288`): "If the transcript is
   silent on a category, return [] (or null for singleton)". This is a
   prompt instruction, not a hard stop.

5. **L4 (SOAP generation)** is then called with empty entities and
   empty contextText (`worker.ts:463-471`). The L4 system prompt says
   *"Do NOT invent clinical findings"* (lines 70-72) and *"Use [not
   documented] rather than inventing"* — but **no pre-call check that
   `entities` are entirely null/empty AND `roleLabeledTranscript` is
   empty**. A misbehaving model that generates a plausible-looking
   SOAP from no input is rendered to the doctor as a finished note.

6. The text_notes branch (`worker.ts:264-266`) DOES guard:
   `if (!visit.rawTextInput?.trim()) throw …`. The same defensive
   pattern is absent from the audio-upload and voice_dictation paths.

## Risk

Severity is P0 because the failure mode is **fabrication of an entire
clinical note from silence**. A doctor who hits "submit" on a recording
that turned out to be silent (mic muted, dropped peer-to-peer audio,
phone call instead of in-person visit) gets a SOAP note with
plausible-looking sections that they may sign without realizing it
contains no patient-derived content. This is the exact harm the
QuillMD value prop says cannot happen.

The smoke test (PR #108) validated the property end-to-end against the
*current* model behavior — but the model behavior is the only thing
preventing the failure. Any future Anthropic model (Sonnet 4.7, Opus
5, etc.) or temperature drift could change this without the codebase
noticing.

## Recommended Fix (plan only — read-only audit)

Add deterministic guards at three points:

1. **L1 / L1b post-write**: throw a typed `EmptyTranscriptError` when
   `result.transcript.trim().length === 0` AND `durationSec > 0`
   (i.e., audio decoded but contained no speech). Categorize as
   permanent in `error-categorize.ts`.

2. **Pre-L4 short-circuit**: in `worker.ts` between L3 and L4 (after
   the entity assignment), check if `entities` is entirely null + empty
   arrays AND `contextText.trim() === ''`. If so, write a soapDraft
   sentinel ("No content captured. Please re-submit a recording with
   audible audio.") and skip L4-L7 directly to FAILED with a
   user-facing reviewReason. The smoke test's claim — "empty audio →
   empty SOAP" — becomes a code-path invariant, not a prayer.

3. **L4 input validation**: add a defensive `if (input.entities is
   empty && input.roleLabeledTranscript.trim() === '') throw` before
   the model call. This is belt-and-suspenders — guard 2 should already
   prevent this, but the LLM provider stays expensive enough that the
   safety check is worth the dozen lines.

This finding was the #1 hypothesis in the audit brief and the code
reading confirms it: the property is asserted, not enforced.
