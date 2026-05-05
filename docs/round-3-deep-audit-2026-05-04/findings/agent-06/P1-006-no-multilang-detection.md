---
id: A06-P1-006
title: Deepgram is locked to English; multi-language code-switching silently mistranscribed
severity: P1
domain: AI safety / transcription accuracy / Iranian-clinic pilot context
files:
  - packages/ai/src/deepgram-batch.ts (lines 154-168)
---

## Issue

The Deepgram batch transcription is hardcoded to `language: 'en'` and
explicitly disables auto-detection (`detect_language: 'false'`). The
worker callsites in L1 and L1b never override either. This means:

- A patient who code-switches Farsi ↔ English is transcribed as if
  every Farsi token were English. Deepgram's nova-3-medical model
  will produce phonetic gibberish for the Farsi spans.
- The model passes the gibberish into L3 / L4, which dutifully tries
  to extract entities from it.
- Either the model fails silently (entities returned for the English
  spans only, half the visit gone from the SOAP) or hallucinates to
  fill the gaps.

## Evidence

```ts
// packages/ai/src/deepgram-batch.ts:154-168
const language = args.language ?? 'en';
...
const params = new URLSearchParams({
  model,
  language,                           // hardcoded 'en'
  diarize: String(wantDiarize),
  punctuate: 'true',
  smart_format: 'true',
  paragraphs: 'true',
  utterances: String(wantUtterances),
  filler_words: 'false',
  detect_language: 'false',           // explicitly off
});
```

- `args.language` is never set by L1 / L1b in the worker. The optional
  `language` field on `DeepgramBatchArgs` exists but no caller uses it.
- No env var to toggle multi-language mode (Deepgram supports
  `language=multi` for code-switching on nova-3 → nova-3-en + nova-3-es,
  and a separate model selector for fa-IR; either would help).
- No transcription fallback on Farsi spans (e.g., Whisper's
  `large-v3` does much better on Persian than nova-3-medical does).
  Despite the brief mentioning "Whisper fallback", the codebase has
  no Whisper integration at all (see P1-007).

## Risk

P1 because the Iranian-clinic pilot mentioned in the meddoc-pro
keyterm vocabulary file is the most explicit pilot context and
**precisely the population most likely to code-switch**:

```ts
// apps/transcribe-md/src/lib/deepgram-vocabulary.ts:58-63
// ── Iranian / Middle-East common brand spellings (pilot context) ──
'brufen', 'profen', 'voltaren', 'panadol', 'paracetamol',
```

If the pilot clinic is in Tehran or serves Farsi-speaking expats, an
English-only Deepgram is going to mistranscribe routine clinical
content. A patient saying "سرم درد می‌کنه از سه روز پیش" (my head has
been hurting for three days) becomes phonetic noise; L3 finds no
chief-complaint entity; L4 generates "[not documented]".

## Recommended Fix (plan only)

1. **Use Deepgram's `language: 'multi'` mode** for nova-3 (currently
   en/es). For Farsi, use `language: 'fa'` with the appropriate
   nova-3 model variant if/when Deepgram releases one, or fall back
   to Whisper-large-v3 (next finding).

2. **Per-clinic language config**: add `practice.transcriptionLanguage`
   ('en', 'es', 'fa', 'multi') and pass through to
   `deepgramBatchTranscribe`. Default 'en' for backward compat.

3. **Code-switching detection**: when nova-3-multi is used, surface
   the per-utterance language tag (Deepgram returns it on each
   utterance) so the Pipeline tab can show which spans were
   non-English. The doctor reviewing the SOAP can verify the
   multilingual transcript was correct.

4. **Documentation**: the pilot readiness doc should explicitly say
   "English-only audio is currently supported" until (1) lands.
