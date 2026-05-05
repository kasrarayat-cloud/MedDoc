---
id: A06-P1-010
title: L5 self-critique uses the same model as L4; correlated failure modes
severity: P1
domain: AI safety / eval bias / "judge knows the same things the writer knows"
files:
  - apps/transcribe-md/src/worker/layers/04-generate-soap.ts (line 16)
  - apps/transcribe-md/src/worker/layers/05-self-critique.ts (line 19)
---

## Issue

Layers 4 (SOAP draft), 5 (critique), and 6 (polish) all use
`claude-sonnet-4-6`. L5's job is to audit L4's output for
hallucination, contradictions, and missing red-flag screening. But
L5 is the same model with the same training data and the same
biases:

- If L4 hallucinates a finding because the model believes a
  particular co-symptom typically appears with the chief complaint,
  L5 — looking at the same prompt context — will likely consider
  that finding plausible too. **The judge can't catch its own
  hallucinations.**
- If L4 misses a red-flag because the prompt didn't list that
  particular flag, L5 sees the same prompt and miss the same flag.
- The "independent pass" comment at L5 (lines 9-12) is aspirational —
  in practice the two passes share 100% of model weights and ~95%
  of context.

## Evidence

```ts
// 04-generate-soap.ts:16
const MODEL = 'claude-sonnet-4-6';

// 05-self-critique.ts:19
const MODEL = 'claude-sonnet-4-6';

// 06-polish.ts:18
const MODEL = 'claude-sonnet-4-6';
```

The L5 system prompt explicitly relies on the model "noticing" a
hallucination by comparing the SOAP to the role-labeled transcript
(line 55):
> "Any factual claim in the SOAP that CANNOT be traced to the
> transcript or entities — i.e. hallucination."

This is a verifiable check IF the auditor model is reliable at
exact-string verification. Claude is well-known to fail at strict
string-presence checks under high context (the "needle in a
haystack" / RAG verification literature). Especially on a 90-min
visit transcript, the L5 audit reliably misses some hallucinations.

The L5 prompt asks for a self-rating (`overall_quality: high |
medium | low`, `safe_to_sign_without_review: bool`) which then
gates whether `needsReview` is set on the visit. The model is
literally judging whether its own pipeline output is safe.

## Risk

P1 because:

- The "self-critique" layer is positioned as the safety net. If it
  has correlated failures with the writer, that net is thinner
  than advertised.
- Eval-framework absence (P2-011) means we don't have ground-truth
  numbers on how often L5 catches a real hallucination vs. how
  often it misses one. The smoke test only checks structural
  output, not adversarial-fixture detection rates.
- Marketing/compliance positioning that mentions "auditor reviews
  every note for hallucination" is misleading without that data.

## Recommended Fix (plan only)

1. **Different model family for L5.** Run L5 on Opus (more capable
   on careful reasoning) OR on a different vendor (GPT-4.1) so a
   shared-weight failure mode in Sonnet doesn't propagate. Pricing
   trade-off is real but L5 is one call per visit.

2. **Different prompt framing**. Instead of "you are an auditor",
   give the L5 model the entities (verbatim from L3), the
   transcript, and ASK it to "find any sentence in the SOAP whose
   underlying claim does not appear in the supplied entities or
   transcript." Strip the SOAP-context from L5's input — make it
   a forced-citation task rather than a vibe-check.

3. **Deterministic backstop**: simple substring/Jaccard check —
   for each Plan-section item, verify at least N substring tokens
   appear in `entities.plan_discussed[].evidence_quote`. Below
   threshold → flag as "claim not grounded in evidence" critical
   issue. This catches the easy cases the L5 model misses.

4. **Eval-corpus**: build a fixed test set of 50 transcripts with
   known-injected hallucinations (3 per visit), run the pipeline,
   measure L5 detection rate. Publish the number ("auditor catches
   X% of injected hallucinations in our regression set"). Without
   this number the layer's value is hand-wavy.

This finding pairs with P2-011 (eval framework gap). A working
eval framework would surface L5's true detection rate; right now
it's faith.
