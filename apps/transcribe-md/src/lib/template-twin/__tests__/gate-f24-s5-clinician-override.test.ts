// ============================================================================
// F24-S5 GATE — the clinician's correction reaches the doctor's own form.
// ----------------------------------------------------------------------------
// Everything here is SHIPPED CODE on the REAL customer template:
// `compileTemplateDocx` on `WM IOV Template.docx`, the real
// `mergeFieldResolutions`, the real `applyClinicianOverrides`, the real
// `validateTemplateTwin`, the real `renderTemplateDocx`. Nothing is
// re-implemented, so this gate cannot agree with a mirror of the bug.
//
// ⚠️ THE ARM THAT MATTERS IS `wins over a SUPPORTED baseline`. Measured on the
// two production fills, 13 of the 28 content controls resolve `supported` and
// ELEVEN of those 13 are `criticality: laterality`. `supported` is not a member
// of `UNFILLED`, so a correction routed through the existing overlay is
// REFUSED for exactly the safety-critical class — silently. A developer testing
// a routine dropdown (40 of 42 unfilled) sees it work perfectly. That is the
// defect this slice exists to prevent, and it is what this arm pins.
//
// ⚠️ AND THE VALIDATOR ARM IS THE ONE THE AUTHOR COULD NOT PREDICT. A populated
// resolution must carry `sourceFactIds` + `evidenceAnchorIds`
// (`FieldResolutionSchema.superRefine`), so an override MUST mint a citable
// fact. Whether the shipped validator then ACCEPTS a `clinician_correction`
// fact was read, never executed. This runs it.
// ============================================================================

import { readFileSync } from 'node:fs';
import path from 'node:path';

import JSZip from 'jszip';
import { beforeAll, describe, expect, it } from 'vitest';

import { compileTemplateDocx, renderTemplateDocx } from '@/lib/note-template-docx';

import { mergeFieldResolutions } from '../bridge-fill';
import { applyClinicianOverrides } from '../clinician-override';
import { listEditableFormControls } from '../editable-controls';
import { expectedDataTypeForFieldKind } from '../semantic-mapping';
import { validateTemplateTwin } from '../validation';
import {
  FieldResolutionSchema,
  type EncounterFact,
  type FieldResolution,
  type SemanticMapping,
  type TemplateDocIR,
  type TemplateField,
} from '../ir';

const WM_IOV_PATH = path.resolve(process.cwd(), '../../WM IOV Template.docx');
const wmIovBytes = new Uint8Array(readFileSync(WM_IOV_PATH));
const NOW = '2026-08-24T03:00:00.000Z';

let ir: TemplateDocIR;
beforeAll(() => {
  ir = compileTemplateDocx(wmIovBytes);
});

/** The content control this arc's acceptance names: SIDE OF EXAM — uniquely
 *  labelled, `criticality: laterality`, and `supported` on production. */
function sideOfExam(): TemplateField {
  const f = ir.fields.find(
    (x) =>
      x.rendererBinding.bindingType === 'content_control' &&
      x.originalLabel.startsWith('SIDE OF EXAM'),
  );
  if (!f) throw new Error('SIDE OF EXAM content control not found in the compiled IR');
  return f;
}

function mappingsForAllFields(): SemanticMapping[] {
  return ir.fields.map(
    (f) =>
      ({
        fieldId: f.fieldId,
        sourceType: 'extraction',
        clinicalConcept: 'exam.side',
        expectedDataType: expectedDataTypeForFieldKind(f.kind) ?? 'text',
        polarityBehavior: 'value_only',
        temporality: 'current',
        laterality: 'optional',
        unitPolicy: 'not_applicable',
        approvedSynonyms: [],
        required: false,
        blankPolicy: 'blank',
        unknownPolicy: 'blank',
        practiceDefault: null,
        status: 'certified',
      }) as SemanticMapping,
  );
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

/** A resolver-SUPPORTED baseline for one field — the class the existing overlay
 *  refuses to touch, reproduced exactly. */
function baselineWithSupported(
  field: TemplateField,
  value: string,
  ordinal: number,
): { resolutions: FieldResolution[]; fact: EncounterFact } {
  const fact = {
    factId: `ttfact_${'ab'.repeat(12)}`,
    sourceType: 'encounter_evidence',
    concept: 'exam.side',
    value,
    polarity: 'affirmed',
    temporality: 'current',
    experiencer: 'patient',
    laterality: 'unknown',
    number: null,
    unit: null,
    speaker: 'Doctor',
    sourceTranscriptOffsets: { start: 0, end: 10 },
    audioTimestampSeconds: null,
    evidenceAnchorIds: ['anchor-baseline'],
    evidenceQuote: `Side of exam ${value}`,
    segment: null,
    quality: { asr: 'high', evidence: 'direct' },
  } as EncounterFact;
  const resolutions = blankBaseline().map((r) =>
    r.fieldId === field.fieldId
      ? FieldResolutionSchema.parse({
          fieldId: field.fieldId,
          status: 'supported',
          value,
          sourceFactIds: [fact.factId],
          evidenceAnchorIds: ['anchor-baseline'],
          selectedOptionOrdinal: ordinal,
          reasonCode: 'resolver_supported',
          clinicianReviewed: false,
        })
      : r,
  );
  return { resolutions, fact };
}

/** Occurrences of `needle` in `hay`. Counted rather than tested for presence:
 *  a dropdown's own definition lists EVERY option inside document.xml, so
 *  `toContain` is true for all of them whatever is selected. The COUNT is what
 *  discriminates a selection from a mere listing. */
function countOf(hay: string, needle: string): number {
  if (!needle) return 0;
  return hay.split(needle).length - 1;
}

/** Two options of SIDE OF EXAM that are genuinely different, so "it changed"
 *  cannot be satisfied by writing the value it already had. */
function twoDistinctOptions(field: TemplateField) {
  const real = field.allowedOptions.filter(
    (o) => !/^choose an item\.?$/i.test(o.displayText.trim()),
  );
  expect(real.length).toBeGreaterThanOrEqual(2);
  return { from: real[0], to: real[1] };
}

describe('F24-S5 — the clinician override', () => {
  it('NON-VACUITY: the real template compiles to the content controls this gate is about', () => {
    const controls = ir.fields.filter(
      (f) => f.rendererBinding.bindingType === 'content_control',
    );
    // The figure the whole slice is scoped by. If this moves, every count in
    // the ledger is stale and this gate must be re-read, not re-baselined.
    expect(controls.length).toBe(28);
    const withOptions = controls.filter((f) => f.allowedOptions.length > 0);
    expect(withOptions.length).toBe(28);
    const soe = sideOfExam();
    expect(soe.criticality).toBe('laterality');
    expect(soe.allowedOptions.length).toBeGreaterThan(1);
  });

  it('ADDRESSING: labels cannot identify a control, which is why the ordinal exists', () => {
    const controls = ir.fields.filter(
      (f) => f.rendererBinding.bindingType === 'content_control',
    );
    const distinctLabels = new Set(controls.map((f) => f.originalLabel));
    // 28 controls, 14 distinct labels — measured on production 2026-08-24 and
    // re-derived here from the template itself. A label-keyed design would be
    // ambiguous for 18 of the 28.
    expect(distinctLabels.size).toBe(14);
    expect(distinctLabels.size).toBeLessThan(controls.length);
  });

  it('ADDRESSING: the editable list is 1-based, dense and in document order', () => {
    const list = listEditableFormControls(ir);
    expect(list.length).toBe(28);
    expect(list.map((c) => c.ordinal)).toEqual(
      Array.from({ length: list.length }, (_, i) => i + 1),
    );
    // Document order, and every entry carries a real fieldId the model never sees.
    const orders = list.map(
      (c) => ir.fields.find((f) => f.fieldId === c.fieldId)!.displayOrder,
    );
    expect(orders).toEqual([...orders].sort((a, b) => a - b));
  });

  it('⚠️ WINS over a SUPPORTED baseline — the case the existing overlay refuses', () => {
    const field = sideOfExam();
    const { from, to } = twoDistinctOptions(field);
    const { resolutions } = baselineWithSupported(field, from.value, from.ordinal);

    // CONTROL: the EXISTING overlay refuses this exact change. If this stops
    // being true, `mergeFieldResolutions` has been widened and the clinical
    // safety property this slice promised not to touch is gone.
    const viaOldOverlay = mergeFieldResolutions(ir, resolutions, [
      FieldResolutionSchema.parse({
        fieldId: field.fieldId,
        status: 'supported',
        value: to.value,
        sourceFactIds: [`ttfact_${'cd'.repeat(12)}`],
        evidenceAnchorIds: ['anchor-other'],
        selectedOptionOrdinal: to.ordinal,
        reasonCode: 'some_other_overlay',
        clinicianReviewed: false,
      }),
    ]);
    expect(viaOldOverlay.find((r) => r.fieldId === field.fieldId)!.value).toBe(from.value);

    // THE CLINICIAN WINS.
    const out = applyClinicianOverrides({
      ir,
      resolutions,
      overrides: [{ fieldId: field.fieldId, selectedOptionOrdinal: to.ordinal }],
      mappings: mappingsForAllFields(),
      noteSha256: 'a'.repeat(64),
    });
    const got = out.resolutions.find((r) => r.fieldId === field.fieldId)!;
    expect(got.value).toBe(to.value);
    expect(got.selectedOptionOrdinal).toBe(to.ordinal);
    expect(got.status).toBe('supported');
    // The dormant seam's first writer.
    expect(got.clinicianReviewed).toBe(true);
    expect(out.declined).toEqual([]);
    expect(out.facts).toHaveLength(1);
    expect(out.facts[0].sourceType).toBe('clinician_correction');
    // Provenance is REQUIRED by FieldResolutionSchema and must be the minted fact.
    expect(got.sourceFactIds).toEqual([out.facts[0].factId]);
    expect(got.evidenceAnchorIds).toEqual(out.facts[0].evidenceAnchorIds);
  });

  it('CARDINALITY: exactly one resolution per ir.field, in ir.fields order', () => {
    const field = sideOfExam();
    const { to } = twoDistinctOptions(field);
    const out = applyClinicianOverrides({
      ir,
      resolutions: blankBaseline(),
      overrides: [{ fieldId: field.fieldId, selectedOptionOrdinal: to.ordinal }],
      mappings: mappingsForAllFields(),
      noteSha256: 'a'.repeat(64),
    });
    expect(out.resolutions).toHaveLength(ir.fields.length);
    expect(out.resolutions.map((r) => r.fieldId)).toEqual(ir.fields.map((f) => f.fieldId));
  });

  describe('FAIL CLOSED — and a refusal never blanks what was there', () => {
    it('an ordinal that is not in the CURRENT option set is declined, not matched by text', () => {
      const field = sideOfExam();
      const { from } = twoDistinctOptions(field);
      const { resolutions } = baselineWithSupported(field, from.value, from.ordinal);
      const bogus = Math.max(...field.allowedOptions.map((o) => o.ordinal)) + 99;
      const out = applyClinicianOverrides({
        ir,
        resolutions,
        overrides: [{ fieldId: field.fieldId, selectedOptionOrdinal: bogus }],
        mappings: mappingsForAllFields(),
        noteSha256: 'a'.repeat(64),
      });
      expect(out.declined).toEqual([
        { fieldId: field.fieldId, reason: 'ordinal_not_in_options' },
      ]);
      // ⚠️ THE PRIOR VALUE SURVIVES. A correction that cannot be applied must
      // not leave a hole where a legitimately resolved value was.
      const got = out.resolutions.find((r) => r.fieldId === field.fieldId)!;
      expect(got.value).toBe(from.value);
      expect(got.clinicianReviewed).toBe(false);
      expect(out.facts).toEqual([]);
    });

    it('a fieldId that is not in this template is declined', () => {
      const out = applyClinicianOverrides({
        ir,
        resolutions: blankBaseline(),
        overrides: [{ fieldId: `ttf_${'0'.repeat(24)}`, selectedOptionOrdinal: 1 }],
        mappings: mappingsForAllFields(),
        noteSha256: 'a'.repeat(64),
      });
      expect(out.declined).toEqual([
        { fieldId: `ttf_${'0'.repeat(24)}`, reason: 'field_not_in_template' },
      ]);
      expect(out.facts).toEqual([]);
    });

    it('a field with no approved concept is declined — the citation would have nothing to satisfy', () => {
      const field = sideOfExam();
      const { to } = twoDistinctOptions(field);
      const mappings = mappingsForAllFields().map((m) =>
        m.fieldId === field.fieldId ? { ...m, clinicalConcept: null } : m,
      );
      const out = applyClinicianOverrides({
        ir,
        resolutions: blankBaseline(),
        overrides: [{ fieldId: field.fieldId, selectedOptionOrdinal: to.ordinal }],
        mappings: mappings as SemanticMapping[],
        noteSha256: 'a'.repeat(64),
      });
      expect(out.declined).toEqual([{ fieldId: field.fieldId, reason: 'no_approved_concept' }]);
      expect(out.facts).toEqual([]);
    });

    it('a duplicate fieldId does not make the result order-dependent', () => {
      const field = sideOfExam();
      const { from, to } = twoDistinctOptions(field);
      const out = applyClinicianOverrides({
        ir,
        resolutions: blankBaseline(),
        overrides: [
          { fieldId: field.fieldId, selectedOptionOrdinal: from.ordinal },
          { fieldId: field.fieldId, selectedOptionOrdinal: to.ordinal },
        ],
        mappings: mappingsForAllFields(),
        noteSha256: 'a'.repeat(64),
      });
      // FIRST wins, and exactly one fact is minted — not two, and not a silent
      // last-write-wins that depends on the database's row order.
      expect(out.resolutions.find((r) => r.fieldId === field.fieldId)!.value).toBe(from.value);
      expect(out.facts).toHaveLength(1);
    });
  });

  // ==========================================================================
  // ⚠️ THE WIRING ARMS — F24-S4's DEFECT, PRE-REGISTERED.
  //
  // S4 shipped a field the only actor that could send it was never told about:
  // every layer it could see was wired correctly, an arm read the caller file
  // and passed, and `CHAT_EDIT_SYSTEM` mentioned the field ZERO times. The
  // capability was unreachable and every proof ran BELOW the broken layer —
  // exactly as every arm above this comment does, by calling the module with
  // an override already in hand.
  //
  // These arms watch the two layers a fixture supplies for free.
  // ==========================================================================
  describe('WIRING — the capability has an actual caller, at every layer', () => {
    const read = (p: string) => readFileSync(path.resolve(process.cwd(), p), 'utf8');

    it('the FILL ENGINE reads the overrides and applies them', () => {
      const src = read('src/lib/template-twin/fill-engine.ts');
      // POSITIVE CONTROL: a token known to be in this file. A matcher that
      // cannot find this cannot be believed about the ones below.
      expect(src).toContain('bridgeTemplateFill');

      expect(src).toContain('templateTwinFieldOverride.findMany');
      expect(src).toContain('applyClinicianOverrides');
      expect(src).toContain('clinicianOverrides');

      // ⚠️ APPLIED OUTSIDE THE generatedNote TERNARY. If the override call sat
      // inside that conditional the feature would silently depend on this run
      // having a generated note — true for the worker, false for other paths,
      // and invisible either way.
      const applyAt = src.indexOf('applyClinicianOverrides({');
      const ternaryAt = src.indexOf('input.markerText != null && input.generatedNote != null');
      expect(applyAt).toBeGreaterThan(-1);
      expect(ternaryAt).toBeGreaterThan(-1);
      expect(applyAt).toBeGreaterThan(ternaryAt);
    });

    it('the PREVIEW passes visitId, so it reads the same overrides the export will', () => {
      const src = read('src/actions/preview-visit-document.ts');
      expect(src).toContain('readAndPrepareTemplateTwinFill');
      expect(src).toMatch(/readAndPrepareTemplateTwinFill\(\{[\s\S]{0,400}?\bvisitId,/);
    });

    it('the CHAT ACTION offers the controls and dispatches the intent', () => {
      const src = read('src/actions/chat-edit-visit.ts');
      expect(src).toContain('edit_table_cell'); // positive control
      expect(src).toContain('listVisitFormControls');
      expect(src).toContain('formControlsForModel');
      expect(src).toContain("case 'edit_form_control'");
      expect(src).toContain('setTemplateControlAction');
    });

    it('⚠️ THE MODEL IS TOLD — the system prompt names the capability', async () => {
      const { CHAT_EDIT_SYSTEM } = await import('@/lib/chat-edit/prompt');
      // POSITIVE CONTROL against the sibling S4 shipped correctly.
      expect(CHAT_EDIT_SYSTEM).toContain('rowOrdinal');
      // The capability itself, and the ECHO rule that makes it safe.
      expect(CHAT_EDIT_SYSTEM).toContain('edit_form_control');
      expect(CHAT_EDIT_SYSTEM).toContain('controlOrdinal');
      expect(CHAT_EDIT_SYSTEM).toContain('FORM CONTROLS');
    });

    it('⚠️ THE SAFETY RULE IS ON THE WIRE, not only in a TS comment', async () => {
      // S4's rule lived in a JSDoc comment on a zod field. `z.toJSONSchema()`
      // emits `description` ONLY from `.describe()`/`.meta()`, so the model
      // received an undocumented integer and the one rule that made it safe
      // was visible to every human reader and to nobody else.
      const { z } = await import('zod');
      const { EditFormControlIntentSchema } = await import('@/lib/chat-edit/intent');
      const json = JSON.stringify(z.toJSONSchema(EditFormControlIntentSchema));
      expect(json).toContain('controlOrdinal');
      // The echo rule must survive the schema conversion.
      expect(json.toLowerCase()).toContain('never one you counted yourself');
    });
  });

  it('⚠️ THE VALIDATOR ACCEPTS a clinician_correction citation', () => {
    const field = sideOfExam();
    const { from, to } = twoDistinctOptions(field);
    const { resolutions, fact } = baselineWithSupported(field, from.value, from.ordinal);
    const mappings = mappingsForAllFields();
    const out = applyClinicianOverrides({
      ir,
      resolutions,
      overrides: [{ fieldId: field.fieldId, selectedOptionOrdinal: to.ordinal }],
      mappings,
      noteSha256: 'a'.repeat(64),
    });
    const result = validateTemplateTwin({
      fields: ir.fields,
      mappings,
      // The minted fact TRAVELS WITH the resolutions. A citation to a fact the
      // fact set does not carry is untraceable, and the validator says so.
      facts: [fact, ...out.facts],
      resolutions: out.resolutions,
      tables: ir.tables,
      allowUncertifiedForSyntheticTest: true,
      now: NOW,
    });
    const mine = result.issues.filter(
      (i) => i.fieldId === field.fieldId && i.severity === 'blocking',
    );
    expect(mine).toEqual([]);
  });

  it('⚠️ REACHES THE BYTES — the chosen option is in the rendered document', async () => {
    const field = sideOfExam();
    const { from, to } = twoDistinctOptions(field);
    const { resolutions, fact } = baselineWithSupported(field, from.value, from.ordinal);
    const mappings = mappingsForAllFields();
    const out = applyClinicianOverrides({
      ir,
      resolutions,
      overrides: [{ fieldId: field.fieldId, selectedOptionOrdinal: to.ordinal }],
      mappings,
      noteSha256: 'a'.repeat(64),
    });
    const validation = validateTemplateTwin({
      fields: ir.fields,
      mappings,
      facts: [fact, ...out.facts],
      resolutions: out.resolutions,
      tables: ir.tables,
      allowUncertifiedForSyntheticTest: true,
      now: NOW,
    });
    const render = await renderTemplateDocx({
      source: wmIovBytes,
      ir,
      resolutions: out.resolutions,
      validation,
    });
    expect(render.verification.verified).toBe(true);

    // ⚠️ READ THE ACTUAL BYTES A DOCTOR OPENS, not a success flag beside them.
    // A render that reported itself verified and wrote nothing would satisfy
    // every other assertion in this file.
    const zip = await JSZip.loadAsync(render.document);
    const xml = await zip.file('word/document.xml')!.async('string');

    // NEGATIVE CONTROL FIRST — the value the resolver had is GONE. Without
    // this, a document that simply contains every option's text (they are all
    // in the dropdown's own definition) would pass the positive assertion
    // while the selection never changed.
    const before = await JSZip.loadAsync(
      (
        await renderTemplateDocx({
          source: wmIovBytes,
          ir,
          resolutions,
          validation: validateTemplateTwin({
            fields: ir.fields,
            mappings,
            facts: [fact],
            resolutions,
            tables: ir.tables,
            allowUncertifiedForSyntheticTest: true,
            now: NOW,
          }),
        })
      ).document,
    );
    const xmlBefore = await before.file('word/document.xml')!.async('string');

    // The two documents must actually DIFFER, and differ in the direction of
    // the correction.
    expect(xml).not.toBe(xmlBefore);
    expect(countOf(xml, to.displayText)).toBeGreaterThan(countOf(xmlBefore, to.displayText));
    expect(countOf(xml, from.displayText)).toBeLessThan(countOf(xmlBefore, from.displayText));
  });
});
