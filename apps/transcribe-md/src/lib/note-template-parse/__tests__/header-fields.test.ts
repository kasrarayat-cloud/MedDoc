// ============================================================================
// Header/short-field capture (feat/template-header-fields).
// ============================================================================
import { describe, expect, it } from 'vitest';

import { canonicalHeaderKey, extractHeaderFields, deriveHeaderFieldsFromRun } from '../header-fields';

const OP_SECTIONS = [
  { label: 'PROCEDURE:' },
  { label: 'PREOPERATIVE DIAGNOSIS:' },
  { label: 'DESCRIPTION OF PROCEDURE:' },
  { label: 'RECOMMENDATIONS:' },
];

describe('deriveHeaderFieldsFromRun (flat-form PDF flattened to one line)', () => {
  it('captures the 5 op-note header fields from a single-line form (the tom fix)', () => {
    // pdfToText flattens the colon form to one run; the line-based path can't find
    // a boundary, so this run-aware derivation must recover the header block.
    const oneLine =
      'OPERATIVE NOTE PATIENT NAME: PATIENT DOB: PATIENT ID #: DATE OF SURGERY: SURGEON: PROCEDURE: PREOPERATIVE DIAGNOSIS: DESCRIPTION OF PROCEDURE: RECOMMENDATIONS: Electronically Signed - DD: DT:';
    const fields = deriveHeaderFieldsFromRun(oneLine, OP_SECTIONS);
    expect(fields.map((f) => f.key)).toEqual([
      'patient_name',
      'patient_dob',
      'patient_id',
      'date_of_surgery',
      'surgeon',
    ]);
    // Full labels retained (not the bare trailing word).
    expect(fields.find((f) => f.key === 'patient_name')?.label).toBe('PATIENT NAME');
    expect(fields.find((f) => f.key === 'date_of_surgery')?.label).toBe('DATE OF SURGERY');
  });

  it('stops at the first section label — form footer labels (DD:/DT:) are not captured', () => {
    const oneLine = 'PATIENT NAME: SURGEON: PROCEDURE: RECOMMENDATIONS: DD: DT:';
    const fields = deriveHeaderFieldsFromRun(oneLine, OP_SECTIONS);
    expect(fields.map((f) => f.key)).toEqual(['patient_name', 'surgeon']);
  });

  it('no header labels before the first section → empty (never invents)', () => {
    expect(deriveHeaderFieldsFromRun('PROCEDURE: RECOMMENDATIONS:', OP_SECTIONS)).toEqual([]);
  });

  it('captures "DATE OF PROCEDURE" header without truncating at the PROCEDURE section (WARN-2)', () => {
    // "DATE OF PROCEDURE" (header) contains the word "PROCEDURE" (a section) — the
    // header must be matched longest-first, NOT truncated by the section label.
    const oneLine = 'PATIENT NAME: DATE OF PROCEDURE: SURGEON: PROCEDURE: RECOMMENDATIONS:';
    const fields = deriveHeaderFieldsFromRun(oneLine, OP_SECTIONS);
    expect(fields.map((f) => f.key)).toEqual(['patient_name', 'date_of_surgery', 'surgeon']);
  });
});

describe('canonicalHeaderKey', () => {
  it('maps the operative-note header labels to canonical keys (colon-tolerant)', () => {
    expect(canonicalHeaderKey('PATIENT NAME:')).toBe('patient_name');
    expect(canonicalHeaderKey('Patient Name')).toBe('patient_name');
    expect(canonicalHeaderKey('PATIENT DOB:')).toBe('patient_dob');
    expect(canonicalHeaderKey('Date of Birth')).toBe('patient_dob');
    expect(canonicalHeaderKey('PATIENT ID #:')).toBe('patient_id');
    expect(canonicalHeaderKey('MRN')).toBe('patient_id');
    expect(canonicalHeaderKey('DATE OF SURGERY:')).toBe('date_of_surgery');
    expect(canonicalHeaderKey('Date of Procedure')).toBe('date_of_surgery');
    expect(canonicalHeaderKey('SURGEON:')).toBe('surgeon');
    expect(canonicalHeaderKey('Operating Surgeon')).toBe('surgeon');
  });

  it('returns null for clinic letterhead / unrelated labels (no noise captured)', () => {
    expect(canonicalHeaderKey('Referring Clinic Phone')).toBeNull();
    expect(canonicalHeaderKey('Fax')).toBeNull();
    expect(canonicalHeaderKey('Address')).toBeNull();
    expect(canonicalHeaderKey('PROCEDURE')).toBeNull();
  });
});

const OP_NOTE = `COMMANDHEALTH SURGICAL CENTER
OPERATIVE NOTE

PATIENT NAME: John Q. Public
PATIENT DOB: 01/02/1970
PATIENT ID #: MR-556677
DATE OF SURGERY: ___________
SURGEON: Dr. Shabatian
Referring Clinic Phone: 555-123-4567

PROCEDURE:
Colonoscopy.

PREOPERATIVE DIAGNOSIS:
Screening.

DESCRIPTION OF PROCEDURE:
The scope was advanced to the cecum.`;

const SECTIONS = [
  { label: 'PROCEDURE:' },
  { label: 'PREOPERATIVE DIAGNOSIS:' },
  { label: 'DESCRIPTION OF PROCEDURE:' },
];

describe('extractHeaderFields', () => {
  it('captures the labeled header fields in order, labels only (never the patient value)', () => {
    const fields = extractHeaderFields(OP_NOTE, SECTIONS);
    expect(fields).toEqual([
      { key: 'patient_name', label: 'PATIENT NAME', order: 1 },
      { key: 'patient_dob', label: 'PATIENT DOB', order: 2 },
      { key: 'patient_id', label: 'PATIENT ID #', order: 3 },
      { key: 'date_of_surgery', label: 'DATE OF SURGERY', order: 4 },
      { key: 'surgeon', label: 'SURGEON', order: 5 },
    ]);
  });

  it('never captures a patient VALUE — no field label carries the filled data', () => {
    const fields = extractHeaderFields(OP_NOTE, SECTIONS);
    const joined = JSON.stringify(fields);
    expect(joined).not.toMatch(/John|Public|1970|556677|Shabatian/);
  });

  it('ignores clinic letterhead (phone/fax) — only patient/procedure fields captured', () => {
    const fields = extractHeaderFields(OP_NOTE, SECTIONS);
    expect(fields.map((f) => f.key)).not.toContain('patient_id_phone');
    expect(fields.every((f) => f.key !== null)).toBe(true);
    // No phone/fax field leaked in.
    expect(JSON.stringify(fields)).not.toMatch(/phone|fax/i);
  });

  it('only scans the header region — a "SURGEON:" mention in the body is not a field', () => {
    const bodyOnly = `PROCEDURE:\nColonoscopy performed. SURGEON: Dr. Body.`;
    expect(extractHeaderFields(bodyOnly, [{ label: 'PROCEDURE:' }])).toEqual([]);
  });

  it('returns [] when there is no header block', () => {
    expect(extractHeaderFields('PROCEDURE:\nColonoscopy.', [{ label: 'PROCEDURE:' }])).toEqual([]);
  });

  it('does NOT scan the whole note when no clinical heading matches (boundary=length)', () => {
    // The section label matches nothing → firstClinicalHeadingIndex returns
    // lines.length; the header region must be empty, NOT the whole note, so a
    // body "SURGEON:" line is never captured as a field.
    const note = `SURGEON: Dr. Body\nSome prose that mentions PATIENT NAME: nobody.`;
    expect(extractHeaderFields(note, [{ label: 'NONEXISTENT HEADING:' }])).toEqual([]);
  });

  it('handles underscore fill-blanks (LABEL ______) as well as colons', () => {
    const note = `PATIENT NAME ____________________\nSURGEON _______________\n\nPROCEDURE:\nx`;
    const fields = extractHeaderFields(note, [{ label: 'PROCEDURE:' }]);
    expect(fields.map((f) => f.key)).toEqual(['patient_name', 'surgeon']);
  });
});
