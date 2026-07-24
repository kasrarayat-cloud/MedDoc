// ============================================================================
// Header-field fill for the styled export (feat/template-header-fields).
// Deterministic fills — NAME/DATE from the visit record, SURGEON from the
// dictated note, DOB/ID blank unless dictated. Never AI.
// ============================================================================
import { describe, expect, it } from 'vitest';

import {
  resolveHeaderFields,
  extractSurgeonFromNote,
  extractSurgeonFromDictation,
  coerceHeaderFields,
} from '../visit-export';
import type { NoteTemplateHeaderField } from '@/worker/note-templates/system-default-template';

const OP_FIELDS: NoteTemplateHeaderField[] = [
  { key: 'patient_name', label: 'PATIENT NAME', order: 1 },
  { key: 'patient_dob', label: 'PATIENT DOB', order: 2 },
  { key: 'patient_id', label: 'PATIENT ID #', order: 3 },
  { key: 'date_of_surgery', label: 'DATE OF SURGERY', order: 4 },
  { key: 'surgeon', label: 'SURGEON', order: 5 },
];

describe('extractSurgeonFromNote', () => {
  it('extracts an explicitly-attributed surgeon (several phrasings)', () => {
    expect(extractSurgeonFromNote('Colonoscopy performed by Dr. Shabatian.')).toBe('Dr. Shabatian');
    expect(extractSurgeonFromNote('SURGEON: Dr. Shabatian')).toBe('Dr. Shabatian');
    expect(extractSurgeonFromNote('The operating surgeon was Dr. Shabatian.')).toBe('Dr. Shabatian');
    expect(extractSurgeonFromNote('Proceduralist: Dr. Ana Reyes-Lopez performed the exam.')).toBe(
      'Dr. Ana Reyes-Lopez'
    );
  });

  it('handles "performed <word> by" phrasing', () => {
    expect(extractSurgeonFromNote('Colonoscopy performed today by Dr. Shabatian.')).toBe(
      'Dr. Shabatian'
    );
  });

  it('stops the name at the sentence period — does not swallow the next word (prod-smoke bug)', () => {
    expect(
      extractSurgeonFromNote(
        'The colonoscopy was performed by Dr. Shabatian. The scope was advanced to the cecum.'
      )
    ).toBe('Dr. Shabatian');
  });

  it('returns null when no surgeon is clearly stated (→ blank field, never guessed)', () => {
    expect(extractSurgeonFromNote('Patient tolerated the procedure well.')).toBeNull();
    // A consulting/referring physician is NOT the surgeon → not extracted.
    expect(extractSurgeonFromNote('Referred by Dr. Smith for evaluation.')).toBeNull();
  });

  it('does NOT grab a referring / consulting / bare-mention surgeon (wrong-physician guard)', () => {
    expect(extractSurgeonFromNote('The referring surgeon, Dr. Smith, was consulted.')).toBeNull();
    expect(extractSurgeonFromNote('Consulting surgeon Dr. Jones did not operate.')).toBeNull();
    // The patient's OWN name/occupation must never land in the surgeon field.
    expect(
      extractSurgeonFromNote('The patient is a surgeon, Dr. Jane Patient, with chest pain.')
    ).toBeNull();
  });
});

describe('resolveHeaderFields', () => {
  const visitDate = new Date('2026-07-23T15:00:00Z');

  it('fills NAME + DATE from the visit record, SURGEON from the note; DOB/ID blank', () => {
    const out = resolveHeaderFields(OP_FIELDS, {
      patientName: 'KUK',
      visitDate,
      soapText: '## DESCRIPTION OF PROCEDURE:\nColonoscopy performed by Dr. Shabatian.',
    });
    expect(out).toEqual([
      { label: 'PATIENT NAME', value: 'KUK' },
      { label: 'PATIENT DOB', value: '' },
      { label: 'PATIENT ID #', value: '' },
      { label: 'DATE OF SURGERY', value: '2026-07-23' },
      { label: 'SURGEON', value: 'Dr. Shabatian' },
    ]);
  });

  it('leaves SURGEON blank when the note does not attribute one (honest blank)', () => {
    const out = resolveHeaderFields(OP_FIELDS, {
      patientName: 'KUK',
      visitDate,
      soapText: 'Colonoscopy completed without complication.',
    });
    expect(out.find((f) => f.label === 'SURGEON')?.value).toBe('');
  });

  it('never infers DOB or PATIENT ID even if numbers appear in the note', () => {
    const out = resolveHeaderFields(OP_FIELDS, {
      patientName: 'KUK',
      visitDate,
      soapText: 'DOB reportedly 01/02/1970; MRN 556677 discussed.',
    });
    expect(out.find((f) => f.label === 'PATIENT DOB')?.value).toBe('');
    expect(out.find((f) => f.label === 'PATIENT ID #')?.value).toBe('');
  });

  it('preserves template order and returns [] for no header fields', () => {
    expect(resolveHeaderFields(null, { patientName: 'X', visitDate, soapText: '' })).toEqual([]);
    expect(resolveHeaderFields([], { patientName: 'X', visitDate, soapText: '' })).toEqual([]);
  });
});

describe('coerceHeaderFields', () => {
  it('shape-guards raw JSONB, dropping malformed entries', () => {
    expect(
      coerceHeaderFields([
        { key: 'surgeon', label: 'SURGEON', order: 1 },
        { key: 'patient_name' }, // missing label/order → dropped
        'garbage',
        null,
      ])
    ).toEqual([{ key: 'surgeon', label: 'SURGEON', order: 1 }]);
    expect(coerceHeaderFields(null)).toEqual([]);
    expect(coerceHeaderFields(undefined)).toEqual([]);
  });

  it('DEFENSE-IN-DEPTH: drops a stored label that looks like it carries data (digits/long/many-word)', () => {
    // A malformed/tampered row where a patient value sits in the label must NOT
    // render — the render seam re-validates rather than trusting the DB.
    expect(
      coerceHeaderFields([
        { key: 'patient_name', label: 'John Q. Public 01/02/1970', order: 1 }, // has digits
        { key: 'patient_id', label: 'MR-556677', order: 2 }, // has digits
        { key: 'surgeon', label: 'this is a long free text sentence that is clearly not a label', order: 3 },
        { key: 'patient_name', label: 'PATIENT NAME', order: 4 }, // clean → kept
      ])
    ).toEqual([{ key: 'patient_name', label: 'PATIENT NAME', order: 4 }]);
  });
});

describe('extractSurgeonFromDictation (dictation fallback for the surgeon field)', () => {
  it('captures "Surgeon is Doctor Enayati" (spelled-out title, no colon) → Dr. Enayati', () => {
    expect(extractSurgeonFromDictation('Operative note. Surgeon is Doctor Enayati. Procedure: colonoscopy.'))
      .toBe('Dr. Enayati');
  });

  it('captures "Surgeon: Dr. Shabatian" and "surgeon was Dr. Kim"', () => {
    expect(extractSurgeonFromDictation('Surgeon: Dr. Shabatian.')).toBe('Dr. Shabatian');
    expect(extractSurgeonFromDictation('The surgeon was Dr. Kim, assisted by a resident.')).toBe('Dr. Kim');
  });

  it('prefers the OPERATING surgeon over a referring one (WARN-4)', () => {
    expect(
      extractSurgeonFromDictation('Referring surgeon was Dr. Smith; operating surgeon was Dr. Lee.')
    ).toBe('Dr. Lee');
    // A lone referring/consulting attribution → no operating surgeon → null.
    expect(extractSurgeonFromDictation('Referring surgeon: Dr. Smith.')).toBeNull();
    expect(extractSurgeonFromDictation('The consulting surgeon is Dr. Jones.')).toBeNull();
  });

  it('never yields a name from "surgeon is the resident" / no attribution / empty', () => {
    expect(extractSurgeonFromDictation('Surgeon is the resident on call.')).toBeNull();
    expect(extractSurgeonFromDictation('Patient is a 61-year-old female for colonoscopy.')).toBeNull();
    expect(extractSurgeonFromDictation('')).toBeNull();
    expect(extractSurgeonFromDictation(null)).toBeNull();
  });

  it('resolveHeaderFields fills SURGEON from the dictation when the note omits it (the TOM fix)', () => {
    const out = resolveHeaderFields(OP_FIELDS, {
      patientName: 'TOM',
      visitDate: new Date('2026-07-23'),
      soapText: '## PROCEDURE:\nColonoscopy.', // note DROPPED the surgeon line
      dictationText: 'Surgeon is Doctor Enayati. Procedure performed: colonoscopy.',
    });
    expect(out.find((f) => f.label === 'SURGEON')?.value).toBe('Dr. Enayati');
  });

  it('prefers an operating-surgeon line in the NOTE over the dictation', () => {
    const out = resolveHeaderFields(OP_FIELDS, {
      patientName: 'X',
      visitDate: new Date('2026-07-23'),
      soapText: '## PROCEDURE:\nSleeve. Surgeon: Dr. Shabatian.',
      dictationText: 'Surgeon is Doctor Someone.',
    });
    expect(out.find((f) => f.label === 'SURGEON')?.value).toBe('Dr. Shabatian');
  });
});
