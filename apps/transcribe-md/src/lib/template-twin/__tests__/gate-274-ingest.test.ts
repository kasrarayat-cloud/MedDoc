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
import { identityKeyPairs, identityKeys, planTransfer } from '../ingest-plan';

/** A compiled field, shaped as the compiler emits it. */
function field(over: {
  fieldId: string;
  partName?: string;
  path?: string;
  ordinal?: number;
  kind?: string;
  label?: string;
  displayOrder?: number;
  sdtId?: string | null;
  tag?: string | null;
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
      sdtId: over.sdtId ?? null,
      tag: over.tag ?? null,
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
        tag: f.rendererBinding.tag,
      }),
    ),
  );
}

const SOURCE = ir([
  field({ fieldId: 'ttf_' + 'a'.repeat(24), path: '/doc/sdt[1]', ordinal: 0, label: 'Chief complaint', tag: 't_chief' }),
  field({ fieldId: 'ttf_' + 'c'.repeat(24), path: '/doc/sdt[2]', ordinal: 1, label: 'Age', tag: 't_age' }),
  field({ fieldId: 'ttf_' + 'd'.repeat(24), path: '/doc/sdt[3]', ordinal: 2, label: 'Plan', tag: 't_plan' }),
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

describe('#274 · ⚠️ AN INSERT MUST NOT RE-PAIR EVERY DOWNSTREAM CONTROL', () => {
  // ══════════════════════════════════════════════════════════════════════════
  // THIS IS THE ARM THE FIRST DESIGN DID NOT HAVE, AND ITS ABSENCE IS WHY A
  // POSITIONAL KEY SHIPPED THROUGH 16 GREEN ARMS.
  //
  // The old fixtures hand-wrote `/doc/sdt[1..4]` as fixed literals with a fixed
  // slot count, so they could express a REORDER and never a SHIFT. Measured on
  // the real 80-control document, inserting one control at the top:
  //
  //     transferred = 3,  same control = 0,  MIS-PAIRED = 3,  status certified
  //
  // Every component of the old key shifts in lockstep on an insert — `path` is
  // a sibling index, `ordinal` is a document-wide counter — so control N takes
  // control N-1's identity. The fixture below reproduces that shift EXACTLY:
  // positions renumber, ids rotate, and only `sdtId` survives, which is what a
  // real Word edit does.
  // ══════════════════════════════════════════════════════════════════════════
  const AFTER_INSERT = ir([
    // the new control takes slot 1 and pushes everything down
    field({ fieldId: 'ttf_' + 'n'.repeat(24), path: '/doc/sdt[1]', ordinal: 0, label: 'NEW question', tag: 't_new' }),
    field({ fieldId: 'ttf_' + 'p'.repeat(24), path: '/doc/sdt[2]', ordinal: 1, label: 'Chief complaint', tag: 't_chief' }),
    field({ fieldId: 'ttf_' + 'q'.repeat(24), path: '/doc/sdt[3]', ordinal: 2, label: 'Age', tag: 't_age' }),
    field({ fieldId: 'ttf_' + 'r'.repeat(24), path: '/doc/sdt[4]', ordinal: 3, label: 'Plan', tag: 't_plan' }),
  ]);

  it('POSITIVE CONTROL — every position really did shift, and every id rotated', () => {
    // Without this the arm below could pass on a fixture where nothing moved.
    const oldPaths = SOURCE.fields.map((f) => f.rendererBinding.path);
    const shifted = AFTER_INSERT.fields.filter((f) => oldPaths.includes(f.rendererBinding.path));
    expect(shifted.length, 'the fixture must REUSE the old paths at new controls').toBeGreaterThan(0);
    const oldIds = new Set(SOURCE.fields.map((f) => f.fieldId));
    expect(AFTER_INSERT.fields.filter((f) => oldIds.has(f.fieldId))).toEqual([]);
  });

  it('⚠️ NO control inherits a disposition belonging to a DIFFERENT control', () => {
    const plan = planTransfer({ target: AFTER_INSERT, sourceIr: SOURCE, certifiedByFieldId: CERTIFIED });
    const conceptOfLabel = new Map(
      SOURCE.fields.map((f) => [f.originalLabel, CERTIFIED.get(f.fieldId)!.clinicalConcept]),
    );
    const labelOfNew = new Map(AFTER_INSERT.fields.map((f) => [f.fieldId, f.originalLabel]));
    const misPaired = plan.transferred.filter(
      (t) => t.mapping.clinicalConcept !== conceptOfLabel.get(labelOfNew.get(t.fieldId)!),
    );
    expect(
      misPaired.map((t) => `${labelOfNew.get(t.fieldId)} <- ${t.mapping.clinicalConcept}`),
      'a control inherited another control\'s CERTIFIED clinical disposition',
    ).toEqual([]);
  });

  it('the three surviving controls DO keep their own dispositions, via their TAG', () => {
    // ⚠️ THE OTHER HALF, AND IT MUST PULL THE OPPOSITE WAY. An implementation
    // that transfers NOTHING also has zero mis-pairs, so the arm above alone is
    // bought by refusing everything.
    const plan = planTransfer({ target: AFTER_INSERT, sourceIr: SOURCE, certifiedByFieldId: CERTIFIED });
    expect(plan.transferred).toHaveLength(3);
    const byLabel = new Map(
      plan.transferred.map((t) => [
        AFTER_INSERT.fields.find((f) => f.fieldId === t.fieldId)!.originalLabel,
        t.mapping.clinicalConcept,
      ]),
    );
    expect(byLabel.get('Chief complaint')).toBe('chief_complaint');
    expect(byLabel.get('Age')).toBe('visit_metadata.patient_age');
    expect(byLabel.get('Plan')).toBe('plan');
    expect(plan.reproposed).toEqual(['ttf_' + 'n'.repeat(24)]);
  });

  it('a DELETION is symmetric — nothing shifts up into a neighbour\'s certification', () => {
    const afterDelete = ir([
      field({ fieldId: 'ttf_' + 's'.repeat(24), path: '/doc/sdt[1]', ordinal: 0, label: 'Age', tag: 't_age' }),
      field({ fieldId: 'ttf_' + 't'.repeat(24), path: '/doc/sdt[2]', ordinal: 1, label: 'Plan', tag: 't_plan' }),
    ]);
    const plan = planTransfer({ target: afterDelete, sourceIr: SOURCE, certifiedByFieldId: CERTIFIED });
    const byLabel = new Map(
      plan.transferred.map((t) => [
        afterDelete.fields.find((f) => f.fieldId === t.fieldId)!.originalLabel,
        t.mapping.clinicalConcept,
      ]),
    );
    expect(byLabel.get('Age')).toBe('visit_metadata.patient_age');
    expect(byLabel.get('Plan')).toBe('plan');
  });

  it('⚠️ a control with NO tag re-proposes rather than guessing', () => {
    // 52 of the reference document's 80 controls carry no sdtId. They lose
    // their certification on an edit, and that is the RULED-SAFE direction: a
    // re-proposal is a question to the doctor, a mis-transfer is a wrong answer
    // presented as certified.
    const noIdSource = ir([field({ fieldId: 'ttf_' + 'u'.repeat(24), path: '/doc/sdt[1]', ordinal: 0, label: 'X', tag: null })]);
    const noIdTarget = ir([field({ fieldId: 'ttf_' + 'v'.repeat(24), path: '/doc/sdt[2]', ordinal: 1, label: 'X', tag: null })]);
    const certs = new Map([['ttf_' + 'u'.repeat(24), certified('ttf_' + 'u'.repeat(24), 'some_concept')]]);
    const plan = planTransfer({ target: noIdTarget, sourceIr: noIdSource, certifiedByFieldId: certs });
    expect(plan.transferred).toEqual([]);
    expect(plan.reproposed).toEqual(['ttf_' + 'v'.repeat(24)]);
  });

  it('⚠️ a kind CHANGE on the same TAG does not inherit — same name, different question', () => {
    const changed = ir([
      field({ fieldId: 'ttf_' + 'w'.repeat(24), path: '/doc/sdt[1]', ordinal: 0, label: 'Age', tag: 't_age', kind: 'single_select' }),
    ]);
    const plan = planTransfer({ target: changed, sourceIr: SOURCE, certifiedByFieldId: CERTIFIED });
    expect(plan.transferred).toEqual([]);
    expect(plan.reproposed).toHaveLength(1);
  });
});

describe('#274 · ⚠️ the SOURCE-TYPE split — 43 of 53, not 53 of 53', () => {
  // ══════════════════════════════════════════════════════════════════════════
  // MEASURED ON THE OWNER'S CERTIFIED VERSION `18a7ae19`:
  //
  //     extraction | CERTIFIED | 43
  //     manual     | CERTIFIED | 10
  //
  // ALL FIFTY-THREE ARE `CERTIFIED`. So a filter on `mappingStatus` alone
  // transfers 53, while the ruling says *transfer the 43, re-propose the ten* —
  // and the split it names is by SOURCE TYPE. The two are easy to conflate
  // because here one implies the other.
  //
  // ⚠️ THE DECLARED GUARD IS WHAT CAUGHT IT. `expectTransferCount: 43` would
  // have aborted the act against a plan of 53 — a declaration whose numbers come
  // from the RULING rather than from the CODE is the only thing that can
  // disagree with the code.
  //
  // These arms drive `planTransfer` directly with the two shapes, since the
  // filter is applied by the caller building the certified map.
  // ══════════════════════════════════════════════════════════════════════════
  const tagged = (fieldId: string, tag: string) => field({ fieldId, tag, label: tag });
  const src = ir([
    tagged('ttf_' + 'x'.repeat(24), 'extracted_one'),
    tagged('ttf_' + 'y'.repeat(24), 'manual_one'),
  ]);
  const tgt = ir([
    tagged('ttf_' + 'z'.repeat(24), 'extracted_one'),
    tagged('ttf_' + 'w'.repeat(24), 'manual_one'),
  ]);
  const withType = (fieldId: string, concept: string, sourceType: string) =>
    ({ ...certified(fieldId, concept), sourceType }) as ReturnType<typeof certified>;

  it('ALL certified rows transfer when no source type is selected', () => {
    const certs = new Map([
      ['ttf_' + 'x'.repeat(24), withType('ttf_' + 'x'.repeat(24), 'c_extract', 'extraction')],
      ['ttf_' + 'y'.repeat(24), withType('ttf_' + 'y'.repeat(24), 'c_manual', 'manual')],
    ]);
    expect(planTransfer({ target: tgt, sourceIr: src, certifiedByFieldId: certs }).transferred).toHaveLength(2);
  });

  it('⚠️ filtering to `extraction` leaves the manual one to RE-PROPOSE', () => {
    // what the caller does: build the map from the selected source types only
    const certs = new Map([
      ['ttf_' + 'x'.repeat(24), withType('ttf_' + 'x'.repeat(24), 'c_extract', 'extraction')],
    ]);
    const plan = planTransfer({ target: tgt, sourceIr: src, certifiedByFieldId: certs });
    expect(plan.transferred).toHaveLength(1);
    expect(plan.transferred[0]!.mapping.clinicalConcept).toBe('c_extract');
    // the manual control is re-proposed, which is what the owner then confirms
    expect(plan.reproposed).toEqual(['ttf_' + 'w'.repeat(24)]);
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

describe("#274 · ⚠️ AMBIGUITY IS PER-KEY — the owner's form proved it", () => {
  // ══════════════════════════════════════════════════════════════════════════
  // THE RULED ACT'S OWN GUARD CAUGHT THIS, BEFORE A ROW MOVED.
  //
  // The owner's 53-control form carries 53 tags but only 35 DISTINCT ones. The
  // first bijection asked whether EVERY key a field answers to is unique and
  // disqualified the field entirely if any one was shared. So every control
  // with a shared tag was refused — even though its `fieldId` is unique and
  // EXACT, the re-issue re-ingesting the very artifact the certified version
  // was compiled from.
  //
  // ⚠️ MEASURED ON `18a7ae19`, NOT INFERRED. EIGHT tags are shared, not three:
  // plan x5, impression x4, patient_is_a_pleasant_age_... x4, family_history
  // x3, past_medical_history x3, past_surgical_history x3, allergies x2,
  // the_patient_medications_were_reviewed_an x2. That is 26 controls sharing a
  // tag, 23 of them among the 43 `extraction` rows.
  //
  //     18 IS THE SURPLUS (53 - 35), NOT A CONTROL COUNT. An earlier version of
  //     this comment said "eighteen controls" in both this file and
  //     ingest-plan.ts; both members of a shared pair are refused, not just the
  //     extra one.
  //
  // Measured: 20 planned where 43 was declared (43 - 23 = 20, exactly).
  // TRANSFER_COUNT_MISMATCH.
  //
  //     AMBIGUITY IS A PROPERTY OF A KEY, NOT OF A CONTROL.
  // ══════════════════════════════════════════════════════════════════════════
  const withTag = (fieldId: string, tag: string, label: string) => field({ fieldId, tag, label });

  it('⚠️ IDENTICAL bytes: a shared TAG must not block an exact fieldId match', () => {
    // three controls sharing the tag `plan`, as the real form does
    const ids = ['ttf_' + 'p'.repeat(24), 'ttf_' + 'q'.repeat(24), 'ttf_' + 'r'.repeat(24)];
    const doc = ir(ids.map((id, i) => withTag(id, 'plan', `Plan ${i}`)));
    const certs = new Map(ids.map((id, i) => [id, certified(id, `concept_${i}`)]));
    // identical bytes => the SAME fieldIds on both sides
    const plan = planTransfer({ target: doc, sourceIr: doc, certifiedByFieldId: certs });
    expect(plan.transferred, 'a shared tag blocked an exact fieldId match').toHaveLength(3);
    for (const [i, id] of ids.entries()) {
      expect(plan.transferred.find((t) => t.fieldId === id)!.mapping.clinicalConcept).toBe(`concept_${i}`);
    }
  });

  it('and the shared TAG still carries nothing when the fieldIds differ', () => {
    // changed bytes: ids rotate, so only the tag could match — and it is shared,
    // so nothing may transfer. The safety property is untouched.
    //
    // ⚠️ REGRESSION GUARD, NOT A PROOF OF THE PER-KEY DELTA — measured, and
    // stated because the commit that added it claimed otherwise. Run against
    // the PRE-#1087 per-FIELD code this arm ALSO passes: old and new both
    // refuse everything here, for different reasons. It is worth keeping and it
    // does not discriminate.
    const src = ir([withTag('ttf_' + 'a'.repeat(24), 'plan', 'Plan A'), withTag('ttf_' + 'b'.repeat(24), 'plan', 'Plan B')]);
    const certs = new Map([
      ['ttf_' + 'a'.repeat(24), certified('ttf_' + 'a'.repeat(24), 'concept_a')],
      ['ttf_' + 'b'.repeat(24), certified('ttf_' + 'b'.repeat(24), 'concept_b')],
    ]);
    const tgt = ir([withTag('ttf_' + 'c'.repeat(24), 'plan', 'Plan A'), withTag('ttf_' + 'd'.repeat(24), 'plan', 'Plan B')]);
    const plan = planTransfer({ target: tgt, sourceIr: src, certifiedByFieldId: certs });
    expect(plan.transferred, 'an ambiguous tag carried a disposition').toEqual([]);
  });

  it('a UNIQUE tag still carries across rotated ids, beside ambiguous siblings', () => {
    // one unique tag among duplicates, with the ids rotated.
    //
    // ⚠️ REGRESSION GUARD, NOT A PROOF OF THE PER-KEY DELTA. This arm's own
    // comment used to read "THE MIXED CASE, which is what the real form is",
    // and the commit message advertised it as such. It is neither. Measured
    // against the PRE-#1087 code it passes unchanged: `exam_lungs` is unique on
    // BOTH sides, so the per-FIELD rule never disqualified it either. The real
    // form's mixed case is IDENTICAL bytes with shared and unique tags side by
    // side — the arm below, which is the one that discriminates.
    const src = ir([
      withTag('ttf_' + 'e'.repeat(24), 'plan', 'Plan A'),
      withTag('ttf_' + 'f'.repeat(24), 'plan', 'Plan B'),
      withTag('ttf_' + 'g'.repeat(24), 'exam_lungs', 'Lungs'),
    ]);
    const certs = new Map([
      ['ttf_' + 'e'.repeat(24), certified('ttf_' + 'e'.repeat(24), 'c_a')],
      ['ttf_' + 'f'.repeat(24), certified('ttf_' + 'f'.repeat(24), 'c_b')],
      ['ttf_' + 'g'.repeat(24), certified('ttf_' + 'g'.repeat(24), 'c_lungs')],
    ]);
    const tgt = ir([
      withTag('ttf_' + 'h'.repeat(24), 'plan', 'Plan A'),
      withTag('ttf_' + 'i'.repeat(24), 'plan', 'Plan B'),
      withTag('ttf_' + 'j'.repeat(24), 'exam_lungs', 'Lungs'),
    ]);
    const plan = planTransfer({ target: tgt, sourceIr: src, certifiedByFieldId: certs });
    expect(plan.transferred).toHaveLength(1);
    expect(plan.transferred[0]!.mapping.clinicalConcept).toBe('c_lungs');
  });

  it("⚠️ THE REAL FORM'S MIXED CASE — shared and unique tags side by side, IDENTICAL bytes", () => {
    // ⚠️ THIS IS THE ARM THE COMMIT CLAIMED TO HAVE AND DID NOT, and it is the
    // shape the ruled act actually runs: the re-issue re-ingests the very
    // artifact the certified version was compiled from, so the bytes — and
    // therefore every `fieldId` — are IDENTICAL on both sides.
    //
    // MEASURED ON THE CERTIFIED VERSION `18a7ae19`: 53 controls, 53 tags, 35
    // distinct. EIGHT tags are shared, covering 26 controls; 27 controls have a
    // tag of their own. Of the 43 `extraction` rows the act transfers, 23 sit
    // on a shared tag and 20 do not.
    //
    // Under the PRE-#1087 per-FIELD rule this arm yields 2 of 5 — only the
    // unique-tag controls survive, and 43 - 23 = 20 is that same subtraction on
    // the real document. Under the shipped per-KEY rule it yields 5 of 5.
    // THAT is what makes this arm load-bearing where the two above are not.
    const shared = ['ttf_' + 's'.repeat(24), 'ttf_' + 't'.repeat(24), 'ttf_' + 'u'.repeat(24)];
    const unique = ['ttf_' + 'v'.repeat(24), 'ttf_' + 'w'.repeat(24)];
    const doc = ir([
      ...shared.map((id, i) => withTag(id, 'plan', `Plan ${i}`)),
      withTag(unique[0]!, 'impression', 'Impression'),
      withTag(unique[1]!, 'exam_lungs', 'Lungs'),
    ]);
    const all = [...shared, ...unique];
    const certs = new Map(all.map((id, i) => [id, certified(id, `concept_${i}`)]));

    // identical bytes => the SAME document on both sides
    const plan = planTransfer({ target: doc, sourceIr: doc, certifiedByFieldId: certs });

    expect(plan.transferred, 'a shared tag still blocked its own exact fieldId').toHaveLength(5);
    expect(plan.reproposed).toEqual([]);
    // ⚠️ AND EACH ROW LANDS ON ITS OWN CONTROL. A count is not a pairing —
    // five transfers that cite the wrong sources would satisfy the line above.
    for (const [i, id] of all.entries()) {
      const row = plan.transferred.find((t) => t.fieldId === id);
      expect(row, `no row for ${id}`).toBeDefined();
      expect(row!.fromFieldId, 'a disposition landed on a different control').toBe(id);
      expect(row!.mapping.clinicalConcept).toBe(`concept_${i}`);
    }
    expect(new Set(plan.transferred.map((t) => t.fromFieldId)).size).toBe(5);
  });

  it('⚠️ a NUL inside a w:tag cannot borrow another control identity', () => {
    // ⚠️ THE REGRESSION THE REFUTATION PASS FOUND, kept as a test so the lossy
    // parse cannot come back. `ambiguityKeyFor` used to recover the ambiguity
    // key by splitting the joined MATCH key on NUL and keeping three fields:
    //
    //     match     tag \0 <part> \0 x \0 y \0 <kind>      (tag is "x\0y")
    //     recovered tag \0 <part> \0 x                      <- a DIFFERENT control's key
    //
    // ⚠️ AND THE SIBLING BELOW IS LOAD-BEARING, NOT SCENERY. Without a control
    // whose tag is exactly `x`, the truncated key has count 0, `keyIsUnique` is
    // false and the old code failed CLOSED — so an arm without it passes under
    // BOTH implementations and proves nothing. The pass measured that
    // precondition explicitly; this arm encodes it.
    //
    // Pre-#1087 the per-FIELD rule refused these (it read the real 4-segment
    // key, count 2). The lossy parse made them read as UNIQUE — so this was a
    // regression, and the arm discriminates in that direction.
    const P = 'ttf_' + 'k'.repeat(24);
    const Q = 'ttf_' + 'l'.repeat(24);
    const R = 'ttf_' + 'r'.repeat(24);
    // P and Q genuinely share the NUL-bearing tag; R owns the truncation of it.
    const src = ir([withTag(P, 'x\u0000y', 'A'), withTag(Q, 'x\u0000y', 'B'), withTag(R, 'x', 'Plain')]);
    const certs = new Map([
      [P, certified(P, 'c_p')],
      [Q, certified(Q, 'c_q')],
      [R, certified(R, 'c_r')],
    ]);

    // identical bytes: every exact fieldId carries, and each onto ITSELF.
    const same = planTransfer({ target: src, sourceIr: src, certifiedByFieldId: certs });
    expect(same.transferred).toHaveLength(3);
    for (const row of same.transferred) expect(row.fromFieldId).toBe(row.fieldId);

    // rotated ids: only tags are left. The shared NUL-bearing tag names nobody,
    // so P and Q inherit NOTHING; R's own unique tag still carries.
    const tgt = ir([
      withTag('ttf_' + 'm'.repeat(24), 'x\u0000y', 'A'),
      withTag('ttf_' + 'z'.repeat(24), 'x\u0000y', 'B'),
      withTag('ttf_' + 'n'.repeat(24), 'x', 'Plain'),
    ]);
    const plan = planTransfer({ target: tgt, sourceIr: src, certifiedByFieldId: certs });
    expect(
      plan.transferred.map((t) => t.mapping.clinicalConcept),
      'a NUL-bearing shared tag carried a disposition',
    ).toEqual(['c_r']);
  });

  it('⚠️ a NUL in the PART NAME cannot collide with a tag — the join is INJECTIVE', () => {
    // ⚠️ THE SECOND HALF OF THE SAME CLASS, and the first fix did NOT close it.
    // Removing the lossy PARSE left a lossy JOIN: with a plain delimiter,
    //
    //     (partName "a\u0000b", tag "x")    -> tag \0 a\0b \0 x
    //     (partName "a",     tag "b\u0000x") -> tag \0 a \0 b\0x
    //
    // are BYTE-IDENTICAL. Two controls in different parts with different tags
    // collapse to one key, each unique on its own side, so both uniqueness gates
    // pass and one inherits the other's certified clinical disposition.
    //
    // Measured against the pre-length-prefix code: it TRANSFERRED (1 row,
    // cross-part, arriving certified) where its own parent had refused. The
    // length-prefixed encoding refuses it, and does so for ANY bytes in ANY
    // component rather than borrowing partName's NUL-freedom from another module.
    const S = 'ttf_' + 's'.repeat(24);
    const T = 'ttf_' + 't'.repeat(24);
    const src = ir([field({ fieldId: S, tag: 'x', label: 'A', partName: 'a\u0000b' })]);
    const tgt = ir([field({ fieldId: T, tag: 'b\u0000x', label: 'B', partName: 'a' })]);
    const certs = new Map([[S, certified(S, 'concept_S')]]);

    const plan = planTransfer({ target: tgt, sourceIr: src, certifiedByFieldId: certs });
    expect(
      plan.transferred,
      'a partName NUL collided with a tag and carried a disposition across parts',
    ).toEqual([]);
    expect(plan.reproposed).toEqual([T]);
  });

  // The NUL character, built rather than typed: a literal control character in
  // a source file is invisible in review, and an escape in a template literal is
  // one keystroke away from being a different string.
  const NUL = String.fromCharCode(0);

  it('⚠️ a DIGIT in a part name cannot absorb the tag\'s length prefix — the partName segment is pinned', () => {
    // ⚠️ ROUND THREE: no arm pinned the partName length prefix. Deleting it from
    // that one segment (`tag${b.partName}`, or with only a NUL before it) left
    // the whole suite green, because no fixture partName held a DIGIT, and real
    // OOXML part names do ('word/header1.xml'). With the prefix gone these two
    // collide: (partName 'a3<NUL>', tag 'x') and (partName 'a', tag '1<NUL>x').
    const S = 'ttf_' + 's'.repeat(24);
    const T = 'ttf_' + 't'.repeat(24);
    const src = ir([field({ fieldId: S, tag: `1${NUL}x`, label: 'A', partName: 'a' })]);
    const tgt = ir([field({ fieldId: T, tag: 'x', label: 'B', partName: `a3${NUL}` })]);
    const certs = new Map([[S, certified(S, 'concept_S')]]);

    const plan = planTransfer({ target: tgt, sourceIr: src, certifiedByFieldId: certs });
    expect(
      plan.transferred,
      'a digit-bearing partName absorbed a length prefix and carried a disposition across parts',
    ).toEqual([]);
    expect(plan.reproposed).toEqual([T]);
  });

  it.each([
    // Round three's two counterexamples, each let through by a WEAKER length
    // encoding with the whole suite green. The first needs no NUL anywhere:
    // printable part names the zip path would accept.
    ['a length prefix without its NUL', { partName: '1', tag: 'abcdefghi1z' }, { partName: '11abcdefghi', tag: 'z' }],
    ['a NUL placed before the length', { partName: '1', tag: `abcdefgh${NUL}2zz` }, { partName: `${NUL}12abcdefgh`, tag: 'zz' }],
  ])('⚠️ %s cannot make two parts collide', (_what, s, t) => {
    const S = 'ttf_' + 's'.repeat(24);
    const T = 'ttf_' + 't'.repeat(24);
    const src = ir([field({ fieldId: S, ...s, label: 'A' })]);
    const tgt = ir([field({ fieldId: T, ...t, label: 'B' })]);
    const certs = new Map([[S, certified(S, 'concept_S')]]);

    const plan = planTransfer({ target: tgt, sourceIr: src, certifiedByFieldId: certs });
    expect(plan.transferred).toEqual([]);
    expect(plan.reproposed).toEqual([T]);
  });

  it('⚠️ a field\'s TWO keys encode partName and tag identically — they differ only by the kind', () => {
    // Round three's verifier found a second class inside the first finding: drop
    // the prefix from the MATCH line only and the two keys of ONE field diverge.
    // The ambiguity gates stay satisfied while the lookup runs on the collided
    // match key. Two readers of one identity must never disagree about it —
    // asserted without naming the encoding, so a legitimate change of encoding
    // does not have to touch this arm.
    const suffixes = new Map<string, string>();
    const cases: Array<[string, string, string]> = [
      ['word/document.xml', 'plan', 'narrative_text'],
      [`a3${NUL}`, 'x', 'short_text'],
      ['word/header1.xml', `1${NUL}x`, 'number'],
      ['1', 'abcdefghi1z', 'short_text'],
      ['11abcdefghi', 'z', 'number'],
    ];
    for (const [partName, tag, kind] of cases) {
      const pair = identityKeyPairs(field({ fieldId: 'ttf_' + 'q'.repeat(24), partName, tag, kind, label: 'L' }))[1]!;
      expect(pair.match.startsWith(pair.ambiguity), JSON.stringify([partName, tag])).toBe(true);
      const suffix = pair.match.slice(pair.ambiguity.length);
      const prior = suffixes.get(kind);
      if (prior !== undefined) expect(suffix, `kind ${kind} encoded differently for two fields`).toBe(prior);
      suffixes.set(kind, suffix);
    }
    // POSITIVE CONTROL: different kinds really are distinguished.
    expect(suffixes.size).toBe(3);
    expect(new Set(suffixes.values()).size).toBe(3);
  });

  it('⚠️ the key encoding is INJECTIVE over an alphabet that can confuse a length prefix', () => {
    // ⚠️ ROUND THREE: the previous version of this arm was a FIXTURE — no
    // component held a digit and `kind` never varied, so `${s.length}${s}` (no
    // NUL) passed it while colliding on printable, NUL-free input. This alphabet
    // carries digits, NUL, a space, two-digit lengths, a real part name and both
    // of round three's counterexamples, and the kind varies.
    //
    // ⚠️ THE TAG IS TRIMMED BY DESIGN (an identity is its trimmed tag), so no tag
    // atom carries leading or trailing whitespace — NUL is not whitespace — and
    // none is blank (a blank tag is not an identity at all).
    const parts = [
      '', 'a', '1', NUL, '11', `1${NUL}`, 'a1', `${NUL}1`, `a3${NUL}`,
      `${NUL}12abcdefgh`, ' 12abcdefgh', 'abcdefghi1', '11abcdefghi', 'word/header1.xml',
    ];
    const tags = [
      'a', '1', NUL, '11', `1${NUL}`, 'a1', `${NUL}1`, `1${NUL}x`, 'x', 'z', 'zz',
      'abcdefghi1z', `abcdefgh${NUL}2zz`, '1abcdefghij',
    ];
    const kinds = ['short_text', 'number'];
    // The alphabet itself is sound: no duplicates, no tag the trim would change.
    expect(new Set(parts).size).toBe(parts.length);
    expect(new Set(tags).size).toBe(tags.length);
    for (const t of tags) expect(t.trim(), JSON.stringify(t)).toBe(t);

    const seen = new Map<string, string>();
    let built = 0;
    for (const partName of parts) {
      for (const tag of tags) {
        for (const kind of kinds) {
          const pair = identityKeyPairs(field({ fieldId: 'ttf_' + 'q'.repeat(24), tag, kind, label: 'L', partName }))[1];
          expect(pair, `no tag key for ${JSON.stringify([partName, tag])}`).toBeDefined();
          const keys: Array<[string, string]> = [
            [pair!.match, JSON.stringify(['match', partName, tag, kind])],
            [pair!.ambiguity, JSON.stringify(['ambiguity', partName, tag])],
          ];
          for (const [key, input] of keys) {
            const prior = seen.get(key);
            if (prior !== undefined) {
              expect(prior, `two DISTINCT inputs share the key ${JSON.stringify(key)}`).toBe(input);
            }
            seen.set(key, input);
            built += 1;
          }
        }
      }
    }
    // ⚠️ POSITIVE CONTROL — a loop that built nothing passes every assertion.
    expect(built).toBe(parts.length * tags.length * kinds.length * 2);
    // Every match key distinct; each ambiguity key shared by exactly its kinds.
    expect(seen.size).toBe(parts.length * tags.length * kinds.length + parts.length * tags.length);
  });
});

describe('#274 · the identity keys themselves', () => {
  it('every field offers its fieldId — universal, and exact for identical bytes', () => {
    for (const f of SOURCE.fields) {
      expect(identityKeys(f).some((k) => k.includes(f.fieldId))).toBe(true);
    }
  });

  it('a field WITH a TAG offers a second, edit-surviving identity', () => {
    expect(identityKeys(SOURCE.fields[0]!)).toHaveLength(2);
  });

  it('a field WITHOUT a tag offers only the fieldId — no id and no positional fallback', () => {
    // ⚠️ THE ABSENCE IS THE POINT. A fallback to position is what mis-paired 3
    // of 3 controls on the real document; there is deliberately nothing here to
    // fall back to.
    const anon = field({ fieldId: 'ttf_' + 'x'.repeat(24), tag: null });
    expect(identityKeys(anon)).toHaveLength(1);
  });

  it('⚠️ no identity key mentions path or ordinal', () => {
    // The regression guard, stated as the property rather than as a fixture:
    // if either ever returns, an insert re-pairs the document again.
    const f = field({ fieldId: 'ttf_' + 'y'.repeat(24), path: '/doc/UNIQUEPATH[7]', ordinal: 4242, sdtId: '55' });
    for (const key of identityKeys(f)) {
      expect(key, 'an identity key leaked a POSITION').not.toContain('UNIQUEPATH');
      expect(key, 'an identity key leaked an ORDINAL').not.toContain('4242');
    }
  });
});

describe('#274 · ⚠️ AN AMBIGUOUS KEY TRANSFERS TO NOBODY — the bijection', () => {
  // ══════════════════════════════════════════════════════════════════════════
  // THE FIRST VERSION ASSERTED THIS PROPERTY IN A COMMENT AND DID NOT HAVE IT.
  // "First wins, and a collision never mis-transfers" guarded the SOURCE map;
  // nothing guarded the TARGET side, so two controls sharing a key both claimed
  // the same certified row. Measured before the fix:
  //
  //     "Right leg findings"  <-  venous.reflux.RIGHT
  //     "Left leg findings"   <-  venous.reflux.RIGHT
  //     transferred = 2, distinct source rows consumed = 1
  //
  // A left-leg finding certified to print the right leg's concept.
  // ══════════════════════════════════════════════════════════════════════════
  // ⚠️ `dup` NOW STAMPS A TAG, NOT AN ID. Round four deleted the sdtId path
  // entirely: on the real document only 10 of 80 controls carry an id AND a
  // unique label, and a renumber landing on a same-label neighbour mis-paired
  // 14 of 14. These arms were written to exercise "an identity that survives an
  // edit", and that is now the semantic tag.
  const dup = (fieldId: string, tag: string, label: string, partName?: string) =>
    field({ fieldId, tag, label, ...(partName ? { partName } : {}) });

  it('⚠️ two controls sharing a TAG in the SAME part: NEITHER inherits', () => {
    // ⚠️ SAME LABEL AS WELL AS SAME id — a real copy-paste, which is what
    // actually collides now that the label is part of the identity. An earlier
    // version of this fixture gave the two halves DIFFERENT labels, and the
    // label pairing correctly told them apart; the arm was asserting a
    // conservatism the code no longer needs.
    const src = ir([
      dup('ttf_' + 'a'.repeat(24), '500', 'Leg findings'),
      dup('ttf_' + 'b'.repeat(24), '500', 'Leg findings'),
    ]);
    const certs = new Map([
      ['ttf_' + 'a'.repeat(24), certified('ttf_' + 'a'.repeat(24), 'venous.reflux.RIGHT')],
      ['ttf_' + 'b'.repeat(24), certified('ttf_' + 'b'.repeat(24), 'venous.reflux.LEFT')],
    ]);
    // bytes changed, so every fieldId rotated and only the sdt key could match
    const tgt = ir([
      dup('ttf_' + 'c'.repeat(24), '500', 'Leg findings'),
      dup('ttf_' + 'd'.repeat(24), '500', 'Leg findings'),
    ]);
    const plan = planTransfer({ target: tgt, sourceIr: src, certifiedByFieldId: certs });
    expect(plan.transferred, 'an ambiguous key carried a clinical disposition').toEqual([]);
    expect(plan.reproposed).toHaveLength(2);
  });

  it('⚠️ a BODY control and a LETTERHEAD control sharing a TAG: neither inherits', () => {
    // `w:id` is unique within a PART, not across the package, and the compiler
    // walks body then headers then footers into one field list.
    const src = ir([
      dup('ttf_' + 'e'.repeat(24), '201', 'Clinical impression'),
      dup('ttf_' + 'g'.repeat(24), '201', 'Practice display name', 'word/header1.xml'),
    ]);
    const certs = new Map([
      ['ttf_' + 'e'.repeat(24), certified('ttf_' + 'e'.repeat(24), 'clinical.impression')],
      ['ttf_' + 'g'.repeat(24), certified('ttf_' + 'g'.repeat(24), 'practice.display_name')],
    ]);
    const tgt = ir([
      dup('ttf_' + 'h'.repeat(24), '201', 'Clinical impression'),
      dup('ttf_' + 'i'.repeat(24), '201', 'Practice display name', 'word/header1.xml'),
    ]);
    const plan = planTransfer({ target: tgt, sourceIr: src, certifiedByFieldId: certs });
    const labelOf = new Map(tgt.fields.map((f) => [f.fieldId, f.originalLabel]));
    const wrong = plan.transferred.filter((t) => {
      const l = labelOf.get(t.fieldId);
      return (l === 'Practice display name' && t.mapping.clinicalConcept !== 'practice.display_name')
        || (l === 'Clinical impression' && t.mapping.clinicalConcept !== 'clinical.impression');
    });
    expect(wrong.map((t) => `${labelOf.get(t.fieldId)} <- ${t.mapping.clinicalConcept}`)).toEqual([]);
  });

  it('POSITIVE CONTROL — DISTINCT tags in the same two parts DO transfer', () => {
    // ⚠️ Without this, the two arms above are bought by an implementation that
    // transfers nothing at all whenever a header exists.
    const src = ir([
      dup('ttf_' + 'j'.repeat(24), '201', 'Clinical impression'),
      dup('ttf_' + 'k'.repeat(24), '900', 'Practice display name', 'word/header1.xml'),
    ]);
    const certs = new Map([
      ['ttf_' + 'j'.repeat(24), certified('ttf_' + 'j'.repeat(24), 'clinical.impression')],
      ['ttf_' + 'k'.repeat(24), certified('ttf_' + 'k'.repeat(24), 'practice.display_name')],
    ]);
    const tgt = ir([
      dup('ttf_' + 'l'.repeat(24), '201', 'Clinical impression'),
      dup('ttf_' + 'm'.repeat(24), '900', 'Practice display name', 'word/header1.xml'),
    ]);
    const plan = planTransfer({ target: tgt, sourceIr: src, certifiedByFieldId: certs });
    expect(plan.transferred).toHaveLength(2);
    const byLabel = new Map(
      plan.transferred.map((t) => [tgt.fields.find((f) => f.fieldId === t.fieldId)!.originalLabel, t.mapping.clinicalConcept]),
    );
    expect(byLabel.get('Clinical impression')).toBe('clinical.impression');
    expect(byLabel.get('Practice display name')).toBe('practice.display_name');
  });

  // ══════════════════════════════════════════════════════════════════════════
  // ⚠️ THE THREE GUARDS OVERLAP, SO THE ARMS ABOVE PROVE THE OUTCOME AND NOT
  // EACH MECHANISM — a mutation proof said so, and it was right.
  //
  // Removing target-uniqueness, and separately removing `partName` from the
  // key, each left every arm above GREEN, because source-uniqueness caught the
  // fixtures on its own. Defence in depth is good; arms that cannot tell the
  // layers apart are not, because the next reader deletes one as redundant and
  // nothing goes red.
  //
  // These two arms are constructed so exactly ONE guard stands between them and
  // a mis-transfer.
  // ══════════════════════════════════════════════════════════════════════════

  it('⚠️ ISOLATES TARGET-UNIQUENESS — source unique, target duplicated: NEITHER inherits', () => {
    // The doctor copy-pasted a certified control, so the NEW document has two
    // controls wearing one w:id while the old document had one. Source-
    // uniqueness cannot see this; only the target-side count can.
    const src = ir([dup('ttf_' + 'q'.repeat(24), '800', 'Findings')]);
    const certs = new Map([['ttf_' + 'q'.repeat(24), certified('ttf_' + 'q'.repeat(24), 'the_findings')]]);
    const tgt = ir([
      dup('ttf_' + 'r'.repeat(24), '800', 'Findings'),
      dup('ttf_' + 's'.repeat(24), '800', 'Findings'),
    ]);
    const plan = planTransfer({ target: tgt, sourceIr: src, certifiedByFieldId: certs });
    // ⚠️ NEITHER, not "one of them". Consumed-once alone would let the FIRST in
    // array order inherit and the second re-propose — a clinical disposition
    // assigned by array order is not a decision anybody made.
    expect(
      plan.transferred.map((t) => t.mapping.clinicalConcept),
      'a duplicated control inherited by array order',
    ).toEqual([]);
    expect(plan.reproposed).toHaveLength(2);
  });

  it('⚠️ ISOLATES partName — ids SWAPPED between body and header must not cross', () => {
    // Every key is unique on BOTH sides here, so neither uniqueness guard fires
    // and consumed-once is satisfied. Only `partName` in the key stops the body
    // control inheriting the letterhead's disposition and vice versa.
    const src = ir([
      dup('ttf_' + 't'.repeat(24), '201', 'Clinical impression'),
      dup('ttf_' + 'u'.repeat(24), '999', 'Practice display name', 'word/header1.xml'),
    ]);
    const certs = new Map([
      ['ttf_' + 't'.repeat(24), certified('ttf_' + 't'.repeat(24), 'clinical.impression')],
      ['ttf_' + 'u'.repeat(24), certified('ttf_' + 'u'.repeat(24), 'practice.display_name')],
    ]);
    // the doctor rebuilt the form; Word handed the ids out the other way round
    const tgt = ir([
      dup('ttf_' + 'v'.repeat(24), '999', 'Clinical impression'),
      dup('ttf_' + 'w'.repeat(24), '201', 'Practice display name', 'word/header1.xml'),
    ]);
    const plan = planTransfer({ target: tgt, sourceIr: src, certifiedByFieldId: certs });
    const labelOf = new Map(tgt.fields.map((f) => [f.fieldId, f.originalLabel]));
    const wrong = plan.transferred
      .filter((t) => {
        const l = labelOf.get(t.fieldId);
        return (
          (l === 'Clinical impression' && t.mapping.clinicalConcept !== 'clinical.impression') ||
          (l === 'Practice display name' && t.mapping.clinicalConcept !== 'practice.display_name')
        );
      })
      .map((t) => `${labelOf.get(t.fieldId)} <- ${t.mapping.clinicalConcept}`);
    expect(wrong, 'a disposition crossed between the body and the letterhead').toEqual([]);
  });

  it('⚠️ ROUND THREE/FOUR — a POSITIONAL id renumber transfers NOTHING without a tag', () => {
    // ══════════════════════════════════════════════════════════════════════════
    // The owner's form assigns `sdtId` with `nextId += 1` per control IN
    // DOCUMENT ORDER, so a dropped clause renumbers everything. Round three
    // mis-paired fifteen certified concepts that way; round four then showed
    // that pairing the id with the LABEL does not save it, because the real
    // document has FOURTEEN ADJACENT PAIRS SHARING A LABEL and only 10 of 80
    // controls carry an id AND a unique label.
    //
    // The id path is therefore GONE. These controls carry no tag, so the ONLY
    // correct outcome is that every one re-proposes.
    // ══════════════════════════════════════════════════════════════════════════
    const withId = (fieldId: string, sdtId: string, label: string) =>
      field({ fieldId, sdtId, label });
    const src = ir([
      withId('ttf_' + '1'.repeat(24), '900037', 'exam_neck'),
      withId('ttf_' + '2'.repeat(24), '900038', 'exam_lungs'),
      withId('ttf_' + '3'.repeat(24), '900039', 'exam_cv'),
    ]);
    const certs = new Map([
      ['ttf_' + '1'.repeat(24), certified('ttf_' + '1'.repeat(24), 'CONCEPT::exam_neck')],
      ['ttf_' + '2'.repeat(24), certified('ttf_' + '2'.repeat(24), 'CONCEPT::exam_lungs')],
      ['ttf_' + '3'.repeat(24), certified('ttf_' + '3'.repeat(24), 'CONCEPT::exam_cv')],
    ]);
    const tgt = ir([
      withId('ttf_' + '4'.repeat(24), '900036', 'exam_neck'),
      withId('ttf_' + '5'.repeat(24), '900037', 'exam_lungs'),
      withId('ttf_' + '6'.repeat(24), '900038', 'exam_cv'),
    ]);
    const plan = planTransfer({ target: tgt, sourceIr: src, certifiedByFieldId: certs });
    expect(plan.transferred, 'an id-only match carried a certified disposition').toEqual([]);
    expect(plan.reproposed).toHaveLength(3);
  });

  it('⚠️ AND THE SAME-LABEL NEIGHBOUR CASE — round four, stated directly', () => {
    // Six consecutive controls on the real form read "CLINICAL INDICATIONS:
    // Choose an item.…". Under a renumber, target #2 inherits source #1's id AND
    // its label, so an id+label key matched and mis-paired. With no tag there is
    // now nothing to match on.
    const same = (fieldId: string, sdtId: string) =>
      field({ fieldId, sdtId, label: 'CLINICAL INDICATIONS: Choose an item.' });
    const src = ir([
      same('ttf_' + 'a'.repeat(24), '900007'),
      same('ttf_' + 'b'.repeat(24), '900008'),
    ]);
    const certs = new Map([
      ['ttf_' + 'a'.repeat(24), certified('ttf_' + 'a'.repeat(24), 'aortic_reflux')],
      ['ttf_' + 'b'.repeat(24), certified('ttf_' + 'b'.repeat(24), 'venous_stasis')],
    ]);
    const tgt = ir([
      same('ttf_' + 'c'.repeat(24), '900006'),
      same('ttf_' + 'd'.repeat(24), '900007'),
    ]);
    const plan = planTransfer({ target: tgt, sourceIr: src, certifiedByFieldId: certs });
    expect(
      plan.transferred.map((t) => t.mapping.clinicalConcept),
      'a same-label neighbour inherited a certified clinical concept',
    ).toEqual([]);
  });

  it('⚠️ a SEMANTIC TAG survives a renumber AND a rename — the strongest identity', () => {
    // The owner's generator emits `<w:tag w:val="exam_lungs"/>` for every control
    // it adds, and the compiler extracts it. It was available in round two and
    // DISCARDED on a `tag 1/80` measurement taken from a different document.
    const src = ir([{ ...dup('ttf_' + '7'.repeat(24), '900037', 'Lungs'), rendererBinding: { ...dup('ttf_' + '7'.repeat(24), '900037', 'Lungs').rendererBinding, tag: 'exam_lungs' } } as TemplateField]);
    const certs = new Map([['ttf_' + '7'.repeat(24), certified('ttf_' + '7'.repeat(24), 'CONCEPT::exam_lungs')]]);
    // renumbered AND renamed by the doctor — only the tag still names it
    const tgt = ir([{ ...dup('ttf_' + '8'.repeat(24), '900099', 'Chest examination'), rendererBinding: { ...dup('ttf_' + '8'.repeat(24), '900099', 'Chest examination').rendererBinding, tag: 'exam_lungs' } } as TemplateField]);
    const plan = planTransfer({ target: tgt, sourceIr: src, certifiedByFieldId: certs });
    expect(plan.transferred).toHaveLength(1);
    expect(plan.transferred[0]!.mapping.clinicalConcept).toBe('CONCEPT::exam_lungs');
  });

  it('POSITIVE CONTROL — a stable RANDOM id with a stable label still transfers', () => {
    // ⚠️ Without this, every arm above is bought by an implementation that
    // refuses all sdtId matching outright. `WM IOV Template.docx` carries
    // Word-generated random ids on 28 of 80 controls, and those must keep
    // working across an edit.
    const src = ir([dup('ttf_' + '9'.repeat(24), '1519045110', 'MACHINE')]);
    const certs = new Map([['ttf_' + '9'.repeat(24), certified('ttf_' + '9'.repeat(24), 'device.machine')]]);
    const tgt = ir([dup('ttf_' + 'A'.repeat(24), '1519045110', 'MACHINE')]);
    const plan = planTransfer({ target: tgt, sourceIr: src, certifiedByFieldId: certs });
    expect(plan.transferred).toHaveLength(1);
    expect(plan.transferred[0]!.mapping.clinicalConcept).toBe('device.machine');
  });

  it('⚠️ ROUND FIVE — a repeated TAG is ambiguous even when the two KINDS differ', () => {
    // ══════════════════════════════════════════════════════════════════════════
    // `kind` is CONTENT-DERIVED and MUTABLE (compiler.ts:854-858 reads
    // `isScaffolded(properties, content)` and a label heuristic), so clearing a
    // control's pre-filled sentence re-types it. While `kind` was part of the
    // COUNTED key, two controls sharing one tag produced two DISTINCT keys —
    // each unique — and the bijection never fired.
    //
    // Measured on real bytes with the shipped generator's own `ros_gi_weight`:
    // a ROS alarm-feature clause inherited a DELETED weight MEASUREMENT
    // control's certified disposition, arriving `certified`, while its own was
    // discarded. transferred = 2 where a correct run returns 1.
    // ══════════════════════════════════════════════════════════════════════════
    const tagged = (fieldId: string, tag: string, label: string, kind: string) =>
      field({ fieldId, tag, label, kind });
    const src = ir([
      tagged('ttf_' + 'k'.repeat(24), 'ros_gi_weight', 'The patient denies weight loss', 'narrative_text'),
      tagged('ttf_' + 'l'.repeat(24), 'ros_gi_weight', 'Weight', 'measurement'),
    ]);
    const certs = new Map([
      ['ttf_' + 'k'.repeat(24), certified('ttf_' + 'k'.repeat(24), 'ros.weight_change')],
      ['ttf_' + 'l'.repeat(24), certified('ttf_' + 'l'.repeat(24), 'vitals.body_weight_kg')],
    ]);
    // the doctor deletes the weight field and clears the clause, which re-types
    // the survivor to `measurement` — the shape that used to collide
    const tgt = ir([
      tagged('ttf_' + 'm'.repeat(24), 'ros_gi_weight', 'The patient denies weight loss', 'measurement'),
    ]);
    const plan = planTransfer({ target: tgt, sourceIr: src, certifiedByFieldId: certs });
    expect(
      plan.transferred.map((t) => t.mapping.clinicalConcept),
      'a repeated tag carried a disposition because the two KINDS differed',
    ).toEqual([]);
  });

  it('POSITIVE CONTROL — a UNIQUE tag whose kind is unchanged still transfers', () => {
    // ⚠️ Without this, the arm above is bought by an implementation that stops
    // transferring on tags altogether — which is the only identity left.
    const one = (fieldId: string) =>
      field({ fieldId, tag: 'exam_lungs', label: 'Lungs', kind: 'narrative_text' });
    const src = ir([one('ttf_' + 'n'.repeat(24))]);
    const certs = new Map([['ttf_' + 'n'.repeat(24), certified('ttf_' + 'n'.repeat(24), 'exam.lungs')]]);
    const plan = planTransfer({
      target: ir([one('ttf_' + 'o'.repeat(24))]),
      sourceIr: src,
      certifiedByFieldId: certs,
    });
    expect(plan.transferred).toHaveLength(1);
    expect(plan.transferred[0]!.mapping.clinicalConcept).toBe('exam.lungs');
  });

  it('⚠️ ONE certified row is consumed by AT MOST ONE control', () => {
    // ⚠️ THIS ARM WAS VACUOUS UNTIL 2026-09-09, AND ITS OLD FIXTURE IS WHY IT
    // IS WRITTEN OUT AT LENGTH NOW. It used to give BOTH target controls the
    // tag `700`, so the TARGET-side uniqueness check refused both before the
    // `consumed` guard was ever reached: `transferred` was `[]` and the
    // assertion reduced to `new Set([]).size === [].length` — 0 === 0, true for
    // every possible implementation, including one with no guard at all.
    // Measured: DELETING the `consumed` Set left the whole suite green,
    // 1045/1045. A test that cannot fail is not a test.
    //
    // The shape below actually reaches the guard. Source A carries tag `plan`
    // and IS certified; source B carries tag `zzz` and is not. The two target
    // controls are their ids SWAPPED:
    //
    //   target bbbb/plan  — its own `fid` finds source B, which has no
    //                       certified row, so it falls through to the TAG key
    //                       and legitimately claims source A.
    //   target aaaa/qqq   — its own `fid` finds source A, which is now
    //                       CONSUMED. Only the guard stops it claiming A a
    //                       second time.
    //
    // With the guard: 1 transfer, A consumed once, aaaa re-proposed.
    // Without it:     2 transfers BOTH citing A — two controls wearing one
    //                 clinical meaning, which is the harm the guard exists for.
    const A = 'ttf_' + 'a'.repeat(24);
    const B = 'ttf_' + 'b'.repeat(24);
    const src = ir([dup(A, 'plan', 'Plan'), dup(B, 'zzz', 'Other')]);
    const certs = new Map([[A, certified(A, 'clinical.plan')]]);
    const tgt = ir([dup(B, 'plan', 'Plan'), dup(A, 'qqq', 'Other')]);

    const plan = planTransfer({ target: tgt, sourceIr: src, certifiedByFieldId: certs });

    // ⚠️ THE LENGTH IS ASSERTED FIRST AND ON PURPOSE. Distinctness alone is
    // satisfiable by an empty array, which is exactly how this arm went
    // vacuous the first time.
    expect(plan.transferred, 'the guard-reaching path did not transfer').toHaveLength(1);
    expect(plan.transferred[0]!.fieldId).toBe(B);
    expect(plan.transferred[0]!.fromFieldId).toBe(A);
    expect(plan.transferred[0]!.mapping.clinicalConcept).toBe('clinical.plan');
    // A is spent, so the control that would otherwise claim it is re-proposed.
    expect(plan.reproposed, 'the second claimant was not re-proposed').toContain(A);

    const sources = plan.transferred.map((t) => t.fromFieldId);
    expect(new Set(sources).size, 'a certified row was consumed twice').toBe(sources.length);
  });
});
