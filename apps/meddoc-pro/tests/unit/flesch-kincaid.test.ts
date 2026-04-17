// ============================================================================
// Flesch-Kincaid grade calculator (M4, user-added)
// ----------------------------------------------------------------------------
// Lives in apps/scribe/src/lib/flesch-kincaid.ts; tests in this package's
// harness because that's where vitest runs. Heuristic syllable counting
// isn't expected to match textbook values exactly — we assert ranges.
// ============================================================================

import { describe, it, expect } from 'vitest';
import { fleschKincaidGrade } from '../../../scribe/src/lib/flesch-kincaid';

describe('fleschKincaidGrade', () => {
  it('returns 0 for empty / whitespace-only input', () => {
    expect(fleschKincaidGrade('')).toBe(0);
    expect(fleschKincaidGrade('   \n  ')).toBe(0);
  });

  it('scores very simple sentences at elementary-school level', () => {
    // "Hi Jane. Take one pill a day. Call us if you feel worse." — short words, short sentences.
    const grade = fleschKincaidGrade('Hi Jane. Take one pill a day. Call us if you feel worse.');
    expect(grade).toBeGreaterThanOrEqual(0);
    expect(grade).toBeLessThan(6);
  });

  it('scores clinical jargon noticeably higher than plain language', () => {
    const plain =
      'You have a cold. Rest and drink water. Call us if you get worse.';
    const jargon =
      'The patient presents with an uncomplicated viral upper respiratory infection requiring supportive management and symptomatic treatment.';
    const plainGrade = fleschKincaidGrade(plain);
    const jargonGrade = fleschKincaidGrade(jargon);
    expect(jargonGrade).toBeGreaterThan(plainGrade + 2);
  });

  it('handles text with no punctuation (single sentence fallback) without crashing', () => {
    // FK math clamps negatives to 0 (very simple text), so any non-negative
    // finite number is acceptable.
    const grade = fleschKincaidGrade('this is a short line');
    expect(Number.isFinite(grade)).toBe(true);
    expect(grade).toBeGreaterThanOrEqual(0);
  });

  it('rounds to one decimal place', () => {
    const out = fleschKincaidGrade('The sun is bright today.');
    expect(out.toString()).toMatch(/^-?\d+(\.\d)?$/);
  });
});
