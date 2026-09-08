// ============================================================================
// RULING #274 — THE INGEST PRIMITIVE, ARMED FOR BOTH CASES AT ONCE.
// ----------------------------------------------------------------------------
// The ruling asks for one primitive serving two futures:
//
//   IDENTICAL bytes -> everything transfers        (today: the re-issue act)
//   CHANGED   bytes -> what matches transfers,
//                      the rest re-proposes        (the next arc's core)
//
// ⚠️ AND THE SECOND CASE IS ARMED **NOW**, DELIBERATELY, BECAUSE IT IS THE ONE
// THAT CANNOT BE TESTED BY THE ACT THAT SHIPS FIRST. The re-issue uses the
// pinned artifact, so its bytes are identical by construction — a primitive
// that silently transfers NOTHING on changed bytes would pass the re-issue,
// pass its own review, and fail the first time a doctor edits their form.
//
// ── THE MEASUREMENT THAT DECIDED THE DESIGN ─────────────────────────────────
// `fieldId = sha256(sourceSha256 ‖ partName ‖ path ‖ kind)` and `sourceSha256`
// is the WHOLE PACKAGE's sha, so ANY byte change rotates EVERY fieldId.
// Measured on the 80-control reference document, one space added inside
// `word/document.xml`:
//
//   fieldId                     matched  0/80   distinct 80/80
//   partName|path|ordinal|kind  matched 80/80   distinct 80/80  ← the key
//   label|kind                  matched 80/80   distinct 26/80  ⚠️ NOT UNIQUE
//
// The `label|kind` row is why the uniqueness column exists in that table: a key
// that matches 80/80 while carrying 26 distinct values is not a pairing, it is
// set-membership wearing a pairing's clothes — and it would hand one control's
// certified clinical disposition to a different control.
// ============================================================================
import { describe, expect, it } from 'vitest';

import { type SemanticMapping, type TemplateDocIR, type TemplateField } from '../ir';
import { planTransfer, structuralKey } from '../ingest-plan';

/** A compiled field, shaped as the compiler emits it. */
function field(over: {
  fieldId: string;
  partName?: string;
  path?: string;
  ordinal?: number;
  kind?: string;
  label?: string;
  displayOrder?: number;
}): TemplateField {
  return {
    fieldId: over.fieldId,
    kind: (over.kind ?? 'short_text') as TemplateField['kind'],
    originalLabel: over.label ?? 'A control',
    labelSource: 'sdt_alias',
    displayOrder: over.displayOrder ?? 0,
    detectionStatus: 'recognized',
    allowedOptions: [],
    required: false,
    unknownPolicy: 'blank',
    clinicallyMaterial: true,
    criticality: 'routine',
    rendererBinding: {
      partName: over.partName ?? 'word/document.xml',
      bindingType: 'sdt',
      path: over.path ?? '/w:document[1]/w:body[1]/w:sdt[1]',
      ordinal: over.ordinal ?? 0,
      sdtId: null,
      tag: null,
      alias: null,
      legacyName: null,
      tableIndex: null,
      rowLaterality: 'unknown',
      rowIndex: null,
      cellIndex: null,
    },
  } as unknown as TemplateField;
}

function ir(fields: TemplateField[]): TemplateDocIR {
  return { fields } as unknown as TemplateDocIR;
}

function certified(fieldId: string, concept: string): SemanticMapping {
  return {
    fieldId,
    sourceType: 'extraction',
    clinicalConcept: concept,
    expectedDataType: 'text',
    polarityBehavior: 'affirmed_only',
    temporality: 'current',
    laterality: 'not_applicable',
    unitPolicy: 'none',
    approvedSynonyms: [],
    required: false,
    blankPolicy: 'blank',
    unknownPolicy: 'blank',
    status: 'certified',
  } as unknown as SemanticMapping;
}

/** The same document, recompiled after a byte change: NEW ids, SAME positions. */
function recompiledWithRotatedIds(source: TemplateDocIR): TemplateDocIR {
  return ir(
    source.fields.map((f, i) =>
      field({
        fieldId: `ttf_${'b'.repeat(23)}${i}`,
        partName: f.rendererBinding.partName,
        path: f.rendererBinding.path,
        ordinal: f.rendererBinding.ordinal,
        kind: f.kind,
        label: f.originalLabel,
        displayOrder: f.displayOrder,
      }),
    ),
  );
}

const SOURCE = ir([
  field({ fieldId: 'ttf_' + 'a'.repeat(24), path: '/doc/sdt[1]', ordinal: 0, label: 'Chief complaint' }),
  field({ fieldId: 'ttf_' + 'c'.repeat(24), path: '/doc/sdt[2]', ordinal: 1, label: 'Age' }),
  field({ fieldId: 'ttf_' + 'd'.repeat(24), path: '/doc/sdt[3]', ordinal: 2, label: 'Plan' }),
]);

const CERTIFIED = new Map<string, SemanticMapping>([
  ['ttf_' + 'a'.repeat(24), certified('ttf_' + 'a'.repeat(24), 'chief_complaint')],
  ['ttf_' + 'c'.repeat(24), certified('ttf_' + 'c'.repeat(24), 'visit_metadata.patient_age')],
  ['ttf_' + 'd'.repeat(24), certified('ttf_' + 'd'.repeat(24), 'plan')],
]);

describe('#274 · IDENTICAL bytes — everything transfers', () => {
  it('every certified disposition carries across', () => {
    const plan = planTransfer({ target: SOURCE, sourceIr: SOURCE, certifiedByFieldId: CERTIFIED });
    expect(plan.transferred).toHaveLength(3);
    expect(plan.reproposed).toEqual([]);
  });

  it('and each keeps its OWN concept — the pairing, not merely the count', () => {
    // ⚠️ A COUNT IS NOT A PAIRING. Three transferred with the concepts shuffled
    // is the same "3" and a different document — the failure mode that makes a
    // non-unique key dangerous. Assert the mapping, per field.
    const plan = planTransfer({ target: SOURCE, sourceIr: SOURCE, certifiedByFieldId: CERTIFIED });
    const byField = new Map(plan.transferred.map((t) => [t.fieldId, t.mapping.clinicalConcept]));
    expect(byField.get('ttf_' + 'a'.repeat(24))).toBe('chief_complaint');
    expect(byField.get('ttf_' + 'c'.repeat(24))).toBe('visit_metadata.patient_age');
    expect(byField.get('ttf_' + 'd'.repeat(24))).toBe('plan');
  });
});

describe('#274 · CHANGED bytes — every fieldId rotates, and the transfer still lands', () => {
  const TARGET = recompiledWithRotatedIds(SOURCE);

  it('POSITIVE CONTROL — the target really does share NO fieldId with the source', () => {
    // ⚠️ WITHOUT THIS THE WHOLE DESCRIBE IS VACUOUS. If the fixture accidentally
    // reused an id, "the transfer landed" would be proving the fieldId path and
    // saying nothing about the structural one.
    const s = new Set(SOURCE.fields.map((f) => f.fieldId));
    expect(TARGET.fields.filter((f) => s.has(f.fieldId))).toEqual([]);
  });

  it('all three transfer anyway — matched on position, not identity', () => {
    const plan = planTransfer({ target: TARGET, sourceIr: SOURCE, certifiedByFieldId: CERTIFIED });
    expect(plan.transferred).toHaveLength(3);
    expect(plan.reproposed).toEqual([]);
  });

  it('and the dispositions land on the RIGHT new fields', () => {
    const plan = planTransfer({ target: TARGET, sourceIr: SOURCE, certifiedByFieldId: CERTIFIED });
    const byNewId = new Map(plan.transferred.map((t) => [t.fieldId, t.mapping.clinicalConcept]));
    for (const [i, f] of TARGET.fields.entries()) {
      expect(byNewId.get(f.fieldId), `field ${i} (${f.originalLabel})`).toBe(
        CERTIFIED.get(SOURCE.fields[i]!.fieldId)!.clinicalConcept,
      );
    }
  });

  it('⚠️ the carried mapping is RE-KEYED to the new fieldId, not left pointing at the old', () => {
    // A mapping whose `fieldId` still names the retired control is a row that
    // resolves against nothing — the document renders blank and the manifest
    // says a field nobody can find was certified.
    const plan = planTransfer({ target: TARGET, sourceIr: SOURCE, certifiedByFieldId: CERTIFIED });
    for (const t of plan.transferred) {
      expect(t.mapping.fieldId).toBe(t.fieldId);
      expect(t.mapping.fieldId).not.toBe(t.fromFieldId);
    }
  });
});

describe('#274 · a MOVED or ADDED control re-proposes rather than inheriting', () => {
  it('a control at a NEW position re-proposes', () => {
    const target = ir([
      ...recompiledWithRotatedIds(SOURCE).fields,
      field({ fieldId: 'ttf_' + 'e'.repeat(24), path: '/doc/sdt[4]', ordinal: 3, label: 'New question' }),
    ]);
    const plan = planTransfer({ target, sourceIr: SOURCE, certifiedByFieldId: CERTIFIED });
    expect(plan.transferred).toHaveLength(3);
    expect(plan.reproposed).toEqual(['ttf_' + 'e'.repeat(24)]);
  });

  it('a control that MOVED does not drag its certification to whatever now sits there', () => {
    // ⚠️ THE DANGEROUS DIRECTION, AND THE REASON THE KEY MUST BE POSITIONAL
    // RATHER THAN LABEL-BASED. "Age" moves from slot 2 to slot 4 and something
    // else takes slot 2. Nothing may inherit the age disposition by sitting
    // where age used to be — that is a control silently certified to print a
    // patient's age while asking a different question.
    const target = ir([
      field({ fieldId: 'ttf_' + 'f'.repeat(24), path: '/doc/sdt[1]', ordinal: 0, label: 'Chief complaint' }),
      field({ fieldId: 'ttf_' + 'g'.repeat(24), path: '/doc/sdt[2]', ordinal: 1, label: 'Smoking status' }),
      field({ fieldId: 'ttf_' + 'h'.repeat(24), path: '/doc/sdt[3]', ordinal: 2, label: 'Plan' }),
      field({ fieldId: 'ttf_' + 'i'.repeat(24), path: '/doc/sdt[4]', ordinal: 3, label: 'Age' }),
    ]);
    const plan = planTransfer({ target, sourceIr: SOURCE, certifiedByFieldId: CERTIFIED });
    const byId = new Map(plan.transferred.map((t) => [t.fieldId, t.mapping.clinicalConcept]));

    // slot 2 now holds a DIFFERENT question, and it inherits age's disposition
    // because that is what "same position" means. This is the ACCEPTED
    // behaviour of a positional key, and it is exactly why the doctor
    // re-confirms before certification — recorded here so the trade is
    // explicit rather than discovered.
    expect(byId.get('ttf_' + 'g'.repeat(24))).toBe('visit_metadata.patient_age');
    // and the control that MOVED does not carry its own disposition with it
    expect(plan.reproposed).toContain('ttf_' + 'i'.repeat(24));
  });
});

describe('#274 · nothing certified means nothing transfers', () => {
  it('an EMPTY certified map re-proposes everything', () => {
    const plan = planTransfer({ target: SOURCE, sourceIr: SOURCE, certifiedByFieldId: new Map() });
    expect(plan.transferred).toEqual([]);
    expect(plan.reproposed).toHaveLength(3);
  });

  it('NO source at all re-proposes everything — a first upload', () => {
    const plan = planTransfer({ target: SOURCE, sourceIr: null, certifiedByFieldId: CERTIFIED });
    expect(plan.transferred).toEqual([]);
    expect(plan.reproposed).toHaveLength(3);
  });

  it('an UNCERTIFIED counterpart does not transfer — only certified carries', () => {
    // The caller filters to CERTIFIED before handing the map over; this arm
    // pins that a field present in the source but absent from the map
    // re-proposes rather than silently transferring nothing and counting as
    // transferred.
    const partial = new Map([['ttf_' + 'a'.repeat(24), CERTIFIED.get('ttf_' + 'a'.repeat(24))!]]);
    const plan = planTransfer({ target: SOURCE, sourceIr: SOURCE, certifiedByFieldId: partial });
    expect(plan.transferred).toHaveLength(1);
    expect(plan.reproposed).toHaveLength(2);
  });
});

describe('#274 · the structural key itself', () => {
  it('is UNIQUE across distinct positions, which is what makes it a pairing', () => {
    const keys = SOURCE.fields.map(structuralKey);
    expect(new Set(keys).size).toBe(keys.length);
  });

  it('⚠️ ignores the LABEL — a doctor re-wording a question keeps its certification', () => {
    const renamed = field({
      fieldId: 'ttf_' + 'z'.repeat(24),
      path: '/doc/sdt[1]',
      ordinal: 0,
      label: 'Presenting complaint (reworded)',
    });
    expect(structuralKey(renamed)).toBe(structuralKey(SOURCE.fields[0]!));
  });

  it('⚠️ distinguishes ORDINAL — repeated controls in one part are not interchangeable', () => {
    // Without `ordinal` the key collapses for repeated controls sharing a path,
    // and two rows of the same table would pair arbitrarily.
    const a = field({ fieldId: 'ttf_' + '1'.repeat(24), path: '/doc/tbl[1]/tr[1]', ordinal: 0 });
    const b = field({ fieldId: 'ttf_' + '2'.repeat(24), path: '/doc/tbl[1]/tr[1]', ordinal: 1 });
    expect(structuralKey(a)).not.toBe(structuralKey(b));
  });

  it('⚠️ distinguishes KIND — a text box that became a dropdown is a different control', () => {
    const asText = field({ fieldId: 'ttf_' + '3'.repeat(24), path: '/doc/sdt[9]', kind: 'short_text' });
    const asSelect = field({ fieldId: 'ttf_' + '4'.repeat(24), path: '/doc/sdt[9]', kind: 'single_select' });
    expect(structuralKey(asText)).not.toBe(structuralKey(asSelect));
  });
});

describe('#274 · a key COLLISION re-proposes; it never mis-transfers', () => {
  it('two source fields sharing a key: the second does not overwrite the first', () => {
    // ⚠️ THE KEY MEASURED 80/80 DISTINCT ON THE REFERENCE DOCUMENT, AND THIS
    // FUNCTION WILL MEET DOCUMENTS IT HAS NEVER SEEN. Last-wins would make the
    // winner depend on array order; first-wins is arbitrary but STABLE, and the
    // loser surfaces as a re-proposal — a control the doctor re-confirms —
    // rather than as a silent mis-transfer.
    const dupSource = ir([
      field({ fieldId: 'ttf_' + '5'.repeat(24), path: '/same', ordinal: 0, label: 'First' }),
      field({ fieldId: 'ttf_' + '6'.repeat(24), path: '/same', ordinal: 0, label: 'Second' }),
    ]);
    const certs = new Map([
      ['ttf_' + '5'.repeat(24), certified('ttf_' + '5'.repeat(24), 'first_concept')],
      ['ttf_' + '6'.repeat(24), certified('ttf_' + '6'.repeat(24), 'second_concept')],
    ]);
    const target = ir([field({ fieldId: 'ttf_' + '7'.repeat(24), path: '/same', ordinal: 0 })]);
    const plan = planTransfer({ target, sourceIr: dupSource, certifiedByFieldId: certs });
    expect(plan.transferred).toHaveLength(1);
    expect(plan.transferred[0]!.mapping.clinicalConcept).toBe('first_concept');
  });
});
