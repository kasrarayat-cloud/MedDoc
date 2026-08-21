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
  // ⚠️ F5-e. PRODUCTION ALWAYS SETS THIS. `03-extract-entities.ts:254` types the
  // segment `z.string().min(1)` — REQUIRED — and instructs one entry per number,
  // so both halves of a dictated line carry the vessel. Omitting it here (as
  // this fixture did) modelled an extraction L3 cannot emit, which is the
  // wrong-universe class one field over from the quote it had already fixed.
  segment: string | null,
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
  segment,
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
    //
    // ⚠️ AND F5-e FOUND IT WAS STILL ONE FIELD SHORT. The quotes were right and
    // `segment` was absent, which L3's REQUIRED `min(1)` makes impossible. Both
    // facts now carry the vessel as structured data, exactly as production does.
    facts.push(fact('measurement.diameter', Number(m[3]), side, `${side === 'right' ? 'Right' : 'Left'} ${vessel}: diameter ${m[3]} millimeters`, vessel));
    facts.push(fact('measurement.reflux_time', Number(m[4]), side, `reflux time ${m[4]} seconds`, vessel));
  }
  return { cells, facts };
}

// F5-i: the derivation REFUSES rather than falling back, so unwrap explicitly.
// This is also the file's non-vacuity control — a form that stopped deriving
// would otherwise parse to zero cells and every arm below would pass on nothing.
const derived = deriveVerificationEncounter(ownersForm());
if (!derived.ok) throw new Error(`expected a derived encounter, got refusal: ${derived.reason}`);
const text = derived.text;
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

  it('⚠️ REQUIRED — F5-e: the reflux column FILLS, on both legs', () => {
    // ⚠️ INVERTED DELIBERATELY, 2026-08-21, WHICH IS WHAT THE PREVIOUS VERSION
    // OF THIS ARM ASKED FOR IN WRITING ("a reflux cell FILLED — F5-e may have
    // landed; invert this arm deliberately"). Its history, kept because this arm
    // has now been wrong in BOTH directions:
    //
    //   until 2026-08-20  "reflux fills"      — PASSED, on a quote production
    //                                            never produces (both facts got
    //                                            the whole dictated sentence)
    //   2026-08-20        "reflux CANNOT fill" — correct about the quote, and
    //                                            still one field short: it built
    //                                            facts with no `segment`, which
    //                                            L3's REQUIRED min(1) forbids
    //   now               "reflux fills"      — with BOTH production-shaped
    //                                            quotes AND the segment present
    //
    // The fix restored a DROPPED FIELD rather than relaxing this matcher:
    // `segment` reached encounter-facts and was spent on the factId hash alone.
    const reflux = results.filter((x) => x.c.kind === 'reflux');
    expect(reflux.length, 'no reflux cells at all — arm is vacuous').toBe(
      VESSELS.length * 2,
    );
    const unfilled = reflux.filter((x) => !x.r.ok);
    expect(
      unfilled.map((x) => `${x.c.side} ${x.c.vessel}: ${x.r.ok ? '' : x.r.reason}`),
      'a reflux cell still refuses — F5-e is not fully landed',
    ).toEqual([]);
    // PER LEG, so a fix that rescued one side would not read as success.
    for (const side of ['right', 'left'] as const) {
      expect(
        reflux.filter((x) => x.c.side === side && x.r.ok).length,
        `no reflux cell filled on the ${side} leg`,
      ).toBe(VESSELS.length);
    }
  });

  it('⚠️ REQUIRED — F5-e: and it is the SEGMENT that rescued it, not a weaker matcher', () => {
    // THE DISCRIMINATION CONTROL. The arm above proves reflux cells fill; it
    // cannot say WHY, and a `segmentCongruent` that had simply stopped requiring
    // congruence would satisfy it just as well — while letting a GSV fact fill an
    // SSV row on a signed document.
    //
    // So: rebuild the SAME facts with `segment: null` — the pre-fix projection,
    // nothing else changed — and require the refusal to come straight back.
    const refluxNoSegment = facts
      .filter((f) => f.concept === 'measurement.reflux_time')
      .map((f) => ({ ...f, segment: null }));
    const anyFilled = cells
      .filter((c) => c.kind === 'reflux')
      .map((c) =>
        matchMeasurementFact({
          value: c.value,
          segmentLabel: c.vessel,
          facts: refluxNoSegment,
          rowLaterality: c.side,
        }),
      );
    expect(anyFilled.length).toBeGreaterThan(0); // non-vacuity
    expect(
      anyFilled.every((r) => !r.ok),
      'a reflux cell filled with NO segment and a bare quote — congruence is no ' +
        'longer being required, which is a wrong-vessel citation waiting to happen',
    ).toBe(true);
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
    //
    // ⚠️ F5-e MOVED THE AUTHORITY. This arm used to read the evidence QUOTE,
    // which was the only anatomy carrier before the segment was emitted. It is
    // no longer a complete one: a reflux fact's quote is "reflux time 0.128
    // seconds" and names no vessel, so a quote-only assertion FAILS on a cell
    // that filled perfectly correctly. Assert the SEGMENT — the field the
    // matcher actually addresses on — and fall back to the quote only where a
    // fact carries no segment, so neither carrier can rot unnoticed.
    const aagsv = results.filter((x) => x.c.vessel.startsWith('AAGSV') && x.r.ok);
    expect(aagsv.length, 'no AAGSV cell filled at all — arm is vacuous').toBeGreaterThan(0);
    // Non-vacuity on the CARRIER: at least one of these must be a reflux cell,
    // or this arm is only re-testing the diameter column it already covered.
    expect(
      aagsv.some((x) => x.c.kind === 'reflux'),
      'no AAGSV *reflux* cell filled — the arm cannot see the column F5-e fixed',
    ).toBe(true);
    for (const x of aagsv) {
      const f = x.r.ok ? x.r.match.fact : null;
      const carrier = f?.segment ?? f?.evidenceQuote ?? '';
      expect(
        carrier,
        `AAGSV cell cited a non-AAGSV fact: ${carrier}`,
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
