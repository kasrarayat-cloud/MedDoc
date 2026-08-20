// ============================================================================
// F5-d — REPRODUCTION. Runs BEFORE any fix is written, per the ruled acceptance
// shape: "REPRODUCE BEFORE YOU FIX. One script, running the REAL matcher on the
// REAL derived encounter against THE TWO BLOCKED FIELDS. Name the mechanism at
// FILE:LINE before a line of fix is written."
//
// TONIGHT'S REFUSAL, verbatim (2026-08-20 15:25):
//
//   [template-twin:synthetic] BLOCKED compiled=617d6de9…:
//     ttf_e119ecd84bdd6b6c0b802967:ASSERTION_NOT_SUPPORTED,
//     ttf_12e093b32f6ad5da739ada7d:ASSERTION_NOT_SUPPORTED
//
// Both blockers are the SAME LABEL — `GSV at the SFJ` — once per leg, both
// `measurement.diameter`, both `extraction`.
//
// ⚠️ THE FILED PRIME SUSPECT IS `segmentCongruent` TOKEN OVERLAP
// (bridge-evidence.ts:131-142, `'aagsv'.includes('gsv')`). This file REFUTES it
// with the real function and names a different mechanism. Everything here calls
// SHIPPED code — nothing is re-implemented, because an SQL re-implementation of
// a shipped predicate already answered 19 where the real one answered 15.
// ============================================================================

import { describe, expect, it } from 'vitest';

import {
  deriveVerificationEncounter,
  type EncounterSourceField,
} from '../verification-encounter';
import { matchMeasurementFact } from '../bridge-evidence';
import { validateTemplateTwin } from '../validation';
import type {
  EncounterFact,
  FieldResolution,
  SemanticMapping,
  TemplateField,
} from '../ir';

/**
 * ⚠️ THE OWNER'S REAL FORM SHAPE, copied from the F5-c gate
 * (`gate-derived-encounter-exercises-the-form.test.ts`), which read it from
 * production on 2026-08-19. An invented fixture here would be the wrong-universe
 * failure this repository has paid for twice.
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
const PLACEHOLDERS = [
  'Saphenous Tributary Vein &lt;&lt;insert location&gt;&gt;',
  'Saphenous Tributary Vein &lt;&lt;insert location&gt;&gt;',
  'Saphenous Tributary Vein &lt;&lt;insert location&gt;&gt;',
];

const ownersForm = (): EncounterSourceField[] => [
  ...[...VESSELS, ...PLACEHOLDERS].flatMap((l) => [
    { originalLabel: l, clinicalConcept: 'measurement.diameter' },
    { originalLabel: 'REFLUX TIME (ms)', clinicalConcept: 'measurement.reflux_time' },
  ]),
  { originalLabel: 'CLINICAL INDICATIONS: Choose an item.', clinicalConcept: 'chief_complaint' },
  { originalLabel: 'Address', clinicalConcept: null },
];

/** Every `<Side> <label>: diameter <v> millimeters` the REAL generator emits. */
function dictatedDiameters(): { side: string; label: string; diameter: string }[] {
  const text = deriveVerificationEncounter(ownersForm());
  const out: { side: string; label: string; diameter: string }[] = [];
  for (const side of ['Right', 'Left']) {
    for (const label of VESSELS) {
      const m = new RegExp(
        `${side} ${label.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}: diameter ([0-9.]+) millimeters`,
      ).exec(text);
      if (m) out.push({ side, label, diameter: m[1]! });
    }
  }
  return out;
}

// ─────────────────────────────────────────────────────────────────────────────
// ARM A — WHICH CELLS CARRY A TRAILING ZERO, measured from the real generator.
// ─────────────────────────────────────────────────────────────────────────────

describe('F5-d ARM A — the two blocked cells are the two trailing-zero diameters', () => {
  const dictated = dictatedDiameters();

  it('non-vacuity: the real generator addresses all 20 vessel cells', () => {
    // Without this, every assertion below could pass over an empty set.
    expect(dictated).toHaveLength(VESSELS.length * 2);
  });

  it('⚠️ EXACTLY TWO of the 20 diameters survive a number round-trip CHANGED', () => {
    // The predicate is the mechanism itself, stated as a question about data:
    // does the dictated text survive String(Number(text))?
    const lossy = dictated.filter((d) => String(Number(d.diameter)) !== d.diameter);
    expect(lossy.map((d) => `${d.side} ${d.label} = ${d.diameter}`)).toEqual([
      'Right GSV at the SFJ = 3.10',
      'Left GSV at the SFJ = 4.40',
    ]);
  });

  it('⚠️ and they are BOTH legs of ONE label — exactly the shape of the refusal', () => {
    const lossy = dictated.filter((d) => String(Number(d.diameter)) !== d.diameter);
    expect(new Set(lossy.map((d) => d.label))).toEqual(new Set(['GSV at the SFJ']));
    expect(new Set(lossy.map((d) => d.side))).toEqual(new Set(['Right', 'Left']));
  });

  it('the OTHER 18 round-trip unchanged — so the predicate discriminates', () => {
    const clean = dictated.filter((d) => String(Number(d.diameter)) === d.diameter);
    expect(clean).toHaveLength(18);
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// ARM B — THE REAL VALIDATOR, on the real values, paired with its control.
// ─────────────────────────────────────────────────────────────────────────────

const SHA = 'c'.repeat(64);
const NOW = '2026-08-20T15:25:00.000Z';

function cellField(seed: string, kind: TemplateField['kind']): TemplateField {
  return {
    fieldId: `ttf_${seed.repeat(24).slice(0, 24)}`,
    kind,
    originalLabel: 'GSV at the SFJ',
    labelSource: 'tag',
    displayOrder: 0,
    detectionStatus: 'certified',
    allowedOptions: [],
    rendererBinding: {
      partName: 'word/document.xml',
      bindingType: 'table_cell',
      path: `/document/${seed}`,
      ordinal: 0,
      sdtId: '1',
      tag: 'synthetic',
      alias: null,
      legacyName: null,
      rowLaterality: 'right' as const,
      tableIndex: 0,
      rowIndex: 1,
      cellIndex: 1,
      repeatAncestorPath: null,
      sourceControlSha256: SHA,
      originalContentSha256: SHA,
    },
    required: false,
    unknownPolicy: 'blank',
    clinicallyMaterial: false,
    criticality: 'routine',
    tableId: null,
    rowPrototype: false,
  };
}

function diameterMapping(f: TemplateField): SemanticMapping {
  return {
    fieldId: f.fieldId,
    sourceType: 'extraction',
    clinicalConcept: 'measurement.diameter',
    expectedDataType: f.kind === 'measurement' ? 'measurement' : 'text',
    polarityBehavior: 'value_only',
    temporality: 'current',
    laterality: 'optional',
    unitPolicy: f.kind === 'measurement' ? 'required' : 'not_applicable',
    approvedSynonyms: [],
    required: false,
    blankPolicy: 'blank',
    unknownPolicy: 'blank',
    practiceDefault: null,
    status: 'certified',
  };
}

/**
 * A fact EXACTLY as L3 extraction stores it, read from the compiled version's
 * own `latestSyntheticTestManifest` on production 2026-08-20:
 *
 *     measurement.diameter | 3.1  | 3.1  | mm      | right
 *     measurement.diameter | 3.23 | 3.23 | mm      | right
 *
 * ⚠️ NOTE `value` IS THE CANONICAL NUMERIC STRING, NOT THE DICTATED TEXT.
 * The dictation said "3.10 millimeters" and the stored fact value is `"3.1"` —
 * the number round-tripped through JSON. That single character is the defect.
 */
function diameterFact(seed: string, dictated: string): EncounterFact {
  return {
    factId: `ttfact_${seed.repeat(24).slice(0, 24)}`,
    sourceType: 'encounter_evidence',
    concept: 'measurement.diameter',
    value: String(Number(dictated)),
    polarity: 'affirmed',
    temporality: 'current',
    experiencer: 'patient',
    laterality: 'right',
    number: Number(dictated),
    unit: 'mm',
    speaker: 'Doctor',
    sourceTranscriptOffsets: { start: 0, end: 20 },
    audioTimestampSeconds: null,
    evidenceAnchorIds: [`anchor-${seed}`],
    evidenceQuote: `Right GSV at the SFJ: diameter ${dictated} millimeters`,
    quality: { asr: 'high', evidence: 'direct' },
  };
}

/** ⚠️ THE RESOLUTION `bridge-fill.ts` USED TO BUILD — `value` is the markdown
 *  cell's BARE STRING: "no unit, no reformat" (its own comment at the time).
 *  Since F5-d(b) the shipped bridge derives the value from the cited fact
 *  instead, so this is a HISTORICAL shape kept deliberately: it is what the
 *  arms below feed the validator to prove the validator never stopped refusing
 *  it. It is NOT what the bridge produces today. */
function bridgedResolution(f: TemplateField, fact: EncounterFact, cellText: string): FieldResolution {
  return {
    fieldId: f.fieldId,
    status: 'supported',
    value: cellText,
    sourceFactIds: [fact.factId],
    evidenceAnchorIds: [...fact.evidenceAnchorIds],
    selectedOptionOrdinal: null,
    reasonCode: 'table_cell_measurement',
    clinicianReviewed: false,
  } as FieldResolution;
}

function codesFor(kind: TemplateField['kind'], dictated: string): string[] {
  const f = cellField('e', kind);
  const m = diameterMapping(f);
  const fact = diameterFact('e', dictated);
  const res = bridgedResolution(f, fact, dictated);
  return validateTemplateTwin({
    fields: [f],
    mappings: [m],
    facts: [fact],
    resolutions: [res],
    now: NOW,
  }).issues
    .filter((i) => i.severity === 'blocking')
    .map((i) => i.code);
}

// ⚠️ ENUMERATE THE ROUTES — AND THEN SAY WHICH ONE PRODUCTION TAKES.
// A table cell could compile as `narrative_text` or as `measurement`, and the
// two go down DIFFERENT branches of `valueFromFact`. Measured on production
// 2026-08-20: all 52 measurement fields of this compiled version are
// `narrative_text`, so that is the only route under test here. Proving the
// other one would be proving a system nobody ships.
const PRODUCTION_CELL_KIND = 'narrative_text' as const;

// ⚠️ THE FIX LANDED (F5-d(b), ruling #135) AND THESE TWO ARMS ARE DELIBERATELY
// **NOT** INVERTED. Read this before "finishing the job" they ask for.
//
// The instruction below said they must become `.not.toContain(...)` once the
// bridge and the validator agree. That instruction was written before the fix
// DIRECTION was ruled, and inverting them now would be wrong twice over:
//
//  1. ⚠️ THEY DO NOT CALL THE BRIDGE. `bridgedResolution` above is a HAND-BUILT
//     mirror of what bridge-fill.ts used to write. A mirror cannot invert when
//     the real thing is fixed — it would have to be edited to say the opposite,
//     which proves nothing about shipped code.
//  2. **INVERTING THEM WOULD DELETE THE ONLY PROOF THAT THE GATE STAYED
//     STRICT.** Ruling #135 forbids fixing F5-d by making the validator compare
//     numerically. Read as they stand, these arms assert exactly that the
//     validator STILL refuses a resolution whose text diverges from its cited
//     fact — i.e. that the fix was a tightening. That is worth more after the
//     fix than before it.
//
// THE INVERSION LIVES WHERE IT CAN BE HONEST — driving the real bridge into the
// real validator, in gate-f5d-bridge-writes-what-the-validator-derives.test.ts.
// Mutation-proved: weakening this comparison reddens that gate's own
// anti-loosening arm.
describe('F5-d ARM B — the REAL validator on the REAL production route', () => {
  it('⚠️ "3.10" — the PRE-FIX bridge shape — is refused ASSERTION_NOT_SUPPORTED', () => {
    // THIS IS THE DEFECT, CHARACTERISED — and, since F5-d(b), also the
    // anti-loosening guard. See the block above for why it was not inverted.
    expect(codesFor(PRODUCTION_CELL_KIND, '3.10')).toContain('ASSERTION_NOT_SUPPORTED');
  });

  it('⚠️ "4.40" — the other leg, same PRE-FIX shape — is refused too', () => {
    expect(codesFor(PRODUCTION_CELL_KIND, '4.40')).toContain('ASSERTION_NOT_SUPPORTED');
  });

  it('THE CONTROL: "3.23", its immediate neighbour, is NOT refused', () => {
    // Without this arm the two above would be satisfied by a validator that
    // refuses everything, which is a different bug and the same green.
    expect(codesFor(PRODUCTION_CELL_KIND, '3.23')).not.toContain('ASSERTION_NOT_SUPPORTED');
  });

  it('THE CONTROL, second form: all 18 canonical diameters are accepted', () => {
    const clean = dictatedDiameters()
      .filter((d) => String(Number(d.diameter)) === d.diameter)
      .map((d) => d.diameter);
    expect(clean.length).toBe(18);
    for (const v of clean) {
      expect(codesFor(PRODUCTION_CELL_KIND, v), `unexpectedly refused: ${v}`).not.toContain(
        'ASSERTION_NOT_SUPPORTED',
      );
    }
  });

  it('⚠️ THE DISCRIMINATOR IS THE TEXT, NOT THE NUMBER — both sides agree numerically', () => {
    // The refusal is not about the VALUE being wrong. `numbersEqual` in the
    // matcher already proved the cell and the fact hold the identical number to
    // 1e-9. Only their STRING forms differ, and only the validator looks at
    // those. Stated as an assertion so the claim is checkable, not rhetoric.
    expect(Number('3.10')).toBe(Number('3.1'));
    expect('3.10').not.toBe('3.1');
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// ARM C — THE FILED PRIME SUSPECT, RUN RATHER THAN ARGUED.
// ─────────────────────────────────────────────────────────────────────────────

describe('F5-d ARM C — segmentCongruent is NOT what refuses these two cells', () => {
  /** Facts for all 20 dictated segments, as extraction would yield them. */
  function allFacts(): EncounterFact[] {
    return dictatedDiameters().map((d, i) => ({
      ...diameterFact(String.fromCharCode(97 + (i % 26)), d.diameter),
      factId: `ttfact_${String(i).padStart(24, '0')}`,
      laterality: d.side === 'Right' ? 'right' : 'left',
      evidenceQuote: `${d.side} ${d.label}: diameter ${d.diameter} millimeters`,
    })) as EncounterFact[];
  }

  it('⚠️ the REAL matcher MATCHES both blocked cells — the bridge is not the refuser', () => {
    const facts = allFacts();
    for (const [side, value] of [
      ['right', '3.10'],
      ['left', '4.40'],
    ] as const) {
      const r = matchMeasurementFact({
        value,
        segmentLabel: 'GSV at the SFJ',
        facts,
        rowLaterality: side,
      });
      expect(r.ok, `matcher refused ${side} ${value}: ${!r.ok ? r.reason : ''}`).toBe(true);
    }
  });

  it('⚠️ token overlap IS real (`aagsv` contains `gsv`) and is DEFEATED by numeric identity', () => {
    // The suspect's premise is true — but every diameter in this encounter is
    // globally unique, so `numbersEqual` filters to one fact before congruence
    // can matter. That is why it is not the mechanism HERE.
    const diameters = dictatedDiameters().map((d) => d.diameter);
    expect(new Set(diameters).size).toBe(diameters.length);
  });

  it('the matcher fills EVERY one of the 20 cells — so no cell is blank from it', () => {
    const facts = allFacts();
    const refused = dictatedDiameters().filter((d) => {
      const r = matchMeasurementFact({
        value: d.diameter,
        segmentLabel: d.label,
        facts,
        rowLaterality: d.side === 'Right' ? 'right' : 'left',
      });
      return !r.ok;
    });
    expect(refused.map((d) => `${d.side} ${d.label}`)).toEqual([]);
  });
});
