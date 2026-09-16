import { describe, it, expect } from 'vitest';

import { fillFromNote, headerKeyForConcept } from '../fill-from-note';
import { fieldExpectedToFill, buildSyntheticDetectedNote } from '../certify-detected-form';
import type { StoredDetectedField } from '../detected-form-store';

// Ruling #326 Slice B — the DETECTED-form value source is the precedented
// note-split + header-fields path (NOT a fabricated DOCX IR). This pins the
// clinical behaviour: a body box fills from the matching note heading; a
// record-derived metadata box fills from the record; a policy-blank metadata box
// (DOB/ID/age) stays blank and is NOT a fill failure; an unmatched note section
// is carried as an addendum, never dropped.

function field(
  id: string,
  label: string,
  opts: { concept?: string | null; headerKey?: string | null } = {},
): StoredDetectedField {
  return {
    id,
    label,
    page: 0,
    boxes: [],
    multiline: false,
    concept: opts.concept ?? null,
    sourceType: 'extraction',
    headerKey: opts.headerKey ?? null,
  };
}

const DATE = new Date('2026-03-04T00:00:00.000Z');

describe('fillFromNote (detected-form value source)', () => {
  it('fills a body section from the matching note heading', () => {
    const fields = [field('p0_f0', 'DESCRIPTION OF PROCEDURE')];
    const { values } = fillFromNote(fields, {
      patientName: null,
      visitDate: DATE,
      noteText: '## DESCRIPTION OF PROCEDURE\nColonoscopy to the cecum.',
    });
    expect(values.get('p0_f0')).toBe('Colonoscopy to the cecum.');
  });

  it('fills a record-derived metadata box (patient name) from the record', () => {
    const fields = [field('p0_h0', 'PATIENT NAME:', { headerKey: 'patient_name' })];
    const { values } = fillFromNote(fields, {
      patientName: 'Jane Q. Public',
      visitDate: DATE,
      noteText: '## Something else\nbody',
    });
    expect(values.get('p0_h0')).toBe('Jane Q. Public');
  });

  it('fills date-of-service from the visit date', () => {
    const fields = [field('p0_h1', 'DATE OF PROCEDURE:', { headerKey: 'date_of_surgery' })];
    const { values } = fillFromNote(fields, {
      patientName: null,
      visitDate: DATE,
      noteText: '',
    });
    expect(values.get('p0_h1')).toBe('2026-03-04');
  });

  it('leaves a policy-blank metadata box (DOB) blank — NOT a fill failure', () => {
    const dob = field('p0_h2', 'PATIENT DOB:', { headerKey: 'patient_dob' });
    const { values } = fillFromNote([dob], { patientName: 'Jane', visitDate: DATE, noteText: '' });
    expect(values.has('p0_h2')).toBe(false);
    // and it is classified as NOT-expected-to-fill, so certify does not require it.
    expect(fieldExpectedToFill(dob)).toBe(false);
  });

  it('carries an unmatched note section to addenda — never dropped', () => {
    const fields = [field('p0_f0', 'DESCRIPTION OF PROCEDURE')];
    const { values, addenda } = fillFromNote(fields, {
      patientName: null,
      visitDate: DATE,
      noteText:
        '## DESCRIPTION OF PROCEDURE\nColonoscopy.\n\n## COMPLICATIONS\nNone encountered.',
    });
    expect(values.get('p0_f0')).toBe('Colonoscopy.');
    // COMPLICATIONS matches no detected field → it must survive as an addendum.
    expect(addenda.some((a) => /complications/i.test(a.label))).toBe(true);
  });

  it('two boxes on the same canonical key do not overwrite each other', () => {
    // A form with two date lines both mapping to date_of_surgery: each field id
    // gets its own value (the per-field resolveHeaderFields call, not a shared map).
    const fields = [
      field('p0_h0', 'DATE OF PROCEDURE:', { headerKey: 'date_of_surgery' }),
      field('p0_h1', 'DATE OF SERVICE:', { headerKey: 'date_of_surgery' }),
    ];
    const { values } = fillFromNote(fields, { patientName: null, visitDate: DATE, noteText: '' });
    expect(values.get('p0_h0')).toBe('2026-03-04');
    expect(values.get('p0_h1')).toBe('2026-03-04');
  });
});

describe('headerKeyForConcept', () => {
  it('maps visit-metadata concepts to canonical header keys, body concepts to null', () => {
    expect(headerKeyForConcept('visit_metadata.patient_name')).toBe('patient_name');
    expect(headerKeyForConcept('visit_metadata.date_of_service')).toBe('date_of_surgery');
    expect(headerKeyForConcept('procedure.surgeon')).toBe('surgeon');
    expect(headerKeyForConcept('visit_metadata.date_of_birth')).toBe('patient_dob');
    // a free-prose body concept is not a header field
    expect(headerKeyForConcept('procedure.description')).toBeNull();
    expect(headerKeyForConcept(null)).toBeNull();
  });
});

describe('buildSyntheticDetectedNote', () => {
  it('carries the surgeon line (so metadata fills) and NO `## <label>` headings', () => {
    // Certify covers every clinical box via a synthetic FACT (tier 1), so the note
    // needs no headings — a heading would match no section and become a spurious
    // addendum continuation page that breaks the fidelity check.
    const note = buildSyntheticDetectedNote();
    expect(note).toMatch(/Operating surgeon: Dr\. Synthetic Example/);
    expect(note).not.toMatch(/^##\s/m);
    // clearly labeled synthetic — no patient identifiers
    expect(note.toLowerCase()).toMatch(/synthetic/);
  });
});
