// ============================================================================
// Build-time guard for the Deepgram keyterm vocabulary.
// ----------------------------------------------------------------------------
// Deepgram caps the total subword tokens across all keyterms at 500.
// Exceed it and every transcription request 400s with
// "Keyterm limit exceeded" — silently breaks the whole pipeline.
//
// We can't ask Deepgram's tokenizer at build time (it's not a public
// library), so we estimate with a conservative ceil(len/3.5) heuristic
// that empirically over-counts cl100k_base / o200k_base on medical
// English by ~10–20%. If estimated tokens stay under our internal cap
// of 450, the real Deepgram count is virtually guaranteed to stay
// under 500 with headroom.
//
// If this test fails, the operator hit the cap by adding too many
// terms. Fix: trim the vocabulary back below 450 estimated tokens
// (drop tail-of-distribution generics that nova-3-medical already
// recognises). Don't lift the limit — Deepgram's hard cap is 500.
// ============================================================================

import { describe, it, expect } from 'vitest';

import {
  MEDICATION_KEYTERMS,
  MEDICATION_KEYTERMS_TAIL,
  MEDICATION_KEYTERMS_FULL,
} from './deepgram-vocabulary';

/** Conservative upper-bound estimate of Deepgram's subword tokenizer.
 *  ceil(len/3.5) over-counts cl100k by ~15% on medical English. The
 *  +1 floor keeps single-character terms from rounding to 0.
 *  Whitespace inside a term ("insulin glargine") is treated as a
 *  separator that consumes one extra token, matching how most BPE
 *  tokenizers handle multi-word strings. */
function estimateSubwordTokens(term: string): number {
  let total = 0;
  for (const chunk of term.split(/\s+/).filter(Boolean)) {
    total += Math.max(1, Math.ceil(chunk.length / 3.5));
  }
  // +1 per whitespace boundary inside the term — Deepgram's tokenizer
  // breaks on whitespace and assigns it its own token slot.
  const wordCount = term.split(/\s+/).filter(Boolean).length;
  if (wordCount > 1) total += wordCount - 1;
  return total;
}

function totalEstimatedTokens(terms: readonly string[]): number {
  return terms.reduce((sum, t) => sum + estimateSubwordTokens(t), 0);
}

/** Internal cap, 10% below the Deepgram-imposed 500. Buffer absorbs
 *  heuristic error + future tokenizer drift. */
const INTERNAL_TOKEN_CAP = 450;

describe('MEDICATION_KEYTERMS — Deepgram 500-token cap', () => {
  it('estimated subword tokens stay under the internal cap', () => {
    const total = totalEstimatedTokens(MEDICATION_KEYTERMS);
    // Surface the real number in the assertion so a failure prints
    // exactly how far over we are (vs a binary pass/fail).
    expect(total).toBeLessThanOrEqual(INTERNAL_TOKEN_CAP);
  });

  it('working set has at least one entry — empty list = bug', () => {
    expect(MEDICATION_KEYTERMS.length).toBeGreaterThan(0);
  });

  it('all entries are lowercase + non-empty (matches Deepgram lookup)', () => {
    for (const t of MEDICATION_KEYTERMS) {
      expect(t).toBe(t.toLowerCase());
      expect(t.trim()).not.toBe('');
    }
  });

  it('working set is duplicate-free', () => {
    const set = new Set(MEDICATION_KEYTERMS);
    expect(set.size).toBe(MEDICATION_KEYTERMS.length);
  });

  it('working set + tail merge preserves uniqueness in FULL', () => {
    const merged = new Set([
      ...MEDICATION_KEYTERMS,
      ...MEDICATION_KEYTERMS_TAIL,
    ]);
    expect(MEDICATION_KEYTERMS_FULL.length).toBe(merged.size);
  });
});

describe('estimateSubwordTokens — heuristic sanity', () => {
  it('counts a single-word term roughly by length', () => {
    // "ibuprofen" = 9 chars → ceil(9/3.5) = 3 tokens.
    expect(estimateSubwordTokens('ibuprofen')).toBe(3);
  });

  it('charges an extra token for the whitespace separator', () => {
    // "insulin glargine" — "insulin" (7c → 2 tok) + sep (1 tok) +
    // "glargine" (8c → 3 tok) = 6.
    expect(estimateSubwordTokens('insulin glargine')).toBe(6);
  });

  it('handles hyphenated terms by length, not boundary', () => {
    // We deliberately don't split on hyphens — Deepgram's tokenizer
    // tends to keep hyphenated drug names as one unit. The heuristic
    // length-based count covers this.
    expect(estimateSubwordTokens('sacubitril-valsartan')).toBeGreaterThan(4);
  });
});
