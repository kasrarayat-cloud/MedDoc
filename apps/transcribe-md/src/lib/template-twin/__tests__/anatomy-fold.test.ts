// ============================================================================
// STAGE 3 — the abbreviation <-> spoken-form fold (ADDRESSING only).
// ----------------------------------------------------------------------------
// Template rows say "GSV at the SFJ"; dictation says "great saphenous vein at
// the saphenofemoral junction". Without the fold every measurement fact missed
// its row while looking, in the logs, exactly like missing evidence.
//
// This decides which ROW a fact is offered to. It never decides whether the
// value is written — that still needs factSatisfiesMapping and a numeric match,
// both untouched.
// ============================================================================

import { describe, expect, it } from 'vitest';

import { foldAnatomy, matchMeasurementFact } from '../bridge-evidence';
import type { EncounterFact } from '../ir';

const fact = (over: Partial<EncounterFact>): EncounterFact =>
  ({
    factId: 'ttfact_aaaaaaaaaaaaaaaaaaaaaaaa',
    sourceType: 'encounter_evidence',
    concept: 'measurement.diameter',
    value: 7,
    polarity: 'affirmed',
    temporality: 'current',
    experiencer: 'patient',
    laterality: 'right',
    number: 7,
    unit: 'mm',
    speaker: null,
    sourceTranscriptOffsets: null,
    audioTimestampSeconds: null,
    evidenceAnchorIds: ['ttev_1'],
    evidenceQuote: 'Right great saphenous vein at the saphenofemoral junction: diameter 7 millimeters',
    quality: { asr: 'unknown', evidence: 'direct' },
    ...over,
  }) as EncounterFact;

describe('foldAnatomy', () => {
  it.each([
    ['great saphenous vein at the saphenofemoral junction', 'gsv at the sfj'],
    ['small saphenous vein at the saphenopopliteal junction', 'ssv at the spj'],
    ['anterior accessory great saphenous vein', 'aagsv'],
    ['posterior accessory great saphenous vein', 'pagsv'],
  ])('%s -> %s', (input, want) => {
    expect(foldAnatomy(input)).toBe(want);
  });

  it('is idempotent on already-abbreviated text', () => {
    expect(foldAnatomy('GSV at the SFJ')).toBe('gsv at the sfj');
    expect(foldAnatomy(foldAnatomy('GSV at the SFJ'))).toBe('gsv at the sfj');
  });

  it('does NOT collapse distinct veins', () => {
    // The failure mode a fuzzy matcher would eventually produce.
    expect(foldAnatomy('small saphenous vein')).not.toBe(foldAnatomy('great saphenous vein'));
    expect(foldAnatomy('anterior accessory great saphenous vein')).not.toBe(
      foldAnatomy('great saphenous vein'),
    );
  });
});

describe('the fold lets a spoken fact reach an abbreviated row', () => {
  it('matches BOTH directions', () => {
    // Row label abbreviated, fact spoken.
    const r1 = matchMeasurementFact({
      value: '7',
      segmentLabel: 'GSV at the SFJ',
      facts: [fact({ concept: 'measurement.diameter' })],
    });
    expect(r1.ok).toBe(true);

    // Row label spoken, fact abbreviated.
    const r2 = matchMeasurementFact({
      value: '7',
      segmentLabel: 'great saphenous vein at the saphenofemoral junction',
      facts: [fact({ evidenceQuote: 'GSV at the SFJ diameter 7 mm', concept: 'measurement.diameter' })],
    });
    expect(r2.ok).toBe(true);
  });

  it('still refuses a DIFFERENT vein — addressing widened, evidence did not', () => {
    const r = matchMeasurementFact({
      value: '7',
      segmentLabel: 'SSV at the SPJ',
      facts: [fact({ concept: 'measurement.diameter' })], // a GSV fact
    });
    expect(r.ok).toBe(false);
  });

  it('still refuses when the NUMBER differs', () => {
    const r = matchMeasurementFact({
      value: '9.9',
      segmentLabel: 'GSV at the SFJ',
      facts: [fact({})],
    });
    expect(r.ok).toBe(false);
  });
});
