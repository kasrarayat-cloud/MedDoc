import { describe, it, expect } from 'vitest';

import { EncounterFactSchema, type EncounterFact } from '@/lib/template-twin/ir';
import { fillFromFacts } from '../fill-from-facts';
import { deriveDetectedFormValues } from '../derive-values';
import type { StoredDetectedField } from '../detected-form-store';

// Ruling #326 Slice B, owner decision 2026-09-16 — a clinical-concept box fills
// from the PROJECTED FACTS through the ruled resolver (tier 1), NOT the crude
// note-heading split. The load-bearing behaviour: a fact-covered box is governed
// by the ruled logic and NEVER falls through to the note-split, so a dictated
// denial is respected instead of being overwritten by raw note prose.

function factBox(id: string, concept: string, label = concept): StoredDetectedField {
  return { id, label, page: 0, boxes: [], multiline: false, concept, sourceType: 'extraction', headerKey: null };
}
function metaBox(id: string, headerKey: string, label: string): StoredDetectedField {
  return { id, label, page: 0, boxes: [], multiline: false, concept: 'visit_metadata.x', sourceType: 'visit_metadata', headerKey };
}

function fact(concept: string, value: string, polarity: EncounterFact['polarity']): EncounterFact {
  return EncounterFactSchema.parse({
    factId: `ttfact_${concept.replace(/[^a-f0-9]/g, '0').padEnd(24, '0').slice(0, 24)}`,
    sourceType: 'encounter_evidence',
    concept,
    value,
    polarity,
    temporality: 'current',
    experiencer: 'patient',
    laterality: 'not_applicable',
    number: null,
    unit: null,
    speaker: null,
    sourceTranscriptOffsets: null,
    audioTimestampSeconds: null,
    evidenceAnchorIds: ['anchor-1'],
    evidenceQuote: 'evidence quote for the self-test',
    quality: { asr: 'high', evidence: 'direct' },
  });
}

const DATE = new Date('2026-03-04T00:00:00.000Z');

describe('fillFromFacts (tier 1 — ruled resolver)', () => {
  it('fills a clinical-concept box from an affirmed fact', () => {
    const { values, factCovered } = fillFromFacts(
      [factBox('b0', 'procedure.description')],
      [fact('procedure.description', 'Colonoscopy to the cecum, adequate prep.', 'affirmed')],
      { allowUncertified: true },
    );
    expect(factCovered.has('b0')).toBe(true);
    expect(values.get('b0')).toMatch(/colonoscopy to the cecum/i);
  });

  it('marks a concept with a candidate fact as fact-covered even when DENIED', () => {
    // A denied fact still COVERS the concept — the ruled resolver decides the
    // outcome (blank or a denial phrase); the box must not fall to the note-split.
    const { factCovered } = fillFromFacts(
      [factBox('b0', 'procedure.findings')],
      [fact('procedure.findings', 'polyps', 'denied')],
      { allowUncertified: true },
    );
    expect(factCovered.has('b0')).toBe(true);
  });

  it('does NOT cover a concept that has no matching fact', () => {
    const { factCovered, values } = fillFromFacts(
      [factBox('b0', 'procedure.findings')],
      [fact('procedure.description', 'something else', 'affirmed')],
      { allowUncertified: true },
    );
    expect(factCovered.has('b0')).toBe(false);
    expect(values.has('b0')).toBe(false);
  });
});

describe('deriveDetectedFormValues (3-tier orchestrator)', () => {
  it('a fact-covered box is NOT overwritten by the note-heading split', () => {
    // The note has a `## FINDINGS` heading with prose, AND a denied finding fact.
    // The box is fact-covered → the ruled resolver governs it; the raw note prose
    // must NOT reach the box (the denial would otherwise be overwritten).
    const box = factBox('b0', 'procedure.findings', 'FINDINGS');
    const { values } = deriveDetectedFormValues({
      fields: [box],
      facts: [fact('procedure.findings', 'polyps', 'denied')],
      noteCtx: {
        patientName: null,
        visitDate: DATE,
        noteText: '## FINDINGS\nRAW NOTE PROSE THAT MUST NOT REACH THE BOX.',
      },
      allowUncertified: false,
    });
    expect(values.get('b0')).not.toBe('RAW NOTE PROSE THAT MUST NOT REACH THE BOX.');
  });

  it('a section box with NO facts fills from the note-heading split (tier 2)', () => {
    const box = factBox('b0', 'procedure.narrative', 'OPERATIVE NARRATIVE');
    const { values } = deriveDetectedFormValues({
      fields: [box],
      facts: [], // no facts → not fact-covered → tier-2
      noteCtx: {
        patientName: null,
        visitDate: DATE,
        noteText: '## OPERATIVE NARRATIVE\nThe scope was advanced to the cecum.',
      },
      allowUncertified: false,
    });
    expect(values.get('b0')).toBe('The scope was advanced to the cecum.');
  });

  it('a metadata box fills from the record (tier 3), a policy-blank one stays blank', () => {
    const { values } = deriveDetectedFormValues({
      fields: [metaBox('h0', 'patient_name', 'PATIENT NAME:'), metaBox('h1', 'patient_dob', 'PATIENT DOB:')],
      facts: [],
      noteCtx: { patientName: 'Jane Q. Public', visitDate: DATE, noteText: '' },
      allowUncertified: false,
    });
    expect(values.get('h0')).toBe('Jane Q. Public');
    expect(values.has('h1')).toBe(false); // policy blank
  });
});
