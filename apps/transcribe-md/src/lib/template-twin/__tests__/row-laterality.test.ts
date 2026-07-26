// ============================================================================
// STAGE 5 — row laterality, stamped from the document, enforced fail-closed.
// ----------------------------------------------------------------------------
// WM_IOV is ONE grid whose vein labels REPEAT: rows 1-13 are the right leg,
// 14-26 the left, and nothing in a row's own text says which. L4 renders it as
// two markdown tables. Offering both to all rows would let a right-leg value
// satisfy a left-leg row — real value, real citation, wrong row, and silent.
//
// So the leg is stamped at COMPILE time from the document's own heading rows
// (never inferred from ordering), and addressing is fail-closed on it.
// ============================================================================

import { describe, expect, it } from 'vitest';

import { matchMeasurementFact } from '../bridge-evidence';
import type { EncounterFact } from '../ir';

const sidedFact = (laterality: EncounterFact['laterality']): EncounterFact =>
  ({
    factId: 'ttfact_aaaaaaaaaaaaaaaaaaaaaaaa',
    sourceType: 'encounter_evidence',
    concept: 'measurement.diameter',
    value: 7,
    polarity: 'affirmed',
    temporality: 'current',
    experiencer: 'patient',
    laterality,
    number: 7,
    unit: 'mm',
    speaker: null,
    sourceTranscriptOffsets: null,
    audioTimestampSeconds: null,
    evidenceAnchorIds: ['ttev_1'],
    evidenceQuote: 'great saphenous vein at the saphenofemoral junction: diameter 7 millimeters',
    quality: { asr: 'unknown', evidence: 'direct' },
  }) as EncounterFact;

const match = (rowLaterality: 'right' | 'left' | 'unknown' | undefined, factSide: EncounterFact['laterality']) =>
  matchMeasurementFact({
    value: '7',
    segmentLabel: 'GSV at the SFJ',
    facts: [sidedFact(factSide)],
    rowLaterality,
  });

describe('same-sided fills', () => {
  it('a right fact fills a right row', () => {
    expect(match('right', 'right').ok).toBe(true);
  });
  it('a left fact fills a left row', () => {
    expect(match('left', 'left').ok).toBe(true);
  });
});

describe('CROSS-LEG CANARY — the error this exists to prevent', () => {
  it('a RIGHT fact offered to a LEFT row is REFUSED', () => {
    const r = match('left', 'right');
    expect(r.ok, 'a right-leg measurement filled a left-leg row').toBe(false);
    if (r.ok) return;
    expect(r.reason).toBe('laterality_mismatch');
  });

  it('a LEFT fact offered to a RIGHT row is REFUSED', () => {
    const r = match('right', 'left');
    expect(r.ok).toBe(false);
    if (r.ok) return;
    expect(r.reason).toBe('laterality_mismatch');
  });
});

describe('unmarked rows are fail-closed', () => {
  it('an UNKNOWN row refuses a sided fact — never a silent guess', () => {
    // A template with no leg headings: the document gave no signal, so filling
    // here would be a guess wearing a citation.
    const r = match('unknown', 'right');
    expect(r.ok).toBe(false);
    if (r.ok) return;
    expect(r.reason).toBe('row_laterality_unknown');
  });

  it('a BILATERAL fact does not fill a sided row', () => {
    const r = match('right', 'bilateral');
    expect(r.ok).toBe(false);
    if (r.ok) return;
    expect(r.reason).toBe('laterality_mismatch');
  });
});

describe('legacy callers are unaffected', () => {
  it('omitting rowLaterality applies no row-side constraint', () => {
    expect(match(undefined, 'right').ok).toBe(true);
  });
});
