// Regression: styled export rendered a partial "## PATIENT SUMMARY" note section
// ABOVE the complete dedicated patientSummary block (duplicate). The note section
// is stripped when the complete field is present.
import { describe, expect, it, vi } from 'vitest';

vi.mock('@meddoc/db', () => ({ default: {} }));

import { stripNotePatientSummarySection } from '../visit-export-server';

describe('stripNotePatientSummarySection', () => {
  it('strips a trailing PATIENT SUMMARY section (the prod shape)', () => {
    const note = [
      '## IMPRESSION',
      'Right GSV reflux positive.',
      '',
      '## PROCEDURES / E&M',
      '[not documented]',
      '',
      '## PATIENT SUMMARY',
      '',
      '**What we talked about today**',
      'You came in because your right leg has been painful.',
      '',
      '**What we found**',
    ].join('\n');
    const out = stripNotePatientSummarySection(note);
    expect(out).not.toMatch(/patient summary/i);
    expect(out).toContain('## PROCEDURES / E&M');
    expect(out).toContain('## IMPRESSION');
    expect(out.endsWith('[not documented]')).toBe(true);
  });

  it('strips a MID-note PATIENT SUMMARY section but keeps the section after it', () => {
    const note = [
      '## FINDINGS',
      'x',
      '## PATIENT SUMMARY',
      'partial summary',
      '## IMPRESSION',
      'y',
    ].join('\n');
    const out = stripNotePatientSummarySection(note);
    expect(out).not.toMatch(/patient summary/i);
    expect(out).toContain('## FINDINGS');
    expect(out).toContain('## IMPRESSION');
    expect(out).toContain('\ny');
  });

  it('is a no-op when the note has no PATIENT SUMMARY section', () => {
    const note = '## FINDINGS\nx\n\n## IMPRESSION\ny';
    expect(stripNotePatientSummarySection(note)).toBe(note.trimEnd());
  });

  it('case-insensitive on the heading, and does not strip a mere mention of the words', () => {
    const note = '## FINDINGS\nWe reviewed the patient summary verbally.\n\n## Patient Summary\ngone';
    const out = stripNotePatientSummarySection(note);
    expect(out).toContain('reviewed the patient summary verbally'); // body mention kept
    expect(out).not.toMatch(/##\s+patient summary/i); // heading section removed
    expect(out).not.toContain('gone');
  });
});
