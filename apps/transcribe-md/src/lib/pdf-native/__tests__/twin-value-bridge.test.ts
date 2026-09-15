// ============================================================================
// S2-4 — the value bridge (ruling #322): the twin's resolutions fill the
// twin-derived anchors 1:1 by fieldId; a value that cannot be placed is a
// FALLBACK trigger, never a drop.
// ============================================================================
import { describe, expect, it } from 'vitest';

import { resolvedValueToText, buildTwinFillTexts } from '../twin-value-bridge';
import type { PdfFillAnchor } from '../fill-engine';
import type { FieldResolution } from '@/lib/template-twin/ir';

const anchor = (key: string): PdfFillAnchor => ({
  key,
  label: key,
  page: 0,
  yTop: 700,
  yBottom: 688,
  firstLineX: 120,
  wrapX: 120,
  rightEdge: 558,
  fontSize: 9,
});

const res = (fieldId: string, value: FieldResolution['value']): FieldResolution => ({
  fieldId,
  status: value === null ? 'not_mentioned' : 'supported',
  value,
  sourceFactIds: value === null ? [] : ['ttfact_000000000000000000000001'],
  evidenceAnchorIds: value === null ? [] : ['a1'],
  selectedOptionOrdinal: null,
  reasonCode: 'x',
  clinicianReviewed: false,
});

const F1 = 'ttf_000000000000000000000001';
const F2 = 'ttf_000000000000000000000002';
const F3 = 'ttf_000000000000000000000003';

describe('resolvedValueToText', () => {
  it('renders string / number scalars', () => {
    expect(resolvedValueToText('Screening colonoscopy')).toBe('Screening colonoscopy');
    expect(resolvedValueToText(6)).toBe('6');
  });
  it('a boolean (checkbox) is UNPLACEABLE — never the literal "Yes"/"No"', () => {
    expect(resolvedValueToText(true)).toBeNull();
    expect(resolvedValueToText(false)).toBeNull();
  });
  it('joins a multi-select string list', () => {
    expect(resolvedValueToText(['Sigmoid', 'Cecum'])).toBe('Sigmoid; Cecum');
  });
  it('returns null for a table value (array of row records) — unplaceable', () => {
    expect(resolvedValueToText([{ site: 'sigmoid', size: '4mm' }])).toBeNull();
  });
});

describe('buildTwinFillTexts', () => {
  it('joins resolutions onto anchors by fieldId (1:1)', () => {
    const { texts, unplaceable } = buildTwinFillTexts(
      [res(F1, 'John Roe'), res(F2, 'Screening colonoscopy')],
      [anchor(F1), anchor(F2)],
      [],
    );
    expect(texts).toEqual({ [F1]: 'John Roe', [F2]: 'Screening colonoscopy' });
    expect(unplaceable).toEqual([]);
  });

  it('a value with no anchor is UNPLACEABLE (fallback), never dropped', () => {
    const { texts, unplaceable } = buildTwinFillTexts(
      [res(F1, 'John Roe'), res(F2, 'orphan value')],
      [anchor(F1)], // no anchor for F2
      [],
    );
    expect(texts).toEqual({ [F1]: 'John Roe' });
    expect(unplaceable).toEqual([F2]);
  });

  it('a value whose field is UNLOCATABLE is unplaceable even if an anchor key exists elsewhere', () => {
    const { unplaceable } = buildTwinFillTexts([res(F1, 'v')], [anchor(F1)], [F1]);
    expect(unplaceable).toEqual([F1]);
  });

  it('a non-scalar (table) value is unplaceable', () => {
    const { texts, unplaceable } = buildTwinFillTexts(
      [res(F1, [{ a: 'b' }])],
      [anchor(F1)],
      [],
    );
    expect(texts).toEqual({});
    expect(unplaceable).toEqual([F1]);
  });

  it('an EMPTY value (not_mentioned / blank) is silently skipped — nothing to place, no fallback', () => {
    const { texts, unplaceable } = buildTwinFillTexts(
      [res(F1, null), res(F2, '   '), res(F3, 'real')],
      [anchor(F1), anchor(F2), anchor(F3)],
      [],
    );
    expect(texts).toEqual({ [F3]: 'real' });
    expect(unplaceable).toEqual([]); // blanks do NOT force a fallback
  });
});
