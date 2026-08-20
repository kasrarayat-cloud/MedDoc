import { describe, expect, it } from 'vitest';
import { valueFromFact } from '../validation';
import type { EncounterFact, SemanticMapping, TemplateField } from '../ir';

/**
 * #135 — THE DOCUMENT CARRIES THE CITED FACT'S VALUE, NOT THE MODEL'S FREE TEXT.
 *
 * The cell and the validator's expectation were two INDEPENDENT renderings of
 * one number: `bridge-fill.ts` wrote the model's raw cell text, the validator
 * re-derived the fact's own value, and the comparison at
 * `validation/index.ts:291` is strict `===`.
 *
 * ⚠️ TONIGHT'S EXACT CELLS, measured on the owner's production template:
 * `deriveVerificationEncounter` emits `(3.1 + k*0.13).toFixed(2)`, which is
 * non-canonical exactly TWICE across twenty diameters — k=0 -> "3.10" and
 * k=10 -> "4.40" — and those are Right and Left `GSV at the SFJ`. They were the
 * only two blocking cells. The other eighteen round-tripped unchanged, which is
 * why the failure looked like a property of one label rather than of the
 * rendering.
 */
const field = (kind: string): TemplateField =>
  ({ fieldId: 'f1', kind, rendererBinding: { bindingType: 'table_cell' } } as unknown as TemplateField);

const mapping = { fieldId: 'f1', clinicalConcept: 'measurement.diameter' } as unknown as SemanticMapping;

const fact = (value: string, num: number): EncounterFact =>
  ({
    factId: 'ttfact_x', sourceType: 'encounter_evidence', concept: 'measurement.diameter',
    value, polarity: 'affirmed', temporality: 'current', experiencer: 'patient',
    laterality: 'right', number: num, unit: 'mm', speaker: null,
    sourceTranscriptOffsets: null, audioTimestampSeconds: null,
    evidenceAnchorIds: ['a1'], evidenceQuote: 'Right GSV at the SFJ: diameter 3.10 millimeters',
    quality: { asr: 'high', evidence: 'direct' },
  } as unknown as EncounterFact);

describe('#135 — one derivation, both callers', () => {
  it('⚠️ TONIGHT\'S CELLS: the model text and the fact value DIFFER as strings', () => {
    // This is the defect, stated as data. Both are the same number.
    for (const [modelText, factValue] of [['3.10', '3.1'], ['4.40', '4.4']] as const) {
      expect(Number(modelText)).toBe(Number(factValue));
      expect(modelText).not.toBe(factValue);
    }
  });

  it('the validator re-derives the FACT value, which is what the cell must carry', () => {
    expect(valueFromFact(field('narrative_text'), mapping, fact('3.1', 3.1))).toBe('3.1');
    expect(valueFromFact(field('narrative_text'), mapping, fact('4.4', 4.4))).toBe('4.4');
  });

  it('⚠️ THE BRIDGE CALLS THAT SAME FUNCTION — not a second rendering', () => {
    // A source assertion, deliberately: the defect was two independent
    // derivations, and only the CALL SITE can show there is now one.
    const src = readFileSync(
      join(__dirname, '..', 'bridge-fill.ts'),
      'utf8',
    );
    const code = src.split('\n').filter((l) => !l.trim().startsWith('//')).join('\n');
    expect(code).toMatch(/valueFromFact\(field, mapping, matched\.match\.fact\)/);
    // and it must NOT write the raw model text on the mapped path
    expect(code).not.toMatch(/status: 'supported',\s*\n\s*value,\s*\n/);
  });

  it('a value with no canonical rendering is REFUSED, never written', () => {
    // null from valueFromFact means nothing to assert; writing it would
    // guarantee the validator rejects the cell.
    expect(valueFromFact(field('narrative_text'), mapping, fact(123 as unknown as string, 123))).toBeNull();
  });
});

/**
 * ⚠️ EVERY FIELD KIND THE CHANGED PATH CAN CARRY — the arm the first version
 * did NOT have, and its absence hid a real defect.
 *
 * The first gate exercised `valueFromFact` at ONE kind (`narrative_text`) — the
 * only kind that returns a string. The bridge guard then tested
 * `typeof canonical !== 'string'`, which is TRUE for every `number`-kind cell
 * and for every `measurement` whose fact carries no unit, so those cells were
 * silently blanked and recorded as `not_mentioned`.
 *
 * The refutation pass reached it by SURGERY ON THE BLANK FIXTURE (a row label
 * changed to `Perforator count`, which the compiler infers as kind `number`),
 * because the owner's live form is 52 of 52 `narrative_text` and could never
 * have shown it. A census over the kinds is what makes the blindness
 * impossible to repeat.
 */
describe('the canonical value survives for EVERY kind, not just strings', () => {
  const kinds: Array<[string, EncounterFact, unknown]> = [
    ['narrative_text', fact('3.1', 3.1), '3.1'],
    ['number', numberFact(3), 3],
    ['checkbox', affirmedFact(), true],
  ];

  it('the census is non-vacuous — more than one kind is exercised', () => {
    expect(new Set(kinds.map(([k]) => k)).size).toBeGreaterThan(1);
  });

  for (const [kind, f, expected] of kinds) {
    it(`⚠️ ${kind}: valueFromFact yields a NON-NULL value the bridge must write`, () => {
      const v = valueFromFact(field(kind), mapping, f);
      expect(v, `${kind} produced null — the bridge would blank this cell`).not.toBeNull();
      expect(v).toEqual(expected);
    });

    it(`${kind}: a "is it a string?" guard would have DISCARDED it`, () => {
      const v = valueFromFact(field(kind), mapping, f);
      // The defect, stated as data: for every non-string kind the old predicate
      // was true and the cell was refused.
      if (kind !== 'narrative_text') expect(typeof v).not.toBe('string');
    });
  }

  it('⚠️ THE BRIDGE GUARD TESTS NULLITY, NOT TYPE', () => {
    const src = readFileSync(join(__dirname, '..', 'bridge-fill.ts'), 'utf8');
    const code = src.split('\n').filter((l) => !l.trim().startsWith('//')).join('\n');
    expect(code).toMatch(/if \(canonical === null\)/);
    expect(code).not.toMatch(/typeof canonical !== 'string'/);
    // and it must never stringify — that reintroduces ASSERTION_NOT_SUPPORTED
    // and NUMBER_INVALID together.
    expect(code).not.toMatch(/String\(canonical\)/);
  });
});

function numberFact(n: number): EncounterFact {
  return {
    factId: 'ttfact_n', sourceType: 'encounter_evidence', concept: 'measurement.diameter',
    value: String(n), polarity: 'affirmed', temporality: 'current', experiencer: 'patient',
    laterality: 'right', number: n, unit: null, speaker: null,
    sourceTranscriptOffsets: null, audioTimestampSeconds: null,
    evidenceAnchorIds: ['a1'], evidenceQuote: 'Perforator count 3',
    quality: { asr: 'high', evidence: 'direct' },
  } as unknown as EncounterFact;
}

function affirmedFact(): EncounterFact {
  return {
    factId: 'ttfact_b', sourceType: 'encounter_evidence', concept: 'measurement.diameter',
    value: 'yes', polarity: 'affirmed', temporality: 'current', experiencer: 'patient',
    laterality: 'right', number: null, unit: null, speaker: null,
    sourceTranscriptOffsets: null, audioTimestampSeconds: null,
    evidenceAnchorIds: ['a1'], evidenceQuote: 'present',
    quality: { asr: 'high', evidence: 'direct' },
  } as unknown as EncounterFact;
}

import { readFileSync } from 'node:fs';
import { join } from 'node:path';
