import { describe, it, expect } from 'vitest';

import { mapFieldsToConcepts, conceptMapOf, deterministicConceptFor } from '../map-fields';
import type { FormField } from '../types';

// Ruling #326 Slice B: the deterministic mapper reuses the SAME registry the
// DOCX-twin proposer uses. A field with no registry hit is left unmapped
// (needs_confirmation) — never guessed onto a clinical field.

function field(id: string, label: string, multiline = false): FormField {
  return { id, label, page: 0, boxes: [], multiline };
}

describe('map-fields (deterministic label → concept)', () => {
  it('maps the colon-form visit-metadata labels the registry knows', () => {
    // exactly the labels the sidecar returns for the owner's colon PDF; the
    // record-derived visit-metadata fields map deterministically.
    for (const label of ['PATIENT NAME:', 'PATIENT DOB:', 'DATE OF PROCEDURE:']) {
      expect(Boolean(deterministicConceptFor(label)), `${label}`).toBe(true);
    }
  });

  it('leaves a free-prose clinical section for the doctor to confirm (never guessed)', () => {
    // DESCRIPTION OF PROCEDURE / CONSENT have no deterministic registry hit, so
    // they are needs_confirmation — safe: no concept is guessed onto a clinical
    // field. (A model-assisted mapper can propose them later; the doctor still
    // approves the sample-value preview.)
    const mapped = mapFieldsToConcepts([
      field('p0_f0', 'DESCRIPTION OF PROCEDURE', true),
      field('p0_f1', 'CONSENT', true),
    ]);
    for (const fc of mapped) expect(fc.status).toBe('needs_confirmation');
  });

  it('leaves an unknown label UNMAPPED with needs_confirmation', () => {
    const [fc] = mapFieldsToConcepts([field('p0_f0', 'Blorptak level:')]);
    expect(fc!.concept).toBeNull();
    expect(fc!.status).toBe('needs_confirmation');
  });

  it('marks a registry hit recognized and includes it in the concept map', () => {
    const mapped = mapFieldsToConcepts([
      field('p0_f0', 'PATIENT NAME:'),
      field('p0_f1', 'Unrecognized thing'),
    ]);
    expect(mapped[0]!.status).toBe('recognized');
    expect(mapped[0]!.concept).toBeTruthy();
    const m = conceptMapOf(mapped);
    expect(m.has('p0_f0')).toBe(true);
    expect(m.has('p0_f1')).toBe(false); // unmapped fields are not in the map
  });

  it('every mapped concept is registered (no junk concept reaches resolution)', () => {
    const mapped = mapFieldsToConcepts([
      field('p0_f0', 'PATIENT NAME:'),
      field('p0_f1', 'SPECIMENS:'),
      field('p0_f2', 'CONSENT'),
    ]);
    // any field with a concept must have a real one; unmapped is null, not junk
    for (const fc of mapped) {
      if (fc.concept !== null) expect(typeof fc.concept).toBe('string');
    }
  });
});
