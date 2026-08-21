import { describe, expect, it } from 'vitest';
import { projectEncounterFacts } from '../encounter-facts';
import { matchMeasurementFact } from '../bridge-evidence';
import { EncounterFactSchema, type EncounterFact } from '../ir';

/**
 * F5-e — THE ANATOMICAL SEGMENT REACHES THE ADDRESSING PREDICATE.
 *
 * THE DEFECT. L3 extracts a `segment` per measurement — REQUIRED, `min(1)`
 * (`03-extract-entities.ts:254`) — and emits ONE ENTRY PER NUMBER, so a line
 * dictating "Right GSV at the SFJ: diameter 3.10 millimeters, reflux time 0.110
 * seconds" produces two entries that BOTH name the vessel. The projection then
 * dropped it: `segment` reached `add()` and was spent only on the factId hash.
 *
 * Downstream, `segmentCongruent` had to recover anatomy from the evidence QUOTE.
 * That works for the diameter half and never for the reflux half, whose quote is
 * a bare "reflux time 0.110 seconds". Measured on production's own manifest:
 * anatomy in 20 of 20 diameter quotes and **0 of 20** reflux quotes. Every
 * reflux cell refused `no_supporting_fact`, and the twin's first real filled
 * document rendered that whole column BLANK — 55 of 80 fields empty, with
 * `needsReviewCount = 0`, so nothing flagged it to the doctor.
 *
 * ⚠️ WHAT THIS GATE IS FOR. The fix WIDENS a haystack, and a widened addressing
 * predicate is how a value lands in the WRONG ROW of a signed document. So
 * "reflux fills" is the cheap half; these arms exist for the expensive half —
 * that it fills from the RIGHT VESSEL, that the segment is what rescued it, and
 * that nesting abbreviations cannot alias one vessel onto another.
 */

const ENTITY = (
  segment: string,
  metric: 'diameter' | 'reflux_time',
  value: number,
  unit: string,
  sourceSpan: string,
  laterality: 'left' | 'right' = 'right',
) => ({ segment, laterality, metric, value, unit, sourceSpan });

/** The production shape: ONE dictated line -> TWO entries, both carrying the
 *  vessel, and only the diameter's quote naming it. */
const project = (
  entities: ReturnType<typeof ENTITY>[],
  contextText = 'Right GSV at the SFJ: diameter 3.10 millimeters, reflux time 0.110 seconds.',
): EncounterFact[] =>
  projectEncounterFacts({
    mode: 'text',
    contextText,
    entities: { measurements: entities },
  });

const REAL_PAIR = [
  ENTITY('GSV at the SFJ', 'diameter', 3.1, 'mm', 'Right GSV at the SFJ: diameter 3.10 millimeters'),
  ENTITY('GSV at the SFJ', 'reflux_time', 0.11, 'seconds', 'reflux time 0.110 seconds'),
];

describe('F5-e — the segment reaches addressing', () => {
  // ── the projection ───────────────────────────────────────────────────────
  it('⚠️ REQUIRED: the projection EMITS the segment, on every measurement fact', () => {
    // The arm that would have gone red for the whole defect. `segment` reached
    // `add()` and died there; nothing downstream could tell.
    const facts = project(REAL_PAIR);
    expect(facts.length, 'projection produced no facts — arm is vacuous').toBe(2);
    for (const f of facts) {
      expect(f.segment, `fact ${f.concept} lost its segment`).toBe('GSV at the SFJ');
    }
  });

  it('the reflux fact carries the vessel in `segment` and NOT in its quote', () => {
    // Pins the asymmetry the defect rests on. If a future L3 change starts
    // putting anatomy in reflux quotes, this arm says so — and the fix would
    // then be masked rather than needed.
    const [diameter, reflux] = project(REAL_PAIR);
    expect(diameter.evidenceQuote).toMatch(/GSV/i);
    expect(reflux.evidenceQuote).not.toMatch(/GSV/i);
    expect(reflux.segment).toMatch(/GSV/i);
  });

  // ── the fill ─────────────────────────────────────────────────────────────
  it('⚠️ REQUIRED: a reflux cell FILLS from a fact whose quote names no vessel', () => {
    const facts = project(REAL_PAIR);
    const r = matchMeasurementFact({
      value: '0.11',
      segmentLabel: 'GSV at the SFJ',
      facts,
      rowLaterality: 'right',
    });
    expect(r.ok, r.ok ? '' : `reflux refused: ${r.reason}`).toBe(true);
    expect(r.ok && r.match.fact.concept).toBe('measurement.reflux_time');
    expect(r.ok && r.match.laterality).toBe('right');
  });

  it('⚠️ REQUIRED: and the SEGMENT is what rescued it — strip it and the refusal returns', () => {
    // THE DISCRIMINATION CONTROL. Without this, a `segmentCongruent` that had
    // simply stopped requiring congruence would satisfy the arm above.
    const facts = project(REAL_PAIR).map((f) => ({ ...f, segment: null }));
    const r = matchMeasurementFact({
      value: '0.11',
      segmentLabel: 'GSV at the SFJ',
      facts,
      rowLaterality: 'right',
    });
    expect(r.ok).toBe(false);
    expect(!r.ok && r.reason).toBe('no_supporting_fact');
  });

  // ── vessel identity, BOTH directions ─────────────────────────────────────
  // The split-family rule: asserting only the side the fix added lets a future
  // edit remove the side that was already there.
  it('⚠️ REQUIRED: a GSV row does NOT bind an AAGSV fact — `aagsv` CONTAINS `gsv`', () => {
    // The substring hazard, and it is not hypothetical: under `hay.includes(t)`
    // a **GSV Below Knee** row was congruent with an **AAGSV at the Proximal
    // Thigh** fact — different vessel, different level, sharing only a suffix.
    // Only numeric equality stood in the way, and that is not a vessel check.
    const facts = project([
      ENTITY('AAGSV at the Proximal Thigh', 'reflux_time', 0.11, 'seconds', 'reflux time 0.110 seconds'),
    ]);
    const r = matchMeasurementFact({
      value: '0.11',
      segmentLabel: 'GSV Below Knee',
      facts,
      rowLaterality: 'right',
    });
    expect(
      r.ok,
      'a GSV row bound an AAGSV fact — the substring hole is back, and it puts ' +
        'one vessel’s measurement under another’s heading',
    ).toBe(false);
  });

  it('⚠️ REQUIRED: and the AAGSV row still binds its OWN fact — the fix is not just stricter', () => {
    // The happy-path control. A predicate that refused everything would pass the
    // arm above; this is the direction that proves it still WORKS.
    const facts = project([
      ENTITY('AAGSV at the Proximal Thigh', 'reflux_time', 0.11, 'seconds', 'reflux time 0.110 seconds'),
    ]);
    const r = matchMeasurementFact({
      value: '0.11',
      segmentLabel: 'AAGSV at the Proximal Thigh',
      facts,
      rowLaterality: 'right',
    });
    expect(r.ok, r.ok ? '' : `AAGSV row refused its own fact: ${r.reason}`).toBe(true);
    expect(r.ok && r.match.fact.segment).toBe('AAGSV at the Proximal Thigh');
  });

  it('⚠️ REQUIRED: a singular row label still matches a PLURAL segment', () => {
    // FOUND BY THE ADVERSARIAL PASS, ON THIS BRANCH'S OWN DIFF. The whole-token
    // hardening that closes the `aagsv`/`gsv` nesting hole is STRICTER, and
    // strictness breaks things: "Perforator" stopped matching "perforators",
    // which the substring test used to catch.
    //
    // Not hypothetical vocabulary — `specialty-guidance.ts:119` ("GSV / SSV /
    // perforators") and `ultrasound-report-template.ts:150` ("Perforators:
    // location …") steer the model to the PLURAL, so that is what a dictation
    // says. Measured: production's only certified template has 0 of 80 labels
    // mentioning a perforator, so this is unreachable there TODAY — pinned
    // because the next form is not this form, and the failure mode is the same
    // silent blank column F5-e already cost a doctor.
    const facts = project([
      ENTITY('medial calf perforators', 'reflux_time', 0.42, 'seconds', 'reflux time 0.420 seconds'),
    ]);
    const r = matchMeasurementFact({
      value: '0.42',
      segmentLabel: 'Perforator',
      facts,
      rowLaterality: 'right',
    });
    expect(r.ok, r.ok ? '' : `a plural segment refused a singular row: ${r.reason}`).toBe(true);
  });

  it('and stemming did NOT reopen the nesting hole it sits beside', () => {
    // The pair. Plural tolerance is a widening, so it is asserted together with
    // the narrowing it must not undo — otherwise the cure for one silent
    // wrong-row bug quietly restores the other.
    const facts = project([
      ENTITY('AAGSV at the Proximal Thigh', 'reflux_time', 0.42, 'seconds', 'reflux time 0.420 seconds'),
    ]);
    const r = matchMeasurementFact({
      value: '0.42',
      segmentLabel: 'GSV Below Knee',
      facts,
      rowLaterality: 'right',
    });
    expect(r.ok, 'stemming reopened the aagsv/gsv nesting hole').toBe(false);
  });

  it('the spoken long form still folds to the template’s abbreviation', () => {
    // `segment` is "the anatomical location AS SPOKEN", so it can arrive fully
    // spelled out. Addressing must fold it exactly as it folds a quote.
    const facts = project([
      ENTITY(
        'great saphenous vein at the saphenofemoral junction',
        'reflux_time',
        0.11,
        'seconds',
        'reflux time 0.110 seconds',
      ),
    ]);
    const r = matchMeasurementFact({
      value: '0.11',
      segmentLabel: 'GSV at the SFJ',
      facts,
      rowLaterality: 'right',
    });
    expect(r.ok, r.ok ? '' : `spoken long form refused: ${r.reason}`).toBe(true);
  });

  // ── identity + compatibility ─────────────────────────────────────────────
  it('⚠️ REQUIRED: factIds do NOT churn — the segment was already in the hash', () => {
    // Claimed in the ledger row, so it is asserted rather than asserted-in-prose.
    // `sourceIdentity` hashed `segment` before it was ever emitted, so emitting
    // it changes no identity. A churn here would orphan every stored citation.
    const [diameter, reflux] = project(REAL_PAIR);
    // ⚠️ THESE TWO LITERALS ARE NOT PINNED FROM THIS TREE. They were computed on
    // a DETACHED WORKTREE AT `origin/main` — the pre-fix projection — and pasted
    // here. Pinning whatever the post-fix code happens to emit would assert only
    // that the code agrees with itself; taking them from before the change is
    // what makes this a non-churn CONTROL. A churn would orphan every stored
    // citation, since `template_twin_fill_manifests` references facts by id.
    expect(diameter.factId).toBe('ttfact_473f47a330053ac79f037a89');
    expect(reflux.factId).toBe('ttfact_ee38e56d27ac7b6061ebf6f9');
  });

  it('a fact constructed WITHOUT a segment still parses under .strict()', () => {
    // Back-compat: the schema is `.strict()`, so a new REQUIRED field would have
    // rejected every previously-constructed fact and every existing fixture.
    const parsed = EncounterFactSchema.parse({
      factId: 'ttfact_000000000000000000000000',
      sourceType: 'encounter_evidence',
      concept: 'chief_complaint',
      value: 'leg swelling',
      polarity: 'affirmed',
      temporality: 'current',
      experiencer: 'patient',
      laterality: 'unknown',
      number: null,
      unit: null,
      speaker: null,
      sourceTranscriptOffsets: null,
      audioTimestampSeconds: null,
      evidenceAnchorIds: ['ttev_000000000000000000000000'],
      evidenceQuote: 'leg swelling',
      quality: { asr: 'high', evidence: 'direct' },
    });
    expect(parsed.segment).toBeNull();
  });

  it('a non-measurement fact carries a NULL segment, not an empty string', () => {
    // `''` would be a token-free haystack contribution that reads as "present".
    const facts = projectEncounterFacts({
      mode: 'text',
      contextText: 'Patient reports leg swelling.',
      entities: { chief_complaint: { statement: 'leg swelling', evidence_quote: 'leg swelling' } },
    });
    expect(facts.length).toBeGreaterThan(0);
    expect(facts[0].segment).toBeNull();
  });
});
