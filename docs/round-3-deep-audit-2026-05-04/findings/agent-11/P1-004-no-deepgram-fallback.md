---
id: A11-P1-004
severity: P1
domain: error-handling-observability
title: Deepgram is the single point of failure for transcription — no fallback provider
---

# A11-P1-004 — No Whisper / fallback transcription provider; Deepgram outage = product down

## Issue

The audit checklist explicitly asks "Deepgram down → Whisper fallback?"; the
answer is **no**. Both transcription paths (`runLayer1Transcribe` for
audio_upload and `runLayer1bTranscribeDictation` for voice_dictation)
exclusively call `deepgramBatchTranscribe()`. There is no `whisperTranscribe`
or any other implementation of the same surface in `packages/ai/src/`. The
only retry on a Deepgram failure is a single in-layer 5xx retry inside
`runLayer1Transcribe` (one extra attempt with 2s backoff), and the BullMQ-
level retry (3 attempts, exp backoff). Both paths still hit Deepgram.

`packages/ai/src/api-usage.ts` includes a `whisper` provider in the pricing
table (line 38) and has a `Provider` union (line 53) listing
`'whisper' | 'openai'` — but no actual client code. So the placeholder is
intentional but never finished.

## Evidence

```
$ grep -rln "Whisper\|whisper" /opt/meddoc-pro/apps/transcribe-md
/opt/meddoc-pro/apps/transcribe-md/src
# (zero matches in source — only in compiled .next/ artifacts as comments)

$ grep -rln "openai\|whisper" /opt/meddoc-pro/packages/ai/src
/opt/meddoc-pro/packages/ai/src/api-usage.ts   # only pricing constants
```

`apps/transcribe-md/src/worker/layers/01-transcribe.ts:75-82` — the
"fallback" is just one retry against the same Deepgram endpoint:
```ts
const status = (err as { status?: number }).status;
if (status && status >= 400 && status < 500) throw err;
// One retry on 5xx / network blips.
```

`apps/transcribe-md/src/worker/error-categorize.ts:23-34` — the worker
*detects* a "provider_down" condition (3 consecutive 5xx in 60 s) and
sends the doctor a `provider_down` reviewReason — but the only action
is to wait. The pipeline doesn't try anyone else.

## Risk

A Deepgram regional outage (which has happened — see Deepgram status page
2024-2025 incidents) means **every visit submitted during the outage fails
the same way**. Three BullMQ retries × 2s exponential backoff = ~50s of
useless retries per visit, all hitting the same dead provider. The visit
ends up `FAILED` with the user-facing message "Our transcription provider
is temporarily unavailable; please try again in a few minutes." but with
no clear ETA, no retry queue, and no resilience.

Pre-pilot, this is acceptable risk; for a real-doctor pilot, a 1-hour
Deepgram outage means a full hour of doctors' notes are unrecoverable
without manual operator-driven re-enqueue (and re-enqueue still hits
Deepgram).

The product being marketed as "AI medical scribe" with a single hard
provider dependency is a reputational + operational fragility worth
flagging before launch.

## Recommended fix

Three options ranked by effort:

1. **Cheap**: implement `openaiWhisperTranscribe()` in
   `packages/ai/src/whisper.ts` (the OpenAI Whisper API has a similar
   batch surface — POST audio, get utterances back). Wrap layer 1 in a
   `try { deepgram } catch (e) { if (categorize(e)==='provider_down')
   return whisper(...) }`. Cost: an extra dependency on OpenAI (already
   listed in `Provider` union — pricing constants exist), maybe one
   week of engineering.

2. **Medium**: queue affected visits with status `STALLED_PROVIDER` and
   re-enqueue them automatically when a periodic Deepgram health probe
   recovers. Avoids dependency on a second vendor.

3. **Surface-only**: improve the user-visible message to include an
   ETA estimate (Deepgram's status page typically resolves in 10-30 min)
   and a "we will email you when your note is ready" promise — needs an
   email side-channel for failure notifications.

Whichever path: **document this single-provider exposure in
LAUNCH_READINESS.md so the founder + ops know the operational ceiling
they're carrying into pilot**.
