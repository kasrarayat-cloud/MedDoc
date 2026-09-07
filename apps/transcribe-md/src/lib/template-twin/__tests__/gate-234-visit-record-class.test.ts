// ============================================================================
// #234 — THE `visit_record` FACT CLASS.
// ----------------------------------------------------------------------------
// A value taken from the patient record did not come out of the doctor's mouth.
// The whole fill path is built on cited EncounterFacts carrying an evidence
// quote, so a record-derived value that borrowed `encounter_evidence` makes the
// FROZEN MANIFEST assert, in the doctor's voice, something he never said.
//
// ⚠️ THAT IS NOT HYPOTHETICAL. `withProcedureDateFact` — the one existing
// record-derived fill — stamped `encounter_evidence` on the visit date for as
// long as this class did not exist. The class is not credible while its one
// precedent keeps lying, so the precedent moves onto it here rather than being
// grandfathered.
// ============================================================================
import { describe, expect, it, vi } from 'vitest';

vi.mock('@meddoc/db', () => ({ default: {} }));
vi.mock('@/lib/audit', () => ({ logAudit: vi.fn() }));

import { EncounterFactSchema } from '../ir';
import { withProcedureDateFact } from '../procedure-date';
import { assertNoRecordDerivedFacts } from '../synthetic-test';

const FIELD_ID = `ttf_${'b'.repeat(24)}`;

function fact(overrides: Record<string, unknown> = {}) {
  return EncounterFactSchema.parse({
    factId: `ttfact_${'c'.repeat(24)}`,
    concept: 'chief_complaint',
    value: 'chest pain',
    polarity: 'affirmed',
    temporality: 'current',
    experiencer: 'patient',
    laterality: 'not_applicable',
    number: null,
    unit: null,
    speaker: 'Clinician',
    sourceTranscriptOffsets: null,
    audioTimestampSeconds: null,
    evidenceAnchorIds: ['a1'],
    evidenceQuote: 'the doctor said so',
    quality: { asr: 'unknown', evidence: 'direct' },
    ...overrides,
  });
}

describe('#234 — the class exists and is distinct', () => {
  it('the fact schema admits `visit_record`', () => {
    expect(fact({ sourceType: 'visit_record' }).sourceType).toBe('visit_record');
  });

  it('⚠️ NON-VACUITY: the four original classes still parse, and a made-up one does NOT', () => {
    // Without this, the arm above is satisfied by an enum that was replaced
    // with a free string.
    for (const s of ['encounter_evidence', 'approved_practice_default', 'verified_note_selection', 'clinician_correction']) {
      expect(fact({ sourceType: s }).sourceType).toBe(s);
    }
    expect(() => fact({ sourceType: 'from_the_ether' })).toThrow();
  });
});

describe('#234 — the one existing record-derived fill stops claiming it was dictated', () => {
  const field = {
    fieldId: FIELD_ID,
    kind: 'date',
    originalLabel: 'Date of Procedure',
    allowedOptions: [],
    rowPrototype: false,
  } as unknown as Parameters<typeof withProcedureDateFact>[0]['fields'][number];
  const mapping = {
    fieldId: FIELD_ID,
    clinicalConcept: 'procedure_date',
    sourceType: 'extraction',
    expectedDataType: 'date',
    polarityBehavior: 'value_only',
    temporality: 'current',
    approvedSynonyms: [],
    required: false,
    blankPolicy: 'blank',
    unknownPolicy: 'blank',
    practiceDefault: null,
    status: 'certified',
  } as unknown as Parameters<typeof withProcedureDateFact>[0]['mappings'][number];

  it('⚠️ the injected visit date is `visit_record`, NEVER `encounter_evidence`', () => {
    const out = withProcedureDateFact({
      fields: [field],
      mappings: [mapping],
      facts: [],
      visitDate: '2026-09-07',
    });
    const injected = out.filter((f) => f.speaker === 'Visit metadata');
    expect(injected, 'the fixture did not reach the injector at all').toHaveLength(1);
    expect(injected[0]!.sourceType).toBe('visit_record');
    // ⚠️ THE ARM THAT MATTERS — the old value must be gone, not merely joined.
    expect(injected[0]!.sourceType).not.toBe('encounter_evidence');
  });

  it('⚠️ NON-VACUITY: it still injects nothing when there is no visit date', () => {
    const out = withProcedureDateFact({
      fields: [field], mappings: [mapping], facts: [], visitDate: null,
    });
    expect(out).toHaveLength(0);
  });

  it('and a REAL dictated fact still wins over the record', () => {
    const spoken = fact({ concept: 'procedure_date', value: '2026-01-01' });
    const out = withProcedureDateFact({
      fields: [field], mappings: [mapping], facts: [spoken], visitDate: '2026-09-07',
    });
    expect(out.filter((f) => f.speaker === 'Visit metadata')).toHaveLength(0);
  });
});

describe('#234 — a record-derived fact can never reach a CERTIFICATION manifest', () => {
  it('the guard refuses one, and names it without copying its value', () => {
    let caught: unknown;
    try {
      assertNoRecordDerivedFacts([fact({ sourceType: 'visit_record', value: 'Jane Alvarez' })]);
    } catch (e) { caught = e; }
    expect(caught, 'a record-derived fact was ALLOWED into the certification test').toBeTruthy();
    const msg = String((caught as Error).message);
    expect(msg).toMatch(/record-derived/i);
    // ⚠️ THE REFUSAL ITSELF MUST NOT LEAK THE VALUE IT REFUSED.
    expect(msg).not.toContain('Jane Alvarez');
    expect(JSON.stringify((caught as { details?: unknown }).details ?? {})).not.toContain('Jane Alvarez');
  });

  it('⚠️ NON-VACUITY: ordinary dictated facts pass straight through', () => {
    // Without this the guard is satisfied by one that refuses everything.
    expect(() => assertNoRecordDerivedFacts([fact(), fact({ sourceType: 'clinician_correction' })])).not.toThrow();
    expect(() => assertNoRecordDerivedFacts([])).not.toThrow();
  });
});
