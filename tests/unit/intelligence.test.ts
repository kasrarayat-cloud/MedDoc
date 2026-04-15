// ============================================================================
// Realtime intelligence helpers — unit tests
// ----------------------------------------------------------------------------
// Pure-function tests for the two synchronous helpers in
// src/lib/realtime/intelligence.ts:
//   - enrichNoteLine  (semantic hint inference)
//   - buildPatientVocabPrimer  (Whisper vocab hint)
//
// buildClinicalTrajectory + fetchRecentAiActions hit OpenAI/Prisma and
// are covered by the E2E suite; skipping here to keep these tests fast
// and deterministic.
// ============================================================================

import { describe, it, expect } from 'vitest';

import {
  buildPatientVocabPrimer,
  enrichNoteLine,
} from '@/lib/realtime/intelligence';
import type { ClinicalNoteView } from '@/lib/data/clinical-notes';
import type { PatientView } from '@/lib/data/patients';

function makeNote(overrides: Partial<ClinicalNoteView> = {}): ClinicalNoteView {
  return {
    id: 'note_1',
    patientId: 'pt_1',
    title: 'Clinical Note',
    procedureType: null,
    category: 'CLINICAL_NOTE',
    content: '',
    status: 'DRAFT',
    createdAt: '2026-04-15T10:00:00.000Z',
    createdById: 'user_1',
    ...overrides,
  };
}

function makePatient(overrides: Partial<PatientView> = {}): PatientView {
  return {
    id: 'pt_1',
    firstName: 'Sarah',
    lastName: 'Mitchell',
    birthYear: 1978,
    mrn: 'MRN-1',
    status: 'ACTIVE',
    tags: [],
    assignedDoctor: 'Dr. Smith',
    lastVisit: '2026-04-15T10:00:00.000Z',
    createdAt: '2026-01-01T00:00:00.000Z',
    briefHistory: [],
    recentNotes: [],
    files: [],
    ...overrides,
  };
}

describe('enrichNoteLine', () => {
  it('tags a lumbar epidural note as back injection', () => {
    const note = makeNote({
      title: 'LESI L4-L5 procedure',
      content: 'Bilateral L4 lumbar epidural steroid injection under fluoro',
    });
    const line = enrichNoteLine(note);
    expect(line).toMatch(/hint=".*lumbar epidural.*"/);
    expect(line).toMatch(/hint=".*low back.*"/);
  });

  it('tags a cervical injection distinctly from lumbar', () => {
    const lumbar = enrichNoteLine(makeNote({ title: 'LESI', content: 'lumbar epidural injection' }));
    const cervical = enrichNoteLine(makeNote({ title: 'CESI', content: 'cervical epidural injection' }));
    expect(lumbar).toMatch(/lumbar/);
    expect(lumbar).not.toMatch(/cervical epidural/);
    expect(cervical).toMatch(/cervical epidural/);
  });

  it('picks up opioid rx + imaging signals', () => {
    const note = makeNote({
      content: 'MRI showed disc protrusion. Norco 5/325 prescribed.',
    });
    const line = enrichNoteLine(note);
    expect(line).toMatch(/opioid rx/);
    expect(line).toMatch(/imaging/);
  });

  it('omits the hint attribute entirely when no signals fire', () => {
    const note = makeNote({
      title: 'Routine check',
      content: 'Routine appointment today, nothing specific.',
    });
    const line = enrichNoteLine(note);
    expect(line).not.toMatch(/hint="/);
    expect(line).toMatch(/id="note_1"/);
    expect(line).toMatch(/title="Routine check"/);
  });
});

describe('buildPatientVocabPrimer', () => {
  it('includes the patient first and last name', () => {
    const primer = buildPatientVocabPrimer(
      makePatient({ firstName: 'Hagop', lastName: 'Hagopian' }),
      [],
      []
    );
    expect(primer).toContain('Hagop');
    expect(primer).toContain('Hagopian');
  });

  it('returns empty string when the patient has no proper nouns', () => {
    // firstName/lastName are always added to the pool, so to get an
    // empty primer we need ALL text fields blank.
    const blank: PatientView = {
      ...makePatient(),
      firstName: '',
      lastName: '',
      pharmacyName: undefined,
      city: undefined,
      briefHistory: [],
    };
    const primer = buildPatientVocabPrimer(blank, [], []);
    expect(primer).toBe('');
  });

  it('extracts capitalized proper nouns from note content', () => {
    const note = makeNote({
      content: 'Patient reports allergy to Penicillin. Referred to Ortho by Chen.',
    });
    const primer = buildPatientVocabPrimer(makePatient(), [note], []);
    expect(primer).toContain('Penicillin');
    expect(primer).toContain('Ortho');
    expect(primer).toContain('Chen');
  });

  it('filters out generic stopwords', () => {
    const note = makeNote({
      content: 'The Patient has Today visited the Clinic for a Follow up.',
    });
    const primer = buildPatientVocabPrimer(makePatient(), [note], []);
    // Words on the stoplist shouldn't make it into the primer.
    expect(primer).not.toContain('Patient,');
    expect(primer).not.toContain('Today,');
    expect(primer).not.toContain('Clinic,');
  });

  it('includes pharmacy proper nouns', () => {
    const primer = buildPatientVocabPrimer(
      makePatient({ pharmacyName: 'Walgreens on Ventura Boulevard' }),
      [],
      []
    );
    expect(primer).toContain('Walgreens');
    expect(primer).toContain('Ventura');
  });
});
