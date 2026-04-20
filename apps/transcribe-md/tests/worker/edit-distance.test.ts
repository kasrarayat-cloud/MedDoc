// ============================================================================
// Unit tests for T-M14.1 charLevenshtein
// ============================================================================

import { describe, expect, it } from 'vitest';

import { charLevenshtein } from '@/lib/edit-distance';

describe('charLevenshtein — basic behaviors', () => {
  it('identical strings return 0', () => {
    expect(charLevenshtein('', '')).toBe(0);
    expect(charLevenshtein('abc', 'abc')).toBe(0);
    expect(charLevenshtein('## Subjective\nfoo', '## Subjective\nfoo')).toBe(0);
  });

  it('one empty side returns the other length', () => {
    expect(charLevenshtein('', 'abcd')).toBe(4);
    expect(charLevenshtein('abcde', '')).toBe(5);
  });

  it('one-character substitution is distance 1', () => {
    expect(charLevenshtein('abc', 'abd')).toBe(1);
    expect(charLevenshtein('kitten', 'kitteN')).toBe(1);
  });

  it('classic kitten → sitting is 3', () => {
    expect(charLevenshtein('kitten', 'sitting')).toBe(3);
  });

  it('insertions only', () => {
    expect(charLevenshtein('abc', 'abcdef')).toBe(3);
  });

  it('deletions only', () => {
    expect(charLevenshtein('abcdef', 'abc')).toBe(3);
  });
});

describe('charLevenshtein — SOAP-like workloads', () => {
  it('small doctor edit produces small distance', () => {
    const ai = '## Assessment\nTension-type headache, resolving.\n';
    const doctor = '## Assessment\nTension-type headache, improving.\n';
    // "resolving" → "improving" = 2 substitutions + 2 insertions, 5 chars
    const d = charLevenshtein(ai, doctor);
    expect(d).toBeGreaterThan(0);
    expect(d).toBeLessThanOrEqual(10);
  });

  it('full rewrite produces a large distance', () => {
    const ai = '## Subjective\n[AI] Patient reports headache.\n';
    const doctor = '## Subjective\nPt reports throbbing frontal headache x 3 days with photophobia.\n';
    const d = charLevenshtein(ai, doctor);
    expect(d).toBeGreaterThan(20);
  });
});

describe('charLevenshtein — input size cap', () => {
  it('returns a finite, non-throwing number for 20K-char inputs', () => {
    const big = 'a'.repeat(20_000);
    const bigDiff = 'b'.repeat(20_000);
    // Cap is 8K/side; answer is a lower-bound approximation (8000).
    const d = charLevenshtein(big, bigDiff);
    expect(Number.isFinite(d)).toBe(true);
    expect(d).toBe(8000);
  });

  it('identical 20K-char inputs still return 0 under cap', () => {
    const big = 'x'.repeat(20_000);
    expect(charLevenshtein(big, big)).toBe(0);
  });
});
