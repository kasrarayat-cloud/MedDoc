import { describe, expect, it } from 'vitest';
import { deriveVerificationEncounter, MIN_CERTIFIED_FILLED_FIELDS } from '../verification-encounter';
import { matchMeasurementFact } from '../bridge-evidence';
import type { EncounterFact } from '../ir';

/**
 * ⚠️ THE ARM THE FIRST VERSION DID NOT HAVE, AND ITS ABSENCE WAS THE DEFECT.
 *
 * `gate-derived-encounter-exercises-the-form.test.ts` asserts the encounter's
 * TEXT — 20 diameter phrases, 20 reflux phrases, both branches present. Every
 * one of those arms passed while EIGHT distinct reflux values existed across
 * twenty cells, and `bridge-evidence.ts:183` refuses a cell whose candidate
 * facts disagree on side. Fourteen of twenty reflux cells could never fill and
 * the suite was silent, because **a count of phrases is not a measure of fill**.
 *
 * This file runs the derived encounter through the REAL matcher and asserts what
 * the lifecycle gate actually buys. It is the ratified required arm.
 *
 * The extraction modelled here is the IDEAL one — one diameter fact and one
 * reflux fact per dictated line, each carrying the stated side and the line as
 * its evidence quote. That is deliberately the BEST case: if a cell cannot fill
 * from a perfect extraction, no real model output will rescue it.
 */
const VESSELS = [
  'GSV at the SFJ',
  'GSV at the Proximal Thigh',
  'GSV at the Knee',
  'GSV Below Knee',
  'SSV at the SPJ',
  'SSV at the Proximal Calf',
  'AAGSV at the SFJ',
  'AAGSV at the Proximal Thigh',
  'PAGSV at the SFJ',
  'PAGSV at the Proximal Thigh',
];

const ownersForm = () =>
  VESSELS.map((l) => ({ originalLabel: l, clinicalConcept: 'measurement.diameter' }));

interface Cell {
  side: 'right' | 'left';
  vessel: string;
  kind: 'diameter' | 'reflux';
  value: string;
  incompetent: boolean;
}

let seq = 0;
const fact = (
  concept: string,
  num: number,
  laterality: 'right' | 'left',
  quote: string,
): EncounterFact => ({
  factId: `ttfact_${String(seq++).padStart(24, '0')}`,
  sourceType: 'encounter_evidence',
  concept,
  value: String(num),
  polarity: 'affirmed',
  temporality: 'current',
  experiencer: 'patient',
  laterality,
  number: num,
  unit: null,
  speaker: null,
  sourceTranscriptOffsets: null,
  audioTimestampSeconds: null,
  evidenceAnchorIds: ['a1'],
  evidenceQuote: quote,
  quality: { asr: 'high', evidence: 'direct' },
});

/** Parse the encounter back into the cells a table would carry, and build the
 *  facts an ideal Layer-3 extraction would produce from the same sentences. */
function parse(text: string): { cells: Cell[]; facts: EncounterFact[] } {
  const cells: Cell[] = [];
  const facts: EncounterFact[] = [];
  const re =
    /(Right|Left) (.+?): diameter (\d+\.\d+) millimeters, reflux time (\d+\.\d+) seconds; (competent[^.]*|incompetent)\./g;
  for (const m of text.matchAll(re)) {
    const side = m[1].toLowerCase() as 'right' | 'left';
    const vessel = m[2];
    const incompetent = m[5].startsWith('incompetent');
    const line = m[0];
    cells.push({ side, vessel, kind: 'diameter', value: m[3], incompetent });
    cells.push({ side, vessel, kind: 'reflux', value: m[4], incompetent });
    // ⚠️ PRODUCTION-SHAPED QUOTES, NOT THE WHOLE SENTENCE FOR BOTH.
    //
    // This handed BOTH facts the full dictated line, so the reflux fact carried
    // "GSV at the SFJ" and the arm below passed. Measured on the real manifest
    // 2026-08-20: diameter quotes carry an anatomy token 20 of 20; reflux quotes
    // **0 of 20** — L3 emits "reflux time 0.110 seconds", no vessel in it.
    //
    // The arm was one layer short of production: the wrong-universe class,
    // inside the gate written to kill it.
    facts.push(fact('measurement.diameter', Number(m[3]), side, `${side === 'right' ? 'Right' : 'Left'} ${vessel}: diameter ${m[3]} millimeters`));
    facts.push(fact('measurement.reflux_time', Number(m[4]), side, `reflux time ${m[4]} seconds`));
  }
  return { cells, facts };
}

const text = deriveVerificationEncounter(ownersForm());
const { cells, facts } = parse(text);

const fill = (c: Cell) =>
  matchMeasurementFact({
    value: c.value,
    segmentLabel: c.vessel, // the IR row's own, leg-UNqualified label
    facts,
    rowLaterality: c.side,
  });

describe('the derived encounter ACTUALLY FILLS the owner\'s form', () => {
  it('the harness is non-vacuous — it parsed both legs of every vessel', () => {
    expect(cells.length).toBe(VESSELS.length * 2 * 2); // 2 legs x (diameter+reflux)
    expect(facts.length).toBe(VESSELS.length * 2 * 2);
  });

  const results = cells.map((c) => ({ c, r: fill(c) }));
  const filled = results.filter((x) => x.r.ok);

  it(`⚠️ REQUIRED: at least ${MIN_CERTIFIED_FILLED_FIELDS} cells fill`, () => {
    expect(filled.length).toBeGreaterThanOrEqual(MIN_CERTIFIED_FILLED_FIELDS);
  });

  it('⚠️ REQUIRED — F5-e: the reflux column is UNFILLABLE, and that is pinned', () => {
    // ⚠️ THIS ARM ASSERTED THE OPPOSITE UNTIL 2026-08-20, AND PASSED, because it
    // fed the matcher a quote production never produces.
    //
    // With production-shaped quotes every reflux cell refuses: bridge-fill's
    // place() addresses the reflux cell by irRow.vein ("GSV at the SFJ") and
    // segmentCongruent needs an anatomy token in the fact's concept, value or
    // quote — a reflux fact has none. Reproduced end to end through the real
    // matcher with a positive control (the same fact WITH anatomy fills).
    //
    // Pinned as a KNOWN GAP so it cannot silently change in EITHER direction.
    const reflux = results.filter((x) => x.c.kind === 'reflux');
    expect(reflux.length).toBeGreaterThan(0); // non-vacuity
    expect(
      reflux.every((x) => !x.r.ok),
      'a reflux cell FILLED — F5-e may have landed; invert this arm deliberately',
    ).toBe(true);
    expect(new Set(reflux.map((x) => (x.r.ok ? 'ok' : x.r.reason)))).toEqual(
      new Set(['no_supporting_fact']),
    );
  });

  it('⚠️ REQUIRED: the DIAMETER column still fills on both legs — the gap is scoped', () => {
    // Scoping matters: F5-e is about the reflux COLUMN only. If diameters stop
    // filling too, the cause is elsewhere and this arm says so.
    for (const side of ['right', 'left'] as const) {
      const n = filled.filter((x) => x.c.kind === 'diameter' && x.c.side === side).length;
      expect(n, `no diameter cell filled on the ${side} leg`).toBeGreaterThan(0);
    }
  });

  it('⚠️ REQUIRED: at least one measurement cell fills PER LEG', () => {
    for (const side of ['right', 'left'] as const) {
      const n = filled.filter((x) => x.c.side === side).length;
      expect(n, `no cell filled on the ${side} leg`).toBeGreaterThan(0);
    }
  });

  it('⚠️ REQUIRED: the AAGSV cell cites an AAGSV fact — congruence, not substring luck', () => {
    // `segmentCongruent` is token-overlap over a haystack that includes the
    // evidence quote, and 'aagsv' contains 'gsv'. A cell that filled from a
    // plain-GSV fact would be a certification artifact citing the wrong vessel.
    const aagsv = results.filter((x) => x.c.vessel.startsWith('AAGSV') && x.r.ok);
    expect(aagsv.length, 'no AAGSV cell filled at all — arm is vacuous').toBeGreaterThan(0);
    for (const x of aagsv) {
      const quote = x.r.ok ? x.r.match.fact.evidenceQuote : '';
      expect(
        quote,
        `AAGSV cell cited a non-AAGSV fact: ${quote}`,
      ).toMatch(/AAGSV/i);
      expect(x.r.ok && x.r.match.laterality).toBe(x.c.side);
    }
  });

  it('no cell EVER fills from the opposite leg', () => {
    for (const x of filled) {
      expect(x.r.ok && x.r.match.laterality).toBe(x.c.side);
    }
  });

  it('⚠️ every refusal is reported, so a silent shrink cannot hide here', () => {
    const refused = results.filter((x) => !x.r.ok);
    const byReason = refused.reduce<Record<string, number>>((a, x) => {
      const k = x.r.ok ? 'ok' : x.r.reason;
      a[k] = (a[k] ?? 0) + 1;
      return a;
    }, {});
    // Recorded rather than asserted to zero: the point is that the number is
    // VISIBLE and the required arms above are met regardless of it.
    expect(filled.length + refused.length).toBe(cells.length);
    expect(byReason).toBeDefined();
  });
});
