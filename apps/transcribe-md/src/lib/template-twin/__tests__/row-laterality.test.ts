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

import { matchMeasurementFact, rowLateralityVerdict } from '../bridge-evidence';
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

// ============================================================================
// THE BASELINE HAD NO SUCH RULE.
// ----------------------------------------------------------------------------
// The bridge refused cross-leg fills from the start. The resolver baseline
// underneath it did not consult the row's laterality at all, so on a synthetic
// encounter where L4 rendered the legs the other way round, three right-leg
// REFLUX TIME cells were filled from left-leg facts. The value was real and the
// citation was real; only the ROW was wrong — which is the precise failure this
// stage exists to prevent, arriving through the door nobody had locked. It
// surfaced downstream as ASSERTION_NOT_SUPPORTED, which reads like missing
// evidence rather than a misaddressed row.
//
// Both callers now go through one function, so a rule that holds for one holds
// for the other by construction.
// ============================================================================

describe('one rule, both callers', () => {
  it('a sided row takes its own side only', () => {
    expect(rowLateralityVerdict({ laterality: 'right' }, 'right')).toBe('ok');
    expect(rowLateralityVerdict({ laterality: 'left' }, 'right')).toBe('laterality_mismatch');
    expect(rowLateralityVerdict({ laterality: 'left' }, 'left')).toBe('ok');
    expect(rowLateralityVerdict({ laterality: 'right' }, 'left')).toBe('laterality_mismatch');
  });

  it('a bilateral fact does not fill a sided row', () => {
    // "No DVT bilaterally" is not a right-leg reflux measurement.
    expect(rowLateralityVerdict({ laterality: 'bilateral' }, 'right')).toBe('laterality_mismatch');
    expect(rowLateralityVerdict({ laterality: 'not_applicable' }, 'left')).toBe(
      'laterality_mismatch',
    );
  });

  it('an unmarked row refuses a sided value, and accepts an unsided one', () => {
    expect(rowLateralityVerdict({ laterality: 'right' }, 'unknown')).toBe('row_laterality_unknown');
    expect(rowLateralityVerdict({ laterality: 'bilateral' }, 'unknown')).toBe('ok');
  });

  it('the resolver does not address fixed-grid rows at all — the bridge does', () => {
    // The first attempt at this bug added the same laterality filter to the
    // resolver. That was still wrong: the resolver has no row information
    // beyond the leg, and in a 26-row grid every reflux cell shares ONE
    // concept, so it could tell right from left and still not tell the SFJ row
    // from the knee row. It guessed, and 33 cells came back
    // needs_clinician_input about an encounter that had said nothing about
    // them. Row addressing belongs to the bridge, which matches by vein label
    // and then requires the fact to satisfy laterality AND segment.
    const { readFileSync } = require('node:fs') as typeof import('node:fs');
    const { join } = require('node:path') as typeof import('node:path');
    const src = readFileSync(join(__dirname, '..', 'resolver', 'index.ts'), 'utf-8');
    expect(src, 'the resolver still resolves fixed-grid cells from raw facts').toContain(
      "if (field.rendererBinding.bindingType === 'table_cell' && !field.rowPrototype)",
    );
    // A repeating-row prototype must NOT be caught by that rule — it expands one
    // row per fact, so there is nothing to address.
    expect(src).toContain('!field.rowPrototype');
  });
});
