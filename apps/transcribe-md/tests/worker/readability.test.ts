import { describe, expect, it } from 'vitest';

import {
  countSentences,
  countSyllables,
  countWords,
  fleschKincaidGrade,
  totalSyllables,
} from '@/worker/layers/readability';

describe('countWords', () => {
  it('counts single-word input', () => {
    expect(countWords('hello')).toBe(1);
  });
  it('counts whitespace-split words', () => {
    expect(countWords('The cat sat on the mat.')).toBe(6);
  });
  it('ignores pure-punctuation tokens', () => {
    expect(countWords('yes --- no')).toBe(2);
  });
  it('is zero for blank input', () => {
    expect(countWords('')).toBe(0);
    expect(countWords('   ')).toBe(0);
  });
});

describe('countSentences', () => {
  it('splits on . ? !', () => {
    expect(countSentences('One. Two? Three!')).toBe(3);
  });
  it('treats abbreviations as non-terminators', () => {
    expect(countSentences('Dr. Smith saw the patient. BP was 140/90.')).toBe(2);
  });
  it('returns 1 on a single sentence without punctuation', () => {
    expect(countSentences('plan is follow-up')).toBe(1);
  });
});

describe('countSyllables', () => {
  it('counts short words correctly', () => {
    expect(countSyllables('cat')).toBe(1);
    expect(countSyllables('simple')).toBe(2);
    expect(countSyllables('hello')).toBe(2);
  });
  it('handles silent trailing e', () => {
    expect(countSyllables('bake')).toBe(1);
    expect(countSyllables('hope')).toBe(1);
  });
  it('returns 1 minimum for any word', () => {
    expect(countSyllables('rhythm')).toBeGreaterThanOrEqual(1);
  });
});

describe('totalSyllables', () => {
  it('sums across words', () => {
    // "The cat sat on the mat." → 1+1+1+1+1+1 = 6
    expect(totalSyllables('The cat sat on the mat.')).toBe(6);
  });
});

describe('fleschKincaidGrade', () => {
  it('returns 0 for empty input', () => {
    expect(fleschKincaidGrade('')).toBe(0);
  });

  it('rates simple children-book prose low', () => {
    // "The cat sat on the mat." — the canonical low-grade string.
    const grade = fleschKincaidGrade('The cat sat on the mat.');
    expect(grade).toBeLessThan(3);
  });

  it('rates medical/technical prose high', () => {
    const grade = fleschKincaidGrade(
      'Hypertension can lead to cardiovascular complications including ' +
        'myocardial infarction, cerebrovascular accident, and nephropathy.'
    );
    // The canonical "dense clinical jargon" check — expect a hard read.
    expect(grade).toBeGreaterThan(12);
  });

  it('rates typical 8th-grade patient-summary prose near the 8 target', () => {
    const summary = [
      'We talked about your blood pressure today.',
      'Your numbers are a little high, so we are going to increase your medicine.',
      'Please take your new dose every morning.',
      'Come back in three months so we can recheck your numbers.',
    ].join(' ');
    const grade = fleschKincaidGrade(summary);
    // Comfortably at or below 8 so the Layer 7e acceptance threshold
    // doesn't flag it. A small tolerance range protects the test from
    // rewording drift.
    expect(grade).toBeLessThan(9);
    expect(grade).toBeGreaterThan(2);
  });
});
