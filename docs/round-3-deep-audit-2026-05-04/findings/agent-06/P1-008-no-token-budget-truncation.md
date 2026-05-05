---
id: A06-P1-008
title: 90-minute visit token-budget exhaustion has no truncation strategy
severity: P1
domain: AI safety / context-window overflow / silent degradation
files:
  - apps/transcribe-md/src/worker/layers/04-generate-soap.ts (lines 83-104)
  - apps/transcribe-md/src/worker/layers/05-self-critique.ts (lines 93-118)
  - apps/transcribe-md/src/worker/layers/06-polish.ts (lines 60-86)
  - apps/transcribe-md/src/worker/layers/03-extract-entities.ts (lines 380-395)
  - packages/ai/src/anthropic.ts
---

## Issue

The pipeline has no documented behavior for transcripts that exceed
Claude's context window (200K tokens for Sonnet 4.6). A 90-minute
visit at typical conversational density is ~12,000 words ≈ 16K
tokens of role-labeled transcript — well under the limit. But:

- A 4-hour group-therapy session, a multi-doctor case conference, a
  badly-recorded long audio file with high repetition (Deepgram does
  emit duplicate utterances on poor audio), or a paranoid /
  manic patient's verbal stream-of-consciousness can blow past 100K
  tokens of input.
- The pipeline's response is **undefined**: the layers pass the
  full transcript to the Anthropic SDK with no truncation, no
  windowing, no hierarchical summarization. The Anthropic API will
  either accept it (cost spike), reject with HTTP 400 (visit fails
  permanently), or — worst case — silently truncate input
  server-side and the model generates a SOAP from a partial
  transcript without flagging the gap.

## Evidence

1. **L4 user prompt** (`04-generate-soap.ts:83-91`):
   ```ts
   const user = [
     `Specialty: ${input.specialty}`,
     '',
     'Extracted entities (structured, with evidence):',
     JSON.stringify(input.entities, null, 2),
     '',
     'Role-labeled transcript:',
     input.roleLabeledTranscript,    // unbounded
   ].join('\n');
   ```
   No length check on `roleLabeledTranscript`. No "if length > N,
   summarize first" branch.

2. **L5 (self-critique) and L6 (polish)** have the same shape —
   `roleLabeledTranscript` is passed in unbounded.

3. **L3 maxTokens: 6144** (output budget) — at high entity density
   (a chronic-disease patient with 15 medications, 20 ROS items,
   10 PMH conditions) the JSON response can be cut off mid-object,
   causing a SCHEMA_FAIL. The retry path in `model-client.ts:74-95`
   is up to 2 retries with the prior error appended — eating MORE
   input tokens, not fewer. Eventually the visit fails permanently.

4. **No token-counting helper.** `packages/ai/src/anthropic.ts`
   has a `hashPrompt` for the cache key but no `estimateTokens`
   function. `prompt-hash.ts` is hash-only.

5. **Pricing math** in `pricing.ts` is per-call, no rolling-budget
   awareness. A 200K-input-token call on Sonnet 4.6 at $3/M
   in-tokens is $0.60 per visit per layer × 6 layers = $3.60 of
   model spend on one visit, plus the Deepgram batch — a single
   pathological audio file can be a $5+ visit.

## Risk

P1 because:

- **Silent quality degradation**: if Anthropic truncates input,
  the visit completes with a SOAP generated from a fraction of the
  transcript. The doctor sees a normal-looking note. This is the
  worst kind of failure — looks fine, isn't fine.
- **Hard-fail mode**: a permanent 400 from Anthropic on
  context-overflow ends the visit in FAILED, but `error-categorize.ts`
  doesn't have a pattern for "context_length_exceeded" so it's
  routed as `transient` and retried twice — three failed expensive
  calls before the visit lands in FAILED.
- **Cost runaway**: malicious or accidental long-recording uploads
  on a free trial could be a vendor-cost DoS.

## Recommended Fix (plan only)

1. **Add `estimateTokens(text)`** to `@meddoc/ai` (Anthropic
   publishes a tokenizer; bundle it). Treat 1 char ≈ 0.25 tokens
   as a quick floor; use a real tokenizer for the budget check.

2. **Pre-L3 truncation strategy** for transcripts above (say) 80K
   tokens of role-labeled text:

   - Run a "summarize-by-time-window" pass first: split the
     transcript into 10-minute windows, summarize each window
     using a smaller model (Haiku) into 500 tokens of "what the
     patient + doctor discussed in this window".
   - Pass the summaries + the full transcript of the FINAL 30
     minutes (most recent assessment + plan) to L3.
   - Persist the windowing metadata so the Pipeline tab can show
     "I summarized X minutes of conversation; review against the
     audio if anything looks off."
   - **Document this in the prompt** so the model knows it has a
     summary, not a verbatim transcript, for the early portion.

3. **`error-categorize.ts` pattern**: add `context_length_exceeded`,
   `prompt is too long`, `tokens exceeds` to the
   `isPermanentInputError` regex. Fail-fast on token-overflow rather
   than retrying.

4. **Per-visit cost ceiling** (`processingCostCents > N`) → abort
   pipeline and surface a clear admin-side flag. Avoids a runaway
   adversarial recording draining Anthropic credits.

5. **Visit duration cap on upload** (`MAX_BYTES = 500MB` exists, but
   bytes ≠ duration — a 500MB FLAC at 96kHz is 6 hours). Add a
   server-side audio-duration check on upload (ffprobe) and reject
   anything over `AUDIO_MAX_DURATION_SEC` (default 5400 = 90 min).

This is the highest-risk operational gap — the others are clinical;
this one is "what happens at the boundary of the model's capacity"
and it currently is documented as "unclear, probably fail".
