// ============================================================================
// UPLOAD-AND-CERTIFIED · S3 — transfer-by-identity on re-upload, the two pure
// safety guarantees (the DB compose is exercised by the QA walk + adversarial
// pass; the fieldId|tag MATCHER itself is proved in gate-274-ingest).
//
//   1. planReuploadTransfer NEVER transfers a record-derived (visit_metadata)
//      row (#247) — it is dropped before the #274 matcher runs, so it is always
//      reproposed and confirmed. Clinical rows transfer by fieldId (identical
//      bytes) or tag (edited bytes rotate every fieldId), bijection respected.
//   2. planAutoConfirm KEEPS an already-certified (transferred) row and only
//      class-decides the reproposed remainder — so a re-upload does not re-open a
//      settled disposition, and the confirm rule still applies to what is new.
// ============================================================================
import { describe, expect, it } from 'vitest';

import { planAutoConfirm } from '../auto-certify-eligibility';
import { planReuploadTransfer } from '../ingest-plan';
import type { TemplateTwinWorkspace } from '../client-types';
import type { SemanticMapping, TemplateDocIR, TemplateField } from '../ir';

function field(over: {
  fieldId: string;
  path?: string;
  ordinal?: number;
  kind?: string;
  label?: string;
  tag?: string | null;
  criticality?: string;
}): TemplateField {
  return {
    fieldId: over.fieldId,
    kind: (over.kind ?? 'short_text') as TemplateField['kind'],
    originalLabel: over.label ?? 'A control',
    labelSource: 'sdt_alias',
    displayOrder: over.ordinal ?? 0,
    detectionStatus: 'recognized',
    allowedOptions: [],
    required: false,
    unknownPolicy: 'blank',
    clinicallyMaterial: true,
    criticality: (over.criticality ?? 'routine') as TemplateField['criticality'],
    rendererBinding: {
      partName: 'word/document.xml',
      bindingType: 'sdt',
      path: over.path ?? '/w:document[1]/w:body[1]/w:sdt[1]',
      ordinal: over.ordinal ?? 0,
      sdtId: null,
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

const ir = (fields: TemplateField[]): TemplateDocIR => ({ fields }) as unknown as TemplateDocIR;

function mapping(fieldId: string, sourceType: string, concept: string | null): SemanticMapping {
  return {
    fieldId,
    sourceType,
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

const A = 'ttf_' + 'a'.repeat(24); // clinical (extraction)
const M = 'ttf_' + 'c'.repeat(24); // visit_metadata (record-derived)
const P = 'ttf_' + 'd'.repeat(24); // clinical (extraction)

const SOURCE = ir([
  field({ fieldId: A, path: '/doc/sdt[1]', ordinal: 0, label: 'Diagnosis', tag: 't_dx' }),
  field({ fieldId: M, path: '/doc/sdt[2]', ordinal: 1, label: 'Patient name', tag: 't_name' }),
  field({ fieldId: P, path: '/doc/sdt[3]', ordinal: 2, label: 'Plan', tag: 't_plan' }),
]);
const CERTIFIED = new Map<string, SemanticMapping>([
  [A, mapping(A, 'extraction', 'preoperative_diagnosis')],
  [M, mapping(M, 'visit_metadata', 'visit_metadata.patient_name')],
  [P, mapping(P, 'extraction', 'plan')],
]);

describe('S3 — planReuploadTransfer: #247 record-derived exclusion + #274 matching', () => {
  it('⚠️ NEVER transfers a visit_metadata row, even on byte-identical re-upload', () => {
    const plan = planReuploadTransfer({ target: SOURCE, sourceIr: SOURCE, certified: CERTIFIED });
    const transferredIds = plan.transferred.map((t) => t.fieldId).sort();
    // The two clinical rows carry; the visit_metadata row is NOT transferred.
    expect(transferredIds).toEqual([A, P].sort());
    expect(transferredIds).not.toContain(M);
    // And it is reproposed, so it lands in the confirm list.
    expect(plan.reproposed).toContain(M);
  });

  it('transfers clinical rows by TAG when an edit rotates every fieldId; visit_metadata still excluded', () => {
    // Edited re-upload: same tags, brand-new fieldIds (whole-package sha rotates all).
    const rotated = ir([
      field({ fieldId: 'ttf_' + 'e'.repeat(24), path: '/doc/sdt[1]', ordinal: 0, label: 'Diagnosis', tag: 't_dx' }),
      field({ fieldId: 'ttf_' + 'f'.repeat(24), path: '/doc/sdt[2]', ordinal: 1, label: 'Patient name', tag: 't_name' }),
      field({ fieldId: 'ttf_' + '9'.repeat(24), path: '/doc/sdt[3]', ordinal: 2, label: 'Plan', tag: 't_plan' }),
    ]);
    const plan = planReuploadTransfer({ target: rotated, sourceIr: SOURCE, certified: CERTIFIED });
    const transferredConcepts = plan.transferred.map((t) => t.mapping.clinicalConcept).sort();
    // Clinical dispositions carry by tag onto the new fieldIds; the name (visit_metadata) does NOT.
    expect(transferredConcepts).toEqual(['plan', 'preoperative_diagnosis']);
    expect(plan.transferred.map((t) => t.mapping.sourceType)).not.toContain('visit_metadata');
  });

  it('⚠️ CLINICAL — a record-derived CONCEPT is excluded even when sourceType is "extraction"', () => {
    // The fallback proposer (model outage) assigns a record-derived concept to a
    // date/short_text control while leaving sourceType 'extraction'. The exclusion
    // must key on the CONCEPT, not only the sourceType, or a patient DOB would
    // transfer-as-certified with no human (adversarial pass, 2026-09-14).
    const dob = mapping(M, 'extraction', 'visit_metadata.date_of_birth'); // record-derived CONCEPT, extraction sourceType
    const clinicalMap = new Map<string, SemanticMapping>([
      [A, mapping(A, 'extraction', 'preoperative_diagnosis')],
      [M, dob],
    ]);
    const plan = planReuploadTransfer({ target: SOURCE, sourceIr: SOURCE, certified: clinicalMap });
    const transferredIds = plan.transferred.map((t) => t.fieldId);
    expect(transferredIds).toEqual([A]); // the clinical row carries
    expect(transferredIds).not.toContain(M); // the record-derived DOB does NOT, despite sourceType 'extraction'
    expect(plan.reproposed).toContain(M);
  });

  it('the record-derived concept check is NORMALIZED (trim/case) like the model path', () => {
    // clinicalConcept is a free string in the schema; a mis-cased/padded record
    // concept must still be excluded so the two readers cannot drift.
    const misCased = new Map<string, SemanticMapping>([
      [A, mapping(A, 'extraction', 'preoperative_diagnosis')],
      [M, mapping(M, 'extraction', '  Procedure.Surgeon ')], // record-derived, padded + mixed case
    ]);
    const plan = planReuploadTransfer({ target: SOURCE, sourceIr: SOURCE, certified: misCased });
    expect(plan.transferred.map((t) => t.fieldId)).toEqual([A]);
    expect(plan.reproposed).toContain(M);
  });

  it('a shared tag is ambiguous → the #274 bijection transfers NEITHER member', () => {
    const src = ir([
      field({ fieldId: A, path: '/doc/sdt[1]', ordinal: 0, label: 'Dx 1', tag: 't_dup' }),
      field({ fieldId: P, path: '/doc/sdt[2]', ordinal: 1, label: 'Dx 2', tag: 't_dup' }),
    ]);
    const cert = new Map<string, SemanticMapping>([
      [A, mapping(A, 'extraction', 'preoperative_diagnosis')],
      [P, mapping(P, 'extraction', 'plan')],
    ]);
    const rotated = ir([
      field({ fieldId: 'ttf_' + 'e'.repeat(24), path: '/doc/sdt[1]', ordinal: 0, label: 'Dx 1', tag: 't_dup' }),
      field({ fieldId: 'ttf_' + 'f'.repeat(24), path: '/doc/sdt[2]', ordinal: 1, label: 'Dx 2', tag: 't_dup' }),
    ]);
    const plan = planReuploadTransfer({ target: rotated, sourceIr: src, certified: cert });
    expect(plan.transferred).toHaveLength(0); // ambiguous tag pairs nothing
    expect(plan.reproposed).toHaveLength(2);
  });
});

describe('S3 — planAutoConfirm keeps a transferred (certified) row, decides only the remainder', () => {
  function ws(fields: Array<{ field: TemplateField; mapping: SemanticMapping }>): TemplateTwinWorkspace {
    return { fields } as unknown as TemplateTwinWorkspace;
  }

  it('a transferred certified row is kept untouched; reproposed rows follow the class rules', () => {
    const carried = { ...mapping(A, 'extraction', 'preoperative_diagnosis'), status: 'certified' as const };
    const freshClinical = { ...mapping(P, 'extraction', 'plan'), status: 'needs_confirmation' as const };
    const freshMeta = { ...mapping(M, 'visit_metadata', 'visit_metadata.patient_name'), status: 'needs_confirmation' as const };
    const out = planAutoConfirm(
      ws([
        { field: field({ fieldId: A, label: 'Diagnosis' }), mapping: carried },
        { field: field({ fieldId: P, label: 'Plan' }), mapping: freshClinical },
        { field: field({ fieldId: M, label: 'Patient name' }), mapping: freshMeta },
      ]),
    );
    const byId = Object.fromEntries(out.mappings.map((m) => [m.fieldId, m]));
    // Transferred row: kept exactly, still certified, never re-decided.
    expect(byId[A]).toBe(carried);
    expect(byId[A].status).toBe('certified');
    // Reproposed clinical row: auto-confirmed to certified.
    expect(byId[P].status).toBe('certified');
    // Reproposed visit_metadata row: declined for the doctor to confirm (#247).
    expect(byId[M].status).toBe('needs_confirmation');
    expect(out.declined.map((d) => d.label)).toContain('Patient name');
  });
})
