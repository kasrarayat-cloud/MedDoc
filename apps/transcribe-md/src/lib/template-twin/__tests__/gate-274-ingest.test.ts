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
import { identityKeys, planTransfer } from '../ingest-plan';

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
  partName?: string;
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
        sdtId: f.rendererBinding.sdtId,
      }),
    ),
  );
}

const SOURCE = ir([
  field({ fieldId: 'ttf_' + 'a'.repeat(24), path: '/doc/sdt[1]', ordinal: 0, label: 'Chief complaint', sdtId: '1001' }),
  field({ fieldId: 'ttf_' + 'c'.repeat(24), path: '/doc/sdt[2]', ordinal: 1, label: 'Age', sdtId: '1002' }),
  field({ fieldId: 'ttf_' + 'd'.repeat(24), path: '/doc/sdt[3]', ordinal: 2, label: 'Plan', sdtId: '1003' }),
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
    field({ fieldId: 'ttf_' + 'n'.repeat(24), path: '/doc/sdt[1]', ordinal: 0, label: 'NEW question', sdtId: '9999' }),
    field({ fieldId: 'ttf_' + 'p'.repeat(24), path: '/doc/sdt[2]', ordinal: 1, label: 'Chief complaint', sdtId: '1001' }),
    field({ fieldId: 'ttf_' + 'q'.repeat(24), path: '/doc/sdt[3]', ordinal: 2, label: 'Age', sdtId: '1002' }),
    field({ fieldId: 'ttf_' + 'r'.repeat(24), path: '/doc/sdt[4]', ordinal: 3, label: 'Plan', sdtId: '1003' }),
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

  it('the three surviving controls DO keep their own dispositions, via sdtId', () => {
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
      field({ fieldId: 'ttf_' + 's'.repeat(24), path: '/doc/sdt[1]', ordinal: 0, label: 'Age', sdtId: '1002' }),
      field({ fieldId: 'ttf_' + 't'.repeat(24), path: '/doc/sdt[2]', ordinal: 1, label: 'Plan', sdtId: '1003' }),
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

  it('⚠️ a control with NO sdtId re-proposes rather than guessing', () => {
    // 52 of the reference document's 80 controls carry no sdtId. They lose
    // their certification on an edit, and that is the RULED-SAFE direction: a
    // re-proposal is a question to the doctor, a mis-transfer is a wrong answer
    // presented as certified.
    const noIdSource = ir([field({ fieldId: 'ttf_' + 'u'.repeat(24), path: '/doc/sdt[1]', ordinal: 0, label: 'X', sdtId: null })]);
    const noIdTarget = ir([field({ fieldId: 'ttf_' + 'v'.repeat(24), path: '/doc/sdt[2]', ordinal: 1, label: 'X', sdtId: null })]);
    const certs = new Map([['ttf_' + 'u'.repeat(24), certified('ttf_' + 'u'.repeat(24), 'some_concept')]]);
    const plan = planTransfer({ target: noIdTarget, sourceIr: noIdSource, certifiedByFieldId: certs });
    expect(plan.transferred).toEqual([]);
    expect(plan.reproposed).toEqual(['ttf_' + 'v'.repeat(24)]);
  });

  it('⚠️ a kind CHANGE on the same sdtId does not inherit — same name, different question', () => {
    const changed = ir([
      field({ fieldId: 'ttf_' + 'w'.repeat(24), path: '/doc/sdt[1]', ordinal: 0, label: 'Age', sdtId: '1002', kind: 'single_select' }),
    ]);
    const plan = planTransfer({ target: changed, sourceIr: SOURCE, certifiedByFieldId: CERTIFIED });
    expect(plan.transferred).toEqual([]);
    expect(plan.reproposed).toHaveLength(1);
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

describe('#274 · the identity keys themselves', () => {
  it('every field offers its fieldId — universal, and exact for identical bytes', () => {
    for (const f of SOURCE.fields) {
      expect(identityKeys(f).some((k) => k.includes(f.fieldId))).toBe(true);
    }
  });

  it('a field WITH an sdtId offers a second, edit-surviving identity', () => {
    expect(identityKeys(SOURCE.fields[0]!)).toHaveLength(2);
  });

  it('a field WITHOUT one offers only the fieldId — no positional fallback', () => {
    // ⚠️ THE ABSENCE IS THE POINT. A fallback to position is what mis-paired 3
    // of 3 controls on the real document; there is deliberately nothing here to
    // fall back to.
    const anon = field({ fieldId: 'ttf_' + 'x'.repeat(24), sdtId: null });
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
  const dup = (fieldId: string, sdtId: string, label: string, partName?: string) =>
    field({ fieldId, sdtId, label, ...(partName ? { partName } : {}) });

  it('⚠️ two controls sharing a w:id in the SAME part: NEITHER inherits', () => {
    const src = ir([
      dup('ttf_' + 'a'.repeat(24), '500', 'Right leg findings'),
      dup('ttf_' + 'b'.repeat(24), '500', 'Left leg findings'),
    ]);
    const certs = new Map([
      ['ttf_' + 'a'.repeat(24), certified('ttf_' + 'a'.repeat(24), 'venous.reflux.RIGHT')],
      ['ttf_' + 'b'.repeat(24), certified('ttf_' + 'b'.repeat(24), 'venous.reflux.LEFT')],
    ]);
    // bytes changed, so every fieldId rotated and only the sdt key could match
    const tgt = ir([
      dup('ttf_' + 'c'.repeat(24), '500', 'Right leg findings'),
      dup('ttf_' + 'd'.repeat(24), '500', 'Left leg findings'),
    ]);
    const plan = planTransfer({ target: tgt, sourceIr: src, certifiedByFieldId: certs });
    expect(plan.transferred, 'an ambiguous key carried a clinical disposition').toEqual([]);
    expect(plan.reproposed).toHaveLength(2);
  });

  it('⚠️ a BODY control and a LETTERHEAD control sharing a w:id: neither inherits', () => {
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

  it('POSITIVE CONTROL — DISTINCT ids in the same two parts DO transfer', () => {
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
      dup('ttf_' + 's'.repeat(24), '800', 'Findings (copy)'),
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

  it('⚠️ ONE certified row is consumed by AT MOST ONE control', () => {
    // The property stated directly, rather than through a fixture: no two
    // transferred rows may cite the same source.
    const src = ir([dup('ttf_' + 'n'.repeat(24), '700', 'Only one')]);
    const certs = new Map([['ttf_' + 'n'.repeat(24), certified('ttf_' + 'n'.repeat(24), 'the_concept')]]);
    const tgt = ir([dup('ttf_' + 'o'.repeat(24), '700', 'Only one'), dup('ttf_' + 'p'.repeat(24), '700', 'Copy')]);
    const plan = planTransfer({ target: tgt, sourceIr: src, certifiedByFieldId: certs });
    const sources = plan.transferred.map((t) => t.fromFieldId);
    expect(new Set(sources).size, 'a certified row was consumed twice').toBe(sources.length);
  });
});
