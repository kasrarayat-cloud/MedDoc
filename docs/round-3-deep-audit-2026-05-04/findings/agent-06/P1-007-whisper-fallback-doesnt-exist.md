---
id: A06-P1-007
title: "Deepgram primary, Whisper fallback" claimed in audit brief but not implemented
severity: P1
domain: AI safety / transcription resilience / vendor lock-in / claim accuracy
files:
  - packages/ai/src/deepgram-batch.ts
  - apps/transcribe-md/src/worker/layers/01-transcribe.ts (lines 73-83)
  - packages/ai/src/api-usage.ts (lines 31, 51, 152-159) — Whisper appears in pricing only
---

## Issue

The audit brief and at least one architecture document describe the
transcription pipeline as "Deepgram primary, Whisper fallback". A
full grep across the worker, the @meddoc/ai package, and the apps
shows that **Whisper is not integrated as a transcription fallback
anywhere**:

- `packages/ai/src/api-usage.ts:31` lists Whisper as a known
  pricing rate, used by the admin usage UI's color-coding only.
- `apps/transcribe-md/src/app/admin/_lib/admin-format.ts` formats
  Whisper as a label option in the admin dashboard.
- **No code path calls Whisper.** No `openai.audio.transcriptions`,
  no `whisper-1` invocation, no fallback try/catch in L1 or L1b
  that switches providers.

## Evidence

`grep -rn "whisper" /opt/meddoc-pro/apps/transcribe-md /opt/meddoc-pro/packages/ai/src` returns 5 hits — all in admin display
code or pricing tables. The actual L1 retry logic is:

```ts
// 01-transcribe.ts:73-83
let result;
try {
  result = await attempt();
} catch (err) {
  // Retry once on 5xx / network blips. 4xx (bad file, bad mime) is
  // terminal and the catch in worker.ts will surface it as a
  // reviewReason on the visit.
  const status = (err as { status?: number }).status;
  if (status && status >= 400 && status < 500) throw err;
  await new Promise((r) => setTimeout(r, BACKOFF_MS));
  result = await attempt();
}
```

A second Deepgram attempt is the only resilience. If Deepgram has a
sustained outage (and the worker's `categorizeError.ts` correctly
detects it as `provider_down`), the visit fails — the doctor's
finished recording sits in MinIO with no SOAP and no escape hatch.

## Risk

P1 because:

- **No safety harm directly** — but the pipeline's resilience claims
  in marketing/compliance docs are inaccurate. If the pilot has a
  Deepgram outage during clinic hours, every visit fails, and the
  product looks broken. A real Whisper fallback would carry the day.
- **Vendor lock-in**: pricing or policy change at Deepgram (e.g.
  pulling nova-3-medical from US-East PHI compliance) leaves no
  migration path.
- **Quality on Farsi**: Whisper-large-v3 is materially better than
  Deepgram on non-English clinical audio (see P1-006). The "fallback"
  could double as a Farsi-specialist primary path.

## Recommended Fix (plan only)

1. **Build the actual Whisper integration.**
   `packages/ai/src/whisper.ts` — a `whisperBatchTranscribe` function
   that mirrors the `deepgramBatchTranscribe` interface (returns the
   same `DeepgramBatchResult` shape, minus diarize/utterances if
   Whisper doesn't support them, with a stub speakerMap for L2 to
   handle).

2. **Wire as the second attempt in L1**:
   ```ts
   try {
     result = await deepgramBatchTranscribe(...);
   } catch (err) {
     if (categorizeError(err) === 'provider_down') {
       result = await whisperBatchTranscribe(...);
     } else {
       throw err;
     }
   }
   ```

3. **Mode selector**: env-flag the fallback so a clinic can opt in
   per-practice. `WHISPER_FALLBACK_ENABLED=true` default off until
   tested in staging.

4. **Documentation alignment**: until shipped, remove the "Whisper
   fallback" line from any architecture doc that claims it. The
   pre-pilot audit documentation should not mislead about the
   resilience model.
