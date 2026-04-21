import { describe, it, expect } from 'vitest';

import {
  extractTokens,
  partitionTokens,
  SUPPORTED_TOKENS,
} from './template-tokens';

describe('extractTokens', () => {
  it('returns empty array when no tokens present', () => {
    expect(extractTokens('Plain document with no placeholders')).toEqual([]);
  });

  it('extracts a single token', () => {
    expect(extractTokens('HPI: {{hpi}}')).toEqual(['hpi']);
  });

  it('extracts multiple tokens in document order', () => {
    const text = 'CC: {{chief_complaint}}\n\nHPI: {{hpi}}\n\nA: {{assessment}}';
    expect(extractTokens(text)).toEqual(['chief_complaint', 'hpi', 'assessment']);
  });

  it('deduplicates repeated tokens', () => {
    const text = '{{hpi}} appears here and again {{hpi}} and {{pmh}}';
    expect(extractTokens(text)).toEqual(['hpi', 'pmh']);
  });

  it('preserves first-occurrence order across duplicates', () => {
    const text = '{{plan}} then {{hpi}} then {{plan}} then {{chief_complaint}}';
    expect(extractTokens(text)).toEqual(['plan', 'hpi', 'chief_complaint']);
  });

  it('only matches snake_case lowercase tokens', () => {
    // {{HPI}} (upper), {{foo bar}} (space), {{123}} (digits) — all
    // rejected by the [a-z_]+ character class.
    const text = '{{HPI}} {{foo bar}} {{123}} {{valid_token}}';
    expect(extractTokens(text)).toEqual(['valid_token']);
  });

  it('ignores single-brace placeholders', () => {
    // docxtemplater uses double braces; `{hpi}` prose shouldn't match.
    expect(extractTokens('single {hpi} brace is prose')).toEqual([]);
  });
});

describe('partitionTokens', () => {
  it('classifies all supported tokens as supported', () => {
    const result = partitionTokens([...SUPPORTED_TOKENS]);
    expect(result.supported).toEqual([...SUPPORTED_TOKENS]);
    expect(result.unsupported).toEqual([]);
  });

  it('buckets unknown tokens into unsupported', () => {
    const result = partitionTokens(['hpi', 'my_custom_field', 'assessment']);
    expect(result.supported).toEqual(['hpi', 'assessment']);
    expect(result.unsupported).toEqual(['my_custom_field']);
  });

  it('handles empty input', () => {
    expect(partitionTokens([])).toEqual({ supported: [], unsupported: [] });
  });

  it('preserves input order within each bucket', () => {
    const result = partitionTokens([
      'custom_a',
      'plan',
      'custom_b',
      'hpi',
      'custom_c',
    ]);
    expect(result.supported).toEqual(['plan', 'hpi']);
    expect(result.unsupported).toEqual(['custom_a', 'custom_b', 'custom_c']);
  });

  it('confirms SUPPORTED_TOKENS contains the expected set', () => {
    // Lock the first-phase token list so a future edit that
    // accidentally drops one trips this test.
    expect([...SUPPORTED_TOKENS]).toEqual([
      'chief_complaint',
      'hpi',
      'pmh',
      'medications',
      'allergies',
      'ros',
      'exam',
      'assessment',
      'plan',
    ]);
  });
});
