# Keyterm regression baseline — Issues #202 + #206 PR-3

Exercises the production keyterm composition path end-to-end on a set of TTS-synthesized doctor-dictation clips, one per high-severity primary in the ISMP confused-drug-names safety floor. Confirms that the safety floor + per-specialty bundle compose under-budget AND that Deepgram preserves the target medication name in the transcript.

## Why

PR-1 (#246) shipped per-visit keyterm scoping. PR-2 (#247) shipped the ISMP safety floor. Both are unit-tested against the builder, but unit tests don't catch ASR drift — Deepgram's behaviour against real audio is the only authoritative signal that the keyterm bias actually works. This baseline is the integration check.

## What it tests

For each of 31 high-severity primaries (Lantus, Levemir, Tresiba, Implanon, metformin, tramadol, …):

1. Synthesize a ~25-40-word doctor dictation containing the primary in natural clinical context.
2. Compose per-visit keyterms exactly like L1/L1b would: `buildKeytermsForVisit({ specialty, safetyFloor: CONFUSED_DRUG_NAMES_FLAT })`.
3. Call Deepgram batch (`nova-3-medical`) with the audio + built keyterms (dictation mode: no diarize, no utterances).
4. Score: the primary medication name must appear at least once in the transcript (word-boundary, case-insensitive). Co-occurrence of `confusedWith` alternatives is tracked but not gated — a clinician can legitimately say both.

## Cost

| Phase | Provider | Approx |
|---|---|---|
| TTS synthesis (once, cached) | OpenAI tts-1 | ~$0.10 |
| Per-scenario batch transcription | Deepgram nova-3-medical | ~$0.005 each |
| **Total for 31 scenarios** |  | **~$0.25** |

## Usage

```bash
cd /opt/meddoc-pro/apps/transcribe-md

# 1. Synthesize audio (idempotent — skips cached MP3s).
npx tsx scripts/keyterm-regression/synthesize.ts

# 2. Run the regression + emit report.
npx tsx scripts/keyterm-regression/run.ts
```

Output:

- Cached audio: `/opt/meddoc-pro/.local/keyterm-regression-audio/{tag}.mp3`
- Baseline report: `/opt/meddoc-pro/docs/keyterm-regression-baseline/baseline-{ISO}.md`

## Strict serial

Every TTS call is serial. Every Deepgram call is serial. No parallel batching. This is a HARD constraint inherited from the PR-2 commit message — see #247's body for the previous-session crash note.

## When to re-run

- After any change to `apps/transcribe-md/src/lib/confused-drug-names.ts` (new pairs, severity changes).
- After any change to `apps/transcribe-md/src/lib/deepgram-vocabulary.ts` (CORE or specialty bundle edits).
- After any change to `apps/transcribe-md/src/lib/deepgram-keyterm-builder.ts` (budget, dedupe, composition rules).
- After a Deepgram model upgrade (`DEFAULT_BATCH_MODEL` in `packages/ai/src/deepgram-batch.ts`).
- Quarterly as a drift check against accumulated ISMP updates.

Adding more primaries (medium/low severity, or new clusters) means appending to `scenarios.ts` and rerunning `synthesize.ts` — the cache makes re-runs cheap.
