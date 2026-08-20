// ============================================================================
// F5-d(b) GATE — the bridge writes what the validator re-derives.
// ----------------------------------------------------------------------------
// Ruling #135. F5-d(a) reproduced the mechanism and named it at FILE:LINE; this
// is the fix's proof, RED-PROVEN AGAINST TONIGHT'S EXACT REFUSAL:
//
//     [template-twin:synthetic] BLOCKED compiled=617d6de9…:
//       ttf_e119ecd84bdd6b6c0b802967:ASSERTION_NOT_SUPPORTED,
//       ttf_12e093b32f6ad5da739ada7d:ASSERTION_NOT_SUPPORTED
//
// Both blockers are `GSV at the SFJ`, once per leg, because
// verification-encounter.ts:132 emits `(3.1 + k*0.13).toFixed(2)` and exactly
// two of the twenty diameters come out non-canonical: k=0 -> "3.10" (Right)
// and k=10 -> "4.40" (Left).
//
// ⚠️ WHY THIS FILE EXISTS AT ALL, GIVEN F5-d(a) ALREADY HAS A REPRO.
// That repro builds its resolution BY HAND — a faithful mirror of what
// bridge-fill.ts wrote, but a mirror. It therefore CANNOT go green when the
// bridge is fixed, and it cannot go red if the bridge regresses. Nothing in
// this repository connected the real bridge to the real validator: the one
// test that renders a bridged document (bridge-fill.test.ts:196,341) passes a
// STUBBED `validation` object with `issues: []`. So the seam where this defect
// lived had no end-to-end coverage in either direction.
//
// EVERYTHING HERE IS SHIPPED CODE: compileTemplateDocx on the customer's real
// WM IOV template, the real bridgeNumericTableCells, the real
// mergeFieldResolutions, the real validateTemplateTwin, the real
// renderTemplateDocx. Nothing is re-implemented.
// ============================================================================

import { readFileSync } from 'node:fs';
import path from 'node:path';

import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';

import { compileTemplateDocx, renderTemplateDocx } from '@/lib/note-template-docx';

import { bridgeNumericTableCells, mergeFieldResolutions } from '../bridge-fill';
import { expectedDataTypeForFieldKind } from '../semantic-mapping';
import { validateTemplateTwin } from '../validation';
import {
  FieldResolutionSchema,
  type EncounterFact,
  type FieldResolution,
  type SemanticMapping,
  type TemplateDocIR,
  type TemplateField,
  type TemplateTwinValidationResult,
} from '../ir';

const WM_IOV_PATH = path.resolve(process.cwd(), '../../WM IOV Template.docx');
const wmIovBytes = new Uint8Array(readFileSync(WM_IOV_PATH));

const NOW = '2026-08-20T21:00:00.000Z';

let ir: TemplateDocIR;
beforeAll(() => {
  ir = compileTemplateDocx(wmIovBytes);
});

// Right block = rowIndex 1..13, Left block = 15..27 (0/14 are leg headers).
// GSV-at-SFJ is row 1 (right) and row 15 (left). diameter = cellIndex 1.
const RIGHT_SFJ_ROW = 1;
const LEFT_SFJ_ROW = 15;
const DIAMETER_COL = 1;

function cell(rowIndex: number, cellIndex: number): TemplateField {
  const f = ir.fields.find(
    (x) =>
      x.rendererBinding.bindingType === 'table_cell' &&
      x.rendererBinding.rowIndex === rowIndex &&
      x.rendererBinding.cellIndex === cellIndex,
  );
  if (!f) throw new Error(`no table_cell field at row ${rowIndex} col ${cellIndex}`);
  return f;
}

/**
 * A fact EXACTLY as L3 stores it — measured on production 2026-08-20 from the
 * compiled version's own latestSyntheticTestManifest:
 *
 *     measurement.diameter | value="3.1" | number=3.1 | unit="mm" | right
 *
 * ⚠️ `value` IS THE CANONICAL NUMERIC STRING AND THE QUOTE IS THE DICTATED
 * TEXT. That one-character difference between "3.1" and "3.10" is the entire
 * defect, and it only exists because the quote and the value travel separately.
 */
function diameterFact(
  seed: string,
  dictated: string,
  laterality: 'left' | 'right',
): EncounterFact {
  const side = laterality === 'right' ? 'Right' : 'Left';
  return {
    factId: `ttfact_${seed.repeat(24).slice(0, 24)}`,
    sourceType: 'encounter_evidence',
    concept: 'measurement.diameter',
    value: String(Number(dictated)),
    polarity: 'affirmed',
    temporality: 'current',
    experiencer: 'patient',
    laterality,
    number: Number(dictated),
    unit: 'mm',
    speaker: 'Doctor',
    sourceTranscriptOffsets: { start: 0, end: 20 },
    audioTimestampSeconds: null,
    evidenceAnchorIds: [`anchor-${seed}`],
    evidenceQuote: `${side} GSV at the SFJ: diameter ${dictated} millimeters`,
    quality: { asr: 'high', evidence: 'direct' },
  } as EncounterFact;
}

/** A certified mapping for EVERY field, so the validator's per-field
 *  MAPPING_MISSING (blocking) does not drown the signal we are here to read.
 *  Data types come from the SHIPPED kind->type map, so a field kind this gate
 *  never anticipated cannot silently take an incompatible mapping. */
function mappingsForAllFields(): SemanticMapping[] {
  return ir.fields.map((f) => {
    const isDiameterCell =
      f.rendererBinding.bindingType === 'table_cell' &&
      f.rendererBinding.cellIndex === DIAMETER_COL;
    return {
      fieldId: f.fieldId,
      sourceType: 'extraction',
      clinicalConcept: isDiameterCell ? 'measurement.diameter' : 'measurement.reflux_time',
      expectedDataType: expectedDataTypeForFieldKind(f.kind) ?? 'text',
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
    } as SemanticMapping;
  });
}

function blankBaseline(): FieldResolution[] {
  return ir.fields.map((f) =>
    FieldResolutionSchema.parse({
      fieldId: f.fieldId,
      status: 'not_mentioned',
      value: null,
      sourceFactIds: [],
      evidenceAnchorIds: [],
      selectedOptionOrdinal: null,
      reasonCode: 'blank_when_unsaid',
      clinicianReviewed: false,
    }),
  );
}

/** The note as L4 writes it: the model renders the DICTATED text in the cell. */
function noteWith(rightDiameter: string, leftDiameter: string): string {
  return [
    'IMPRESSION',
    'Bilateral great saphenous vein reflux.',
    '',
    '| VEIN | DIAMETER (mm) | REFLUX TIME (seconds) |',
    '| --- | --- | --- |',
    `| Right GSV at the SFJ | ${rightDiameter} | [not documented] |`,
    `| Left GSV at the SFJ | ${leftDiameter} | [not documented] |`,
  ].join('\n');
}

interface RunResult {
  bridged: FieldResolution[];
  blocking: Array<{ fieldId: string | null; code: string }>;
  merged: FieldResolution[];
}

/** THE WHOLE PRODUCTION CHAIN: bridge -> merge -> validate. */
function run(rightDictated: string, leftDictated: string): RunResult {
  const facts = [
    diameterFact('a', rightDictated, 'right'),
    diameterFact('b', leftDictated, 'left'),
  ];
  const mappings = mappingsForAllFields();
  const bridged = bridgeNumericTableCells({
    facts,
    mappings,
    ir,
    filledNote: noteWith(rightDictated, leftDictated),
  });
  const merged = mergeFieldResolutions(ir, blankBaseline(), bridged);
  const result = validateTemplateTwin({
    fields: ir.fields,
    mappings,
    facts,
    resolutions: merged,
    tables: ir.tables,
    // The route the real refusal came down: the synthetic certification test.
    allowUncertifiedForSyntheticTest: true,
    now: NOW,
  });
  return {
    bridged,
    merged,
    blocking: result.issues
      .filter((i) => i.severity === 'blocking')
      .map((i) => ({ fieldId: i.fieldId, code: i.code })),
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// 1 · TONIGHT'S REFUSAL, GONE — and non-vacuously so.
// ─────────────────────────────────────────────────────────────────────────────

describe('F5-d(b) — the two blocked GSV-at-SFJ cells now pass the validator', () => {
  it('⚠️ UNIVERSE CONTROL: these are THE two field IDs production refused', () => {
    // Without this arm, everything below is a proof about "two cells that look
    // like the blocked ones". Field IDs compile deterministically from the
    // template structure, so the customer's real WM IOV docx must reproduce the
    // exact ids the production refusal named:
    //
    //   [template-twin:synthetic] BLOCKED compiled=617d6de9…:
    //     ttf_e119ecd84bdd6b6c0b802967:ASSERTION_NOT_SUPPORTED,
    //     ttf_12e093b32f6ad5da739ada7d:ASSERTION_NOT_SUPPORTED
    //
    // Cross-checked against production's own stored round-trip proof, which
    // places those two ids at w:tbl[0]/w:tr[1]/w:tc[1] and w:tr[15]/w:tc[1] —
    // the coordinates this gate addresses. If the template or the compiler ever
    // moves them, this arm goes red rather than the gate quietly testing two
    // arbitrary cells.
    expect(cell(RIGHT_SFJ_ROW, DIAMETER_COL).fieldId).toBe('ttf_e119ecd84bdd6b6c0b802967');
    expect(cell(LEFT_SFJ_ROW, DIAMETER_COL).fieldId).toBe('ttf_12e093b32f6ad5da739ada7d');
  });

  it('NON-VACUITY: the bridge actually FILLS both cells', () => {
    // Without this arm, "no ASSERTION_NOT_SUPPORTED" is satisfied perfectly by
    // a bridge that fills nothing at all — a blank cell asserts nothing, so it
    // can never be unsupported. That is the cheapest possible false green here
    // and it is exactly what an over-eager fail-closed fix would produce.
    const { bridged } = run('3.10', '4.40');
    const ids = new Set(bridged.map((r) => r.fieldId));
    expect(ids.has(cell(RIGHT_SFJ_ROW, DIAMETER_COL).fieldId)).toBe(true);
    expect(ids.has(cell(LEFT_SFJ_ROW, DIAMETER_COL).fieldId)).toBe(true);
    expect(bridged.every((r) => r.status === 'supported')).toBe(true);
  });

  it('⚠️ THE FIX: neither trailing-zero cell is ASSERTION_NOT_SUPPORTED any more', () => {
    const { blocking } = run('3.10', '4.40');
    const right = cell(RIGHT_SFJ_ROW, DIAMETER_COL).fieldId;
    const left = cell(LEFT_SFJ_ROW, DIAMETER_COL).fieldId;
    const unsupported = blocking
      .filter((i) => i.code === 'ASSERTION_NOT_SUPPORTED')
      .map((i) => i.fieldId);
    expect(unsupported).not.toContain(right);
    expect(unsupported).not.toContain(left);
    // And the shape of tonight's refusal — TWO of them, one per leg — is gone
    // entirely, not merely reduced to one.
    expect(unsupported).toEqual([]);
  });

  it('⚠️ the cell carries the CITED FACT\'S value, not the model\'s text', () => {
    // This is the tightening ruling #135 chose, stated as a value rather than a
    // principle: the document says "3.1" because that is what the evidence
    // says, and "3.10" was only ever the model's formatting of it.
    const { bridged } = run('3.10', '4.40');
    const byId = new Map(bridged.map((r) => [r.fieldId, r]));
    expect(byId.get(cell(RIGHT_SFJ_ROW, DIAMETER_COL).fieldId)?.value).toBe('3.1');
    expect(byId.get(cell(LEFT_SFJ_ROW, DIAMETER_COL).fieldId)?.value).toBe('4.4');
  });

  it('⚠️ THE RETURN TYPE IS WRITTEN THROUGH, NOT STRINGIFIED — the `number` route', () => {
    // ENUMERATE THE ROUTES. Production's 52 measurement fields are all
    // `narrative_text` (measured 2026-08-20), where the derivation returns a
    // string and `String(derived)` is a NO-OP. So the single most likely
    // half-landed version of this fix — deriving correctly and then
    // stringifying, which is what anyone writes when a type complains — is
    // INVISIBLE on the only route production takes.
    //
    // It is not invisible here. A `number` field derives a NUMBER, and
    // renderer.ts:809-815 refuses a string for that kind with
    // FIELD_VALUE_INVALID, killing the whole render. This arm is the only thing
    // in the suite that can tell the two apart.
    const field = cell(RIGHT_SFJ_ROW, DIAMETER_COL);
    const numberIr: TemplateDocIR = {
      ...ir,
      fields: ir.fields.map((f) =>
        f.fieldId === field.fieldId ? { ...f, kind: 'number' as const } : f,
      ),
    };
    const fact = diameterFact('a', '3.10', 'right');
    const mappings = mappingsForAllFields().map((m) =>
      m.fieldId === field.fieldId
        ? { ...m, expectedDataType: 'number' as const, unitPolicy: 'not_applicable' as const }
        : m,
    );
    // A `number` field derives `number !== null && unit === null ? number : null`,
    // so the unit must be absent for this route to produce a value at all.
    const unitless = { ...fact, unit: null } as EncounterFact;
    const bridged = bridgeNumericTableCells({
      facts: [unitless],
      mappings,
      ir: numberIr,
      filledNote: noteWith('3.10', '[not documented]'),
    });
    const written = bridged.find((r) => r.fieldId === field.fieldId);
    expect(written, 'the number route must still fill').toBeDefined();
    expect(typeof written?.value).toBe('number');
    expect(written?.value).toBe(3.1);
  });

  it('⚠️ A DICTATED NUMBER NEVER BECOMES A TICKED BOX — the `checkbox` route', () => {
    // A DEFECT THIS FIX WOULD HAVE INTRODUCED, caught by reading the diff
    // rather than by any test. Deriving from the fact means the derivation
    // returns what the FIELD KIND says, and `checkbox` derives a BOOLEAN from
    // the fact's POLARITY — nothing to do with the number. So a numeric table
    // cell compiled as a checkbox would take a dictated "3.10", cite a real
    // affirmed fact, satisfy the validator (which re-derives the same boolean)
    // and render ☒.
    //
    // Pre-fix that was inert: the bridge wrote the string "3.10", the validator
    // derived `true`, and `true === "3.10"` blocked it. The fix removed the
    // accident that was protecting it, so the protection is now explicit.
    const field = cell(RIGHT_SFJ_ROW, DIAMETER_COL);
    const checkboxIr: TemplateDocIR = {
      ...ir,
      fields: ir.fields.map((f) =>
        f.fieldId === field.fieldId ? { ...f, kind: 'checkbox' as const } : f,
      ),
    };
    const bridged = bridgeNumericTableCells({
      facts: [diameterFact('a', '3.10', 'right')],
      mappings: mappingsForAllFields().map((m) =>
        m.fieldId === field.fieldId ? { ...m, expectedDataType: 'boolean' as const } : m,
      ),
      ir: checkboxIr,
      filledNote: noteWith('3.10', '[not documented]'),
    });
    expect(bridged.find((r) => r.fieldId === field.fieldId)).toBeUndefined();
    // The non-vacuity half: the same run on the real kind DOES fill, so this is
    // a refusal of the checkbox specifically and not of everything.
    const ok = bridgeNumericTableCells({
      facts: [diameterFact('a', '3.10', 'right')],
      mappings: mappingsForAllFields(),
      ir,
      filledNote: noteWith('3.10', '[not documented]'),
    });
    expect(ok.find((r) => r.fieldId === field.fieldId)?.value).toBe('3.1');
  });

  it('THE CONTROL: canonical diameters were never broken and still are not', () => {
    // If this arm ever goes red the fix has broken the 18 cells that worked.
    const { bridged, blocking } = run('6.2', '5.8');
    const byId = new Map(bridged.map((r) => [r.fieldId, r]));
    expect(byId.get(cell(RIGHT_SFJ_ROW, DIAMETER_COL).fieldId)?.value).toBe('6.2');
    expect(byId.get(cell(LEFT_SFJ_ROW, DIAMETER_COL).fieldId)?.value).toBe('5.8');
    expect(blocking.filter((i) => i.code === 'ASSERTION_NOT_SUPPORTED')).toEqual([]);
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// 2 · THE GATE DID NOT WEAKEN. This is the arm that makes the fix a TIGHTENING
//     rather than a loosening, and it is the one ruling #135 explicitly ruled
//     out doing: "❌ NOT by making the validator compare numerically".
// ─────────────────────────────────────────────────────────────────────────────

describe('F5-d(b) — the validator is exactly as strict as it was', () => {
  /** The resolution bridge-fill.ts USED to build: the model's raw cell text. */
  function preFixResolution(field: TemplateField, fact: EncounterFact, cellText: string): FieldResolution {
    return {
      fieldId: field.fieldId,
      status: 'supported',
      value: cellText,
      sourceFactIds: [fact.factId],
      evidenceAnchorIds: [...fact.evidenceAnchorIds],
      selectedOptionOrdinal: null,
      reasonCode: 'table_cell_measurement',
      clinicianReviewed: false,
    } as FieldResolution;
  }

  function validateHandBuilt(cellText: string, dictated: string): string[] {
    const field = cell(RIGHT_SFJ_ROW, DIAMETER_COL);
    const fact = diameterFact('a', dictated, 'right');
    const mappings = mappingsForAllFields();
    const merged = mergeFieldResolutions(ir, blankBaseline(), [
      preFixResolution(field, fact, cellText),
    ]);
    return validateTemplateTwin({
      fields: ir.fields,
      mappings,
      facts: [fact],
      resolutions: merged,
      tables: ir.tables,
      allowUncertifiedForSyntheticTest: true,
      now: NOW,
    })
      .issues.filter((i) => i.severity === 'blocking' && i.fieldId === field.fieldId)
      .map((i) => i.code);
  }

  it('⚠️ RED PROOF OF TONIGHT\'S REFUSAL: the PRE-FIX shape is still refused', () => {
    // The old bridge wrote "3.10" while the fact said "3.1". Feed the validator
    // exactly that and it must still say ASSERTION_NOT_SUPPORTED. If this arm
    // ever goes green, somebody has "fixed" F5-d by relaxing the validator, and
    // that is the one route ruling #135 forbids.
    expect(validateHandBuilt('3.10', '3.10')).toContain('ASSERTION_NOT_SUPPORTED');
  });

  it('⚠️ and a value with NO numeric relationship to the fact is still refused', () => {
    // The stronger direction: the validator is not merely fussy about
    // formatting, it refuses an unevidenced number outright. A numeric
    // comparison would have let "3.1" through for a fact of 3.1 while still
    // catching this — so this arm alone would NOT have caught a loosening, and
    // the one above alone would not have caught a validator that accepts
    // anything. Both, or neither means much.
    expect(validateHandBuilt('9.9', '3.10')).toContain('ASSERTION_NOT_SUPPORTED');
  });

  it('the same hand-built shape with the FACT\'S value is accepted', () => {
    // The discrimination control for the two arms above: they must be refusing
    // the divergence, not refusing every hand-built resolution.
    expect(validateHandBuilt('3.1', '3.10')).not.toContain('ASSERTION_NOT_SUPPORTED');
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// 3 · THE FIX NEVER BLANKS A CELL THAT WOULD HAVE RENDERED.
//     The one real risk of a fail-closed derivation is losing content, so it is
//     measured rather than argued.
// ─────────────────────────────────────────────────────────────────────────────

describe('F5-d(b) — a refusal only ever replaces a BLOCKING failure', () => {
  const infos: string[] = [];
  afterEach(() => {
    infos.length = 0;
    vi.restoreAllMocks();
  });

  function bridgeReasons(fact: EncounterFact, dictated: string): string[] {
    vi.spyOn(console, 'info').mockImplementation((...args: unknown[]) => {
      infos.push(args.map(String).join(' '));
    });
    bridgeNumericTableCells({
      facts: [fact],
      mappings: mappingsForAllFields(),
      ir,
      filledNote: noteWith(dictated, '[not documented]'),
    });
    return infos
      .map((line) => /reason=(\S+)/.exec(line)?.[1])
      .filter((r): r is string => Boolean(r));
  }

  it('⚠️ a NUMERIC fact value blanks the cell — and that cell could never render', () => {
    // narrative_text derives `typeof fact.value === 'string' ? fact.value : null`,
    // so a numeric fact value has no derivable text and the cell goes blank with
    // reason=value_not_derivable_from_fact.
    const numericValued = { ...diameterFact('a', '3.1', 'right'), value: 3.1 } as EncounterFact;
    expect(bridgeReasons(numericValued, '3.1')).toContain('value_not_derivable_from_fact');

    // AND THE OTHER HALF, WHICH IS THE POINT: pre-fix, that same cell filled
    // with "3.1" and the validator then refused it as ASSERTION_NOT_SUPPORTED —
    // a BLOCKING issue, which kills prepared.render for the WHOLE visit. So the
    // blank is not lost content; it is a whole document recovered.
    const field = cell(RIGHT_SFJ_ROW, DIAMETER_COL);
    const merged = mergeFieldResolutions(ir, blankBaseline(), [
      {
        fieldId: field.fieldId,
        status: 'supported',
        value: '3.1',
        sourceFactIds: [numericValued.factId],
        evidenceAnchorIds: [...numericValued.evidenceAnchorIds],
        selectedOptionOrdinal: null,
        reasonCode: 'table_cell_measurement',
        clinicianReviewed: false,
      } as FieldResolution,
    ]);
    const codes = validateTemplateTwin({
      fields: ir.fields,
      mappings: mappingsForAllFields(),
      facts: [numericValued],
      resolutions: merged,
      tables: ir.tables,
      allowUncertifiedForSyntheticTest: true,
      now: NOW,
    })
      .issues.filter((i) => i.severity === 'blocking' && i.fieldId === field.fieldId)
      .map((i) => i.code);
    expect(codes).toContain('ASSERTION_NOT_SUPPORTED');
  });

  it('⚠️ THE CENSUS REASONS ARE DECIDED UPSTREAM OF THIS CHANGE', () => {
    // The INBOX census is 44 blank: 32 no_supporting_fact, 12
    // laterality_mismatch. Both are emitted by matchMeasurementFact, which this
    // change does not touch and which runs BEFORE the derivation is consulted —
    // so neither count can move. Asserted rather than reasoned: a fact that
    // supports nothing still reports no_supporting_fact, and never the new
    // reason.
    const unrelated = {
      ...diameterFact('c', '9.9', 'right'),
      evidenceQuote: 'Right calf tenderness on palpation',
    } as EncounterFact;
    const reasons = bridgeReasons(unrelated, '3.1');
    expect(reasons).toContain('no_supporting_fact');
    expect(reasons).not.toContain('value_not_derivable_from_fact');
  });

  it('⚠️ and a production-shaped fact produces NO new-reason blanks at all', () => {
    // The new reason must be unreachable on the production fact shape, or the
    // fix would be trading two refused cells for a fresh crop of blank ones.
    const reasons = bridgeReasons(diameterFact('a', '3.10', 'right'), '3.10');
    expect(reasons).not.toContain('value_not_derivable_from_fact');
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// 4 · THE DOCUMENT ACTUALLY RENDERS, carrying the derived value.
//     The validator is not the only consumer: renderer.ts:778-824 type-checks
//     by field kind, so a caller that stringified the derivation would satisfy
//     the validator and still fail the render.
// ─────────────────────────────────────────────────────────────────────────────

describe('F5-d(b) — the derived value reaches the rendered document', () => {
  it('renders, and the field proof records the derived value', async () => {
    const { merged } = run('3.10', '4.40');
    const validation: TemplateTwinValidationResult = {
      valid: true,
      issues: [],
      checkedAt: NOW,
      validatorVersion: 'template-field-validator/1.0.0',
    };
    const rendered = await renderTemplateDocx({
      source: wmIovBytes,
      ir,
      resolutions: merged,
      validation,
    });
    // The renderer refuses a string where a kind wants a number
    // (FIELD_VALUE_INVALID) and vice versa, by THROWING — so reaching a
    // round-trip verification at all already asserts that the derivation's
    // RETURN TYPE matched the field's kind.
    expect(rendered.verification.verified).toBe(true);
    expect(rendered.verification.fieldCheck).toBe('verified');

    // And the cell is FILLED, not proven-blank: the derived value reached the
    // document and survived the round-trip read-back.
    const right = rendered.verification.fields.find(
      (f) => f.fieldId === cell(RIGHT_SFJ_ROW, DIAMETER_COL).fieldId,
    );
    const left = rendered.verification.fields.find(
      (f) => f.fieldId === cell(LEFT_SFJ_ROW, DIAMETER_COL).fieldId,
    );
    expect(right?.kind).toBe('filled');
    expect(left?.kind).toBe('filled');
  });
});
