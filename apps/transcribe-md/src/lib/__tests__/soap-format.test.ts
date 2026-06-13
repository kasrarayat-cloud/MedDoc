// ============================================================================
// SOAP formatting helpers — pinned on the 2026-06-13 live-voice prod-smoke
// defects: the empty Assessment and the Plan rendered 4,5,6,8,9.
// ============================================================================

import { describe, expect, it } from 'vitest';

import {
  EMPTY_SECTION_PLACEHOLDER,
  renumberOrderedLists,
  stripEmptySectionPlaceholder,
} from '../soap-format';

describe('renumberOrderedLists — Plan numbering holes', () => {
  it('the real smoke Plan (4,5,6,8,9 surviving) renumbers to 1..5 contiguous', () => {
    const soap = [
      '## Plan',
      '4. Continue lisinopril 20 mg daily.',
      '5. Start amlodipine 5 mg daily.',
      '6. Recheck blood pressure in 4 weeks.',
      '8. Continue atorvastatin.',
      '9. Lifestyle counselling given.',
    ].join('\n');
    expect(renumberOrderedLists(soap)).toBe(
      [
        '## Plan',
        '1. Continue lisinopril 20 mg daily.',
        '2. Start amlodipine 5 mg daily.',
        '3. Recheck blood pressure in 4 weeks.',
        '4. Continue atorvastatin.',
        '5. Lifestyle counselling given.',
      ].join('\n')
    );
  });

  it('resets the counter at each section header (Plan restarts at 1)', () => {
    const soap = [
      '## Subjective',
      '3. Third HPI point only one surviving.',
      '## Plan',
      '7. Only plan item.',
    ].join('\n');
    expect(renumberOrderedLists(soap)).toBe(
      ['## Subjective', '1. Third HPI point only one surviving.', '## Plan', '1. Only plan item.'].join('\n')
    );
  });

  it('never touches doses, dates, or prose ("3.5 mg", "12/05/2024", a year)', () => {
    const soap = [
      '## Plan',
      '5. Amlodipine 3.5 mg is not a list renumber target.',
      'Reviewed on 12/05/2024.',
      'In 2024 the patient started lisinopril.',
    ].join('\n');
    const out = renumberOrderedLists(soap);
    expect(out).toContain('1. Amlodipine 3.5 mg');
    expect(out).toContain('Reviewed on 12/05/2024.');
    expect(out).toContain('In 2024 the patient started lisinopril.');
  });

  it('leaves nested/indented items alone (only top-level renumbers)', () => {
    const soap = ['## Plan', '5. Parent item.', '  2. nested keeps its number.'].join('\n');
    const out = renumberOrderedLists(soap);
    expect(out).toContain('1. Parent item.');
    expect(out).toContain('  2. nested keeps its number.');
  });
});

describe('stripEmptySectionPlaceholder', () => {
  const SOAP = [
    '## Assessment',
    EMPTY_SECTION_PLACEHOLDER,
    '## Plan',
    '1. Item.',
  ];

  it('removes the placeholder from the targeted section block', () => {
    const out = stripEmptySectionPlaceholder(SOAP, 0);
    expect(out).toEqual(['## Assessment', '## Plan', '1. Item.']);
  });

  it('is a no-op when the section has no placeholder', () => {
    const clean = ['## Assessment', 'Real content.', '## Plan'];
    expect(stripEmptySectionPlaceholder(clean, 0)).toEqual(clean);
  });

  it('only strips within the targeted section, not a later one', () => {
    const two = ['## Assessment', 'content', '## Plan', EMPTY_SECTION_PLACEHOLDER];
    // Targeting Assessment (idx 0) must not remove Plan's placeholder.
    expect(stripEmptySectionPlaceholder(two, 0)).toEqual(two);
  });
});
