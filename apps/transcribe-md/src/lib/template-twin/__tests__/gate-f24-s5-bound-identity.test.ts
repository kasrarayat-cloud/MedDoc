// ============================================================================
// F24-S5 — THE BOUND IDENTITY, AND THE CLINICIAN'S CORRECTION THAT MOVES IT.
// ----------------------------------------------------------------------------
// ⚠️ THIS GATE EXISTS BECAUSE THE PREVIOUS ONE WAS DECORATIVE. The adversarial
// pass on PR #824 mutated shipped source five ways and left that gate 16/16
// GREEN, three of them `tsc`-clean:
//
//   | mutation                                          | old gate | consequence
//   | delete `clinicianOverrides` from the fill call    | 16/16    | feature 100% dead
//   | make the overlay conditional on `generatedNote`   | 16/16    | the defect its own WIRING arm NAMES
//   | drop `visitId` from the override `where`          | 16/16    | cross-PATIENT contamination
//   | move the `.describe()` echo rule onto `value`     | 16/16    | F24-S4's defect, inside the arm for it
//   | delete the `upsert` entirely                      | 16/16    | chat says "set", nothing is written
//
// Every one of those survived because the arms were SUBSTRING SCANS, and
// `toContain('clinicianOverrides')` is satisfied by the variable DECLARATION —
// which is exactly why deleting its USE was invisible.
//
// So this gate CALLS THINGS AND ASSERTS BEHAVIOUR. Where a source scan is
// genuinely the only instrument (a prompt's text, a schema's wire form), it
// reads the SHIPPED ARTIFACT — `z.toJSONSchema()` output, not the file.
//
// ⚠️ AND IT RUNS AGAINST THE REAL CUSTOMER FORM, compiled by the shipped
// compiler — the same 28 content controls the one certified twin in production
// carries. A synthetic option set would not have the label collisions, the
// placeholder, or the paired option sets that make this slice hard.
// ============================================================================

import { readFileSync } from 'node:fs';
import path from 'node:path';

import { beforeAll, describe, expect, it, vi } from 'vitest';
import * as z from 'zod';

import { compileTemplateDocx } from '@/lib/note-template-docx';
import { isWordPlaceholderOption } from '@/lib/note-template-docx/placeholder-option';

// `editable-controls` imports the prisma singleton for its DB helper; the pure
// list function under test never touches it.
vi.mock('@meddoc/db', () => ({ default: {} }));
// ⚠️ `fill-engine` -> `twin-audit` -> `@/lib/audit` -> `@/lib/nextauth`, so
// importing the real `prepareTemplateTwinFill` drags a web framework into a
// unit test of a pure clinical boundary. The audit write is fire-and-forget and
// no arm here asserts it; stubbing the edge is cheaper and more honest than
// stubbing the function under test, which is what the old gate did.
vi.mock('@/lib/audit', () => ({ logAudit: vi.fn() }));

import { applyClinicianOverrides } from '../clinician-override';
import {
  formControlsForModel,
  listEditableFormControls,
} from '../editable-controls';
import { prepareTemplateTwinFill } from '../fill-engine';
import {
  EMPTY_OVERRIDES_SHA256,
  manifestMatchesDocument,
  noteIdentity,
  overridesIdentity,
} from '../note-identity';
import { expectedDataTypeForFieldKind } from '../semantic-mapping';
import {
  FieldResolutionSchema,
  type FieldResolution,
  type SemanticMapping,
  type TemplateDocIR,
  type TemplateField,
} from '../ir';
import { ChatReplySchema } from '@/lib/chat-edit/intent';
import { CHAT_EDIT_SYSTEM } from '@/lib/chat-edit/prompt';

const WM_IOV_PATH = path.resolve(process.cwd(), '../../WM IOV Template.docx');
const wmIovBytes = new Uint8Array(readFileSync(WM_IOV_PATH));

let ir: TemplateDocIR;
let selects: TemplateField[];
beforeAll(() => {
  ir = compileTemplateDocx(wmIovBytes);
  selects = ir.fields.filter(
    (f) => f.rendererBinding.bindingType === 'content_control' && f.allowedOptions.length > 0,
  );
});

const NOTE = 'IMPRESSION: right GSV incompetent.';

// ───────────────────────────────────────────────────────────────────────────
// 0 · NON-VACUITY. Everything below is a claim about THIS form; if it stopped
//     compiling to the shape the claims assume, every arm would pass over an
//     empty set and say nothing.
// ───────────────────────────────────────────────────────────────────────────
describe('0 · the fixture is the form these claims are about', () => {
  it('compiles to 80 fields, 28 of them enumerated content controls', () => {
    expect(ir.fields.length).toBe(80);
    expect(selects.length).toBe(28);
  });

  it('⚠️ and every one of the 28 has had Word’s placeholder REMOVED', () => {
    // Measured on production before this change: 28 of 28 carried
    // "Choose an item." at ordinal 0, and nowhere else.
    for (const f of selects) {
      expect(
        f.allowedOptions.some((o) => isWordPlaceholderOption(o.displayText)),
        `${f.fieldId} still offers Word's placeholder as a clinical option`,
      ).toBe(false);
    }
  });

  it('⚠️ ORDINALS ARE NOT RENUMBERED — the sets start at 1 and stay sparse', () => {
    // THE POINT OF THE WHOLE DESIGN. `selectedOptionOrdinal` is persisted on
    // manifests and on override rows, and an override row outlives a recompile
    // (it is keyed by (visitId, fieldId), with no compiled-version reference).
    // Renumbering would silently re-point every stored ordinal at its
    // NEIGHBOUR — which resolves successfully, so the fail-closed
    // `ordinal_not_in_options` decline would never fire.
    //
    // It also matters to the renderer: a legacy `w:ddList` write puts the
    // ordinal in `w:result val`, which Word resolves against the DOCUMENT's own
    // untouched list.
    let sawSparse = 0;
    for (const f of selects) {
      const ords = f.allowedOptions.map((o) => o.ordinal);
      expect(ords).toEqual([...ords].sort((a, b) => a - b));
      // The placeholder was at 0 on every one of these, so the survivors start
      // at 1. If this were renumbering, they would start at 0.
      expect(Math.min(...ords)).toBe(1);
      if (ords[0] !== 0) sawSparse += 1;
    }
    expect(sawSparse).toBe(28);
  });

  it('⚠️ and no control was emptied by the exclusion', () => {
    for (const f of selects) expect(f.allowedOptions.length).toBeGreaterThan(0);
  });
});

// ───────────────────────────────────────────────────────────────────────────
// 1 · THE BOUND IDENTITY — the root fix. Behavioural, on the real functions.
// ───────────────────────────────────────────────────────────────────────────
describe('1 · the bound identity is (note, overrides)', () => {
  const OV = [{ fieldId: 'ttf_a', selectedOptionOrdinal: 2 }];

  it('is CANONICAL — row order cannot move it', () => {
    const a = [
      { fieldId: 'ttf_b', selectedOptionOrdinal: 1 },
      { fieldId: 'ttf_a', selectedOptionOrdinal: 2 },
    ];
    expect(overridesIdentity(a)).toBe(overridesIdentity([...a].reverse()));
  });

  it('DISCRIMINATES — a different ordinal is a different identity', () => {
    expect(overridesIdentity(OV)).not.toBe(
      overridesIdentity([{ fieldId: 'ttf_a', selectedOptionOrdinal: 3 }]),
    );
    // …and the empty set is not the same as any correction. If these collided,
    // every arm below would pass vacuously.
    expect(overridesIdentity(OV)).not.toBe(EMPTY_OVERRIDES_SHA256);
    expect(overridesIdentity([])).toBe(EMPTY_OVERRIDES_SHA256);
  });

  it('⚠️ THE ROOT ARM — a NEW override makes a note-matching manifest STALE', () => {
    // This is the whole slice. Before the widening, this case answered `match`:
    // the export served the pre-override bytes and the sign freeze pinned the
    // pre-override manifest forever, because an override never touches
    // `soapFinal`.
    const r = manifestMatchesDocument({
      manifestNoteSha256: noteIdentity(NOTE),
      manifestOverridesSha256: EMPTY_OVERRIDES_SHA256,
      soapFinal: NOTE,
      currentOverrides: OV,
    });
    expect(r.ok).toBe(false);
    expect(r.reason).toBe('overrides_changed');
  });

  it('a manifest filled WITH the override is fresh for that override', () => {
    const r = manifestMatchesDocument({
      manifestNoteSha256: noteIdentity(NOTE),
      manifestOverridesSha256: overridesIdentity(OV),
      soapFinal: NOTE,
      currentOverrides: OV,
    });
    expect(r).toEqual({ ok: true, reason: 'match' });
  });

  it('a REMOVED override is stale too — the identity is the SET, not a counter', () => {
    const r = manifestMatchesDocument({
      manifestNoteSha256: noteIdentity(NOTE),
      manifestOverridesSha256: overridesIdentity(OV),
      soapFinal: NOTE,
      currentOverrides: [],
    });
    expect(r.reason).toBe('overrides_changed');
  });

  it('⚠️ a LEGACY manifest (null sibling) is vacuously fresh — never backfilled', () => {
    // Null can only mean "written before the override table existed", and no
    // override row can predate its own table. Failing closed here would strip
    // native export from every manifest written before this migration —
    // measured: 2 in production, both on signed visits.
    const r = manifestMatchesDocument({
      manifestNoteSha256: noteIdentity(NOTE),
      manifestOverridesSha256: null,
      soapFinal: NOTE,
      currentOverrides: [],
    });
    expect(r).toEqual({ ok: true, reason: 'match' });
  });

  it('⚠️ but a legacy manifest is NOT a free pass once a correction EXISTS', () => {
    // The dangerous reading of "null is vacuously fresh" would be "null skips
    // the check". It does not: null means the EMPTY set, and the empty set
    // disagrees with a real correction.
    const r = manifestMatchesDocument({
      manifestNoteSha256: noteIdentity(NOTE),
      manifestOverridesSha256: null,
      soapFinal: NOTE,
      currentOverrides: OV,
    });
    expect(r.reason).toBe('overrides_changed');
  });

  it('the NOTE is still checked first, and its unprovable cases still decline', () => {
    expect(
      manifestMatchesDocument({
        manifestNoteSha256: noteIdentity(NOTE),
        manifestOverridesSha256: EMPTY_OVERRIDES_SHA256,
        soapFinal: 'a different note',
        currentOverrides: [],
      }).reason,
    ).toBe('note_changed');
    expect(
      manifestMatchesDocument({
        manifestNoteSha256: null,
        manifestOverridesSha256: EMPTY_OVERRIDES_SHA256,
        soapFinal: NOTE,
        currentOverrides: [],
      }).reason,
    ).toBe('manifest_note_unknown');
    expect(
      manifestMatchesDocument({
        manifestNoteSha256: noteIdentity(NOTE),
        manifestOverridesSha256: EMPTY_OVERRIDES_SHA256,
        soapFinal: null,
        currentOverrides: [],
      }).reason,
    ).toBe('visit_note_absent');
  });
});

// ───────────────────────────────────────────────────────────────────────────
// 2 · THE OVERLAY — behavioural, on the real form.
// ───────────────────────────────────────────────────────────────────────────
function mappingsFor(fields: readonly TemplateField[]): SemanticMapping[] {
  return fields.map(
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

function resolutionsWith(
  fields: readonly TemplateField[],
  supported: { fieldId: string; value: string; ordinal: number } | null,
): FieldResolution[] {
  return fields.map((f) =>
    supported && f.fieldId === supported.fieldId
      ? FieldResolutionSchema.parse({
          fieldId: f.fieldId,
          status: 'supported',
          value: supported.value,
          sourceFactIds: ['ttfact_' + 'a'.repeat(24)],
          evidenceAnchorIds: ['anchor'],
          selectedOptionOrdinal: supported.ordinal,
          reasonCode: 'synthetic_direct_evidence',
          clinicianReviewed: false,
        })
      : FieldResolutionSchema.parse({
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

describe('2 · the clinician beats the resolver', () => {
  it('⚠️ THE ACCEPTANCE CASE — a `supported` value IS overridden', () => {
    // 13 of the 28 resolve `supported` on the two real production fills, and 11
    // of those 13 are `criticality: laterality`. `supported` is NOT in
    // `UNFILLED`, so routing the correction through `mergeFieldResolutions`
    // would have refused exactly those — the developer testing a routine
    // dropdown sees it work, the doctor correcting SIDE OF EXAM is ignored.
    const field = selects[0];
    // Two options that are not substrings of one another, so "it changed" is
    // not satisfiable by a prefix match.
    const a = field.allowedOptions[0];
    const b = field.allowedOptions.find(
      (o) =>
        o.value !== a.value &&
        !o.value.includes(a.value) &&
        !a.value.includes(o.value),
    );
    expect(b, 'fixture needs two substring-independent options').toBeTruthy();

    const out = applyClinicianOverrides({
      ir,
      resolutions: resolutionsWith(ir.fields, {
        fieldId: field.fieldId,
        value: a.value,
        ordinal: a.ordinal,
      }),
      overrides: [{ fieldId: field.fieldId, selectedOptionOrdinal: b!.ordinal }],
      mappings: mappingsFor(ir.fields),
      noteSha256: noteIdentity(NOTE)!,
    });
    const got = out.resolutions.find((r) => r.fieldId === field.fieldId)!;
    expect(got.value).toBe(b!.value);
    expect(got.selectedOptionOrdinal).toBe(b!.ordinal);
    expect(got.reasonCode).toBe('clinician_override');
    expect(got.clinicianReviewed).toBe(true);
    expect(out.declined).toEqual([]);
    expect(out.facts).toHaveLength(1);
  });

  it('⚠️ an unknown ordinal DECLINES and leaves the prior value untouched', () => {
    const field = selects[0];
    const a = field.allowedOptions[0];
    const out = applyClinicianOverrides({
      ir,
      resolutions: resolutionsWith(ir.fields, {
        fieldId: field.fieldId,
        value: a.value,
        ordinal: a.ordinal,
      }),
      overrides: [{ fieldId: field.fieldId, selectedOptionOrdinal: 9999 }],
      mappings: mappingsFor(ir.fields),
      noteSha256: noteIdentity(NOTE)!,
    });
    expect(out.declined).toEqual([
      { fieldId: field.fieldId, reason: 'ordinal_not_in_options' },
    ]);
    // NOT blanked. A half-applied correction must never leave a hole where a
    // legitimately derived value was.
    expect(out.resolutions.find((r) => r.fieldId === field.fieldId)!.value).toBe(a.value);
  });

  it('⚠️ ordinal 0 — the placeholder’s old slot — resolves to NOTHING now', () => {
    // Before this change ordinal 0 was "Choose an item." on all 28 controls, and
    // the pass drove it end to end into a rendered imaging report with
    // `clinicianReviewed: true` and no validator issue. It must now be
    // unreachable rather than merely discouraged.
    const field = selects[0];
    const out = applyClinicianOverrides({
      ir,
      resolutions: resolutionsWith(ir.fields, null),
      overrides: [{ fieldId: field.fieldId, selectedOptionOrdinal: 0 }],
      mappings: mappingsFor(ir.fields),
      noteSha256: noteIdentity(NOTE)!,
    });
    expect(out.declined).toEqual([
      { fieldId: field.fieldId, reason: 'ordinal_not_in_options' },
    ]);
    expect(out.resolutions.find((r) => r.fieldId === field.fieldId)!.value).toBeNull();
  });

  it('a field not in the template declines rather than throwing', () => {
    const out = applyClinicianOverrides({
      ir,
      resolutions: resolutionsWith(ir.fields, null),
      overrides: [{ fieldId: 'ttf_' + 'f'.repeat(24), selectedOptionOrdinal: 1 }],
      mappings: mappingsFor(ir.fields),
      noteSha256: noteIdentity(NOTE)!,
    });
    expect(out.declined[0].reason).toBe('field_not_in_template');
  });

  it('⚠️ CARDINALITY — exactly one resolution per ir.field, in ir.fields order', () => {
    const out = applyClinicianOverrides({
      ir,
      resolutions: resolutionsWith(ir.fields, null),
      overrides: [{ fieldId: selects[0].fieldId, selectedOptionOrdinal: selects[0].allowedOptions[0].ordinal }],
      mappings: mappingsFor(ir.fields),
      noteSha256: noteIdentity(NOTE)!,
    });
    expect(out.resolutions).toHaveLength(ir.fields.length);
    expect(out.resolutions.map((r) => r.fieldId)).toEqual(ir.fields.map((f) => f.fieldId));
  });

  it('⚠️ ALL 28 controls apply cleanly — not just the first one', () => {
    // `describe.each` over the whole set rather than one representative: the
    // pass noted that proving one control proves one control.
    for (const field of selects) {
      const opt = field.allowedOptions[field.allowedOptions.length - 1];
      const out = applyClinicianOverrides({
        ir,
        resolutions: resolutionsWith(ir.fields, null),
        overrides: [{ fieldId: field.fieldId, selectedOptionOrdinal: opt.ordinal }],
        mappings: mappingsFor(ir.fields),
        noteSha256: noteIdentity(NOTE)!,
      });
      expect(out.declined, `${field.fieldId} declined unexpectedly`).toEqual([]);
      expect(out.resolutions.find((r) => r.fieldId === field.fieldId)!.value).toBe(opt.value);
    }
  });
});

// ───────────────────────────────────────────────────────────────────────────
// 3 · THE WIRING — and these are the arms that kill the partial edits.
// ───────────────────────────────────────────────────────────────────────────
describe('3 · the fill actually applies the correction', () => {
  async function runFill(opts: { withNote: boolean; withOverride: boolean }) {
    const field = selects[0];
    const opt = field.allowedOptions[field.allowedOptions.length - 1];
    const prepared = await prepareTemplateTwinFill({
      compiledVersionId: 'cv1',
      noteTemplateId: 'tpl1',
      noteTemplateVersion: 1,
      ir,
      mappings: mappingsFor(ir.fields),
      facts: [],
      certifiedFieldIds: ir.fields.map((f) => f.fieldId),
      source: wmIovBytes,
      resolverModelVersion: null,
      validationNow: new Date('2026-08-24T00:00:00.000Z'),
      visitDate: new Date('2026-08-24T00:00:00.000Z'),
      markerText: undefined,
      generatedNote: opts.withNote ? NOTE : undefined,
      clinicianOverrides: opts.withOverride
        ? [{ fieldId: field.fieldId, selectedOptionOrdinal: opt.ordinal }]
        : [],
    });
    return {
      value: prepared.manifest.fields.find((f) => f.fieldId === field.fieldId)!.value,
      expected: opt.value,
      manifest: prepared.manifest,
    };
  }

  it('⚠️ KILLS "delete the clinicianOverrides argument" — the resolution MOVED', async () => {
    // The old gate asserted the STRING `clinicianOverrides` appeared in the
    // file, which the variable declaration satisfies. This asserts the VALUE in
    // the manifest changed, which nothing but a working overlay produces.
    const off = await runFill({ withNote: true, withOverride: false });
    const on = await runFill({ withNote: true, withOverride: true });
    expect(off.value).toBeNull();
    expect(on.value).toBe(on.expected);
  });

  it('⚠️ KILLS "make the overlay conditional on generatedNote"', async () => {
    // The correction must land on a fill that has NO generated note to bridge
    // from. Putting the overlay inside that ternary makes the feature quietly
    // conditional on something unrelated to it — and the old WIRING arm NAMED
    // this defect while being blind to it.
    const on = await runFill({ withNote: false, withOverride: true });
    expect(on.value).toBe(on.expected);
  });

  it('⚠️ a DECLINED correction becomes a manifest WARNING — never silent, never blocking', async () => {
    const field = selects[0];
    const prepared = await prepareTemplateTwinFill({
      compiledVersionId: 'cv1',
      noteTemplateId: 'tpl1',
      noteTemplateVersion: 1,
      ir,
      mappings: mappingsFor(ir.fields),
      facts: [],
      certifiedFieldIds: ir.fields.map((f) => f.fieldId),
      source: wmIovBytes,
      resolverModelVersion: null,
      validationNow: new Date('2026-08-24T00:00:00.000Z'),
      visitDate: new Date('2026-08-24T00:00:00.000Z'),
      markerText: undefined,
      generatedNote: NOTE,
      clinicianOverrides: [{ fieldId: field.fieldId, selectedOptionOrdinal: 9999 }],
    });
    const issues = prepared.manifest.validation.issues.filter(
      (i) => i.code === 'CLINICIAN_OVERRIDE_DECLINED',
    );
    expect(issues).toHaveLength(1);
    expect(issues[0].severity).toBe('warning');
    // ⚠️ AND IT DOES NOT STRAND THE DOCUMENT. Losing one correction must not
    // block the whole render.
    expect(prepared.manifest.validation.valid).toBe(true);
  });
});

// ───────────────────────────────────────────────────────────────────────────
// 4 · THE MODEL IS AN ACTOR, AND IT IS WIRED BY ITS PROMPT AND ITS SCHEMA.
// ───────────────────────────────────────────────────────────────────────────
describe('4 · the actor that invokes this was told', () => {
  it('⚠️ KILLS "move the .describe() onto value" — read from the WIRE form', () => {
    // F24-S4 shipped `rowOrdinal` with its safety rule in a TS doc comment.
    // `z.toJSONSchema()` emits `description` only from `.describe()`/`.meta()`,
    // so the model received an undocumented integer. This reads the converted
    // schema — the bytes the model actually gets — and pins the rule to
    // `controlOrdinal` SPECIFICALLY, so moving it onto `value` reddens.
    const json = JSON.stringify(z.toJSONSchema(ChatReplySchema));
    const schema = JSON.parse(json) as unknown;

    const found: { path: string; description?: string }[] = [];
    const walk = (node: unknown, at: string) => {
      if (!node || typeof node !== 'object') return;
      const obj = node as Record<string, unknown>;
      const props = obj.properties as Record<string, unknown> | undefined;
      if (props) {
        for (const [k, v] of Object.entries(props)) {
          const d = (v as Record<string, unknown>)?.description;
          if (k === 'controlOrdinal' || k === 'value') {
            found.push({ path: `${at}.${k}`, description: typeof d === 'string' ? d : undefined });
          }
          walk(v, `${at}.${k}`);
        }
      }
      for (const key of ['anyOf', 'oneOf', 'allOf']) {
        const arr = obj[key];
        if (Array.isArray(arr)) arr.forEach((n, i) => walk(n, `${at}.${key}[${i}]`));
      }
      if (obj.items) walk(obj.items, `${at}.items`);
    };
    walk(schema, '$');

    const ordinals = found.filter((f) => f.path.endsWith('.controlOrdinal'));
    // NON-VACUITY: the field must be in the wire schema at all.
    expect(ordinals.length, 'controlOrdinal is absent from the converted schema').toBeGreaterThan(0);
    for (const o of ordinals) {
      expect(o.description, `${o.path} reaches the model with no description`).toBeTruthy();
      // The ECHO rule is the one that makes it safe, and it must be on the
      // ordinal — not on a neighbour.
      expect(o.description!.toLowerCase()).toContain('list');
      expect(o.description!.toLowerCase()).toMatch(/never one you counted|never .*yourself/);
    }
  });

  it('⚠️ the PROMPT names the intent and its ask-which rule', () => {
    const prompt = String(CHAT_EDIT_SYSTEM);
    expect(prompt).toContain('edit_form_control');
    expect(prompt).toContain('controlOrdinal');
    // Positive control: a sibling that is known to be present, so a broken
    // matcher cannot read as "the rule is missing".
    expect(prompt).toContain('edit_table_cell');
  });

  it('⚠️ THE ASK IS ANSWERABLE — the discriminator exists for every ambiguous control', () => {
    // The refuted slice mandated "quote the two labels and their numbers" while
    // 18 of 28 controls share a label BYTE-IDENTICALLY, with option sets
    // matching in pairs. The question it told the model to ask read "did you
    // mean #25 '<sentence>' or #30 '<the identical sentence>'?" — the
    // never-ask-an-unanswerable-question invariant, on a new carrier.
    const controls = listEditableFormControls(ir);
    const byLabel = new Map<string, number>();
    for (const c of controls) byLabel.set(c.label, (byLabel.get(c.label) ?? 0) + 1);

    const ambiguous = controls.filter((c) => (byLabel.get(c.label) ?? 0) > 1);
    // NON-VACUITY, and it is the measured production figure: 18 of 28.
    expect(ambiguous.length).toBe(18);
    expect(controls.length - ambiguous.length).toBe(10);

    for (const c of ambiguous) {
      expect(c.sameLabelIndex, `${c.ordinal} is ambiguous with no occurrence index`).toBeTruthy();
      expect(c.sameLabelTotal).toBe(byLabel.get(c.label));
    }
    // Unambiguous controls carry NO occurrence — noise the model must not
    // reason past.
    for (const c of controls.filter((x) => (byLabel.get(x.label) ?? 0) === 1)) {
      expect(c.sameLabelIndex).toBeNull();
    }
    // And it reaches the model.
    const shown = formControlsForModel(controls);
    expect(shown.filter((s) => s.occurrence).length).toBe(18);
    // ⚠️ THE DISCRIMINATOR ACTUALLY DISCRIMINATES: within one label group the
    // occurrence strings are distinct, which is the whole point.
    for (const [label, n] of byLabel) {
      if (n <= 1) continue;
      const occ = controls.filter((c) => c.label === label).map((c) => c.sameLabelIndex);
      expect(new Set(occ).size).toBe(n);
    }
  });

  it('⚠️ no fieldId ever crosses to the model', () => {
    const shown = JSON.stringify(formControlsForModel(listEditableFormControls(ir)));
    expect(shown).not.toContain('ttf_');
  });
});

// ───────────────────────────────────────────────────────────────────────────
// 5 · THE ORDERING IS EARNED, NOT INHERITED.
// ───────────────────────────────────────────────────────────────────────────
describe('5 · document order is produced, not assumed', () => {
  it('⚠️ SHUFFLED INPUT still yields document order — the .sort() is load-bearing', () => {
    // The old order arm asserted the output was sorted while `ir.fields`
    // arrived PRE-SORTED, so deleting the `.sort()` left it green. You could
    // predict that arm's result from the target alone, which is the tell.
    const shuffled: TemplateDocIR = {
      ...ir,
      fields: [...ir.fields].reverse(),
    };
    const fromShuffled = listEditableFormControls(shuffled);
    const fromOriginal = listEditableFormControls(ir);
    expect(fromShuffled.map((c) => c.fieldId)).toEqual(fromOriginal.map((c) => c.fieldId));
    // Non-vacuity: the shuffle really did change the input order.
    expect(shuffled.fields.map((f) => f.fieldId)).not.toEqual(ir.fields.map((f) => f.fieldId));
    // And the result really is by displayOrder.
    const orders = fromShuffled.map(
      (c) => ir.fields.find((f) => f.fieldId === c.fieldId)!.displayOrder,
    );
    expect(orders).toEqual([...orders].sort((a, b) => a - b));
  });

  it('ordinals are 1-based and contiguous over the offered set', () => {
    const controls = listEditableFormControls(ir);
    expect(controls.map((c) => c.ordinal)).toEqual(
      controls.map((_, i) => i + 1),
    );
  });
});
