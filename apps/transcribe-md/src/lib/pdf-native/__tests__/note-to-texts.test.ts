import { describe, expect, it } from 'vitest';
import { buildPdfFillTexts } from '../note-to-texts';
import type { NoteTemplateHeaderField } from '@/worker/note-templates/system-default-template';

const SECTIONS = [
  { key: 'procedure', label: 'PROCEDURE:' },
  { key: 'preop', label: 'PREOPERATIVE DIAGNOSIS:' },
  { key: 'recommendations', label: 'RECOMMENDATIONS:' },
];
const HEADER: NoteTemplateHeaderField[] = [
  { key: 'patient_name', label: 'PATIENT NAME:', order: 1 },
  { key: 'patient_dob', label: 'PATIENT DOB:', order: 2 },
  { key: 'date_of_surgery', label: 'DATE OF SURGERY:', order: 3 },
  { key: 'surgeon', label: 'SURGEON:', order: 4 },
];

const NOTE = `## PROCEDURE:
Screening colonoscopy with polypectomy.

## PREOPERATIVE DIAGNOSIS:
_[All AI-drafted content for this section was set aside for your review — see the suggestions below and adopt before signing.]_

## RECOMMENDATIONS:
- Follow up for pathology in one week.
- Surveillance colonoscopy in five years.`;

describe('buildPdfFillTexts', () => {
  it('splits the note by section headings + fills header values (GOAL-8 rules)', () => {
    const { texts, addenda } = buildPdfFillTexts({
      noteText: NOTE,
      sections: SECTIONS,
      headerFields: HEADER,
      headerCtx: {
        patientName: 'KUK',
        visitDate: new Date('2026-07-23T12:00:00Z'),
        soapText: `${NOTE}\nThe colonoscopy was performed by Dr. Shabatian.`,
      },
    });
    // Sections: matched by heading; bullets stripped; set-aside → omitted.
    expect(texts.procedure).toBe('Screening colonoscopy with polypectomy.');
    expect(texts.recommendations).toContain('Follow up for pathology in one week.');
    expect(texts.recommendations).not.toContain('- '); // bullets stripped
    expect(texts).not.toHaveProperty('preop'); // set-aside → blank → omitted
    // Header fields: NAME + DATE deterministic, SURGEON from note; DOB blank → omitted.
    expect(texts.patient_name).toBe('KUK');
    expect(texts.date_of_surgery).toBe('2026-07-23');
    expect(texts.surgeon).toBe('Dr. Shabatian');
    expect(texts).not.toHaveProperty('patient_dob');
    // Every note heading maps to a form label → no addenda.
    expect(addenda).toEqual([]);
  });

  it('omits a section absent from the note (leaves that region blank)', () => {
    const { texts } = buildPdfFillTexts({
      noteText: '## PROCEDURE:\nColonoscopy.',
      sections: SECTIONS,
      headerFields: [],
      headerCtx: { patientName: null, visitDate: new Date('2026-07-23'), soapText: '' },
    });
    expect(texts.procedure).toBe('Colonoscopy.');
    expect(texts).not.toHaveProperty('recommendations');
  });

  it('carries a note section with NO matching form label into addenda (hybrid note)', () => {
    // The note has FINDINGS + IMPRESSION headings the op-note form has no field
    // for — they must NOT be dropped; they flow to the addendum page.
    const hybrid = `## PROCEDURE:
Screening colonoscopy.

## FINDINGS:
Two 4 mm polyps in the sigmoid colon, removed.

## IMPRESSION:
Tubular adenomas; surveillance in 5 years.`;
    const { texts, addenda } = buildPdfFillTexts({
      noteText: hybrid,
      sections: SECTIONS,
      headerFields: HEADER,
      headerCtx: { patientName: 'KUK', visitDate: new Date('2026-07-23'), soapText: hybrid },
    });
    expect(texts.procedure).toBe('Screening colonoscopy.');
    const labels = addenda.map((a) => a.label);
    expect(labels).toEqual(['FINDINGS', 'IMPRESSION']);
    expect(addenda[0].text).toContain('sigmoid colon');
    expect(addenda[1].text).toContain('surveillance in 5 years');
  });

  it('two note headings that normalize to the same key BOTH survive (no last-write-wins drop)', () => {
    // A signed note with a duplicate/case-variant heading the form has NO field
    // for — both bodies must reach the addendum page, neither silently dropped.
    const note = `## PROCEDURE:
Colonoscopy.

## Impression
Bilateral GSV reflux; recommend ablation.

## IMPRESSION
Addendum: SSV reflux 2.8s on the right.`;
    const { texts, addenda } = buildPdfFillTexts({
      noteText: note,
      sections: SECTIONS,
      headerFields: HEADER,
      headerCtx: { patientName: 'KUK', visitDate: new Date('2026-07-23'), soapText: note },
    });
    expect(texts.procedure).toBe('Colonoscopy.');
    const impressions = addenda.filter((a) => a.label.toLowerCase() === 'impression');
    expect(impressions).toHaveLength(2);
    expect(impressions[0].text).toContain('Bilateral GSV reflux');
    expect(impressions[1].text).toContain('SSV reflux 2.8s');
  });

  it('duplicate headings that DO match a section concatenate into the region (never dropped)', () => {
    const note = `## RECOMMENDATIONS:
Follow up in one week.

## RECOMMENDATIONS:
Surveillance colonoscopy in five years.`;
    const { texts } = buildPdfFillTexts({
      noteText: note,
      sections: SECTIONS,
      headerFields: [],
      headerCtx: { patientName: null, visitDate: new Date('2026-07-23'), soapText: '' },
    });
    expect(texts.recommendations).toContain('Follow up in one week.');
    expect(texts.recommendations).toContain('Surveillance colonoscopy in five years.');
  });

  it('a note heading naming an EMPTY header field is preserved as an addendum (not swallowed)', () => {
    // PATIENT DOB yields no value (blank) — a note section under that heading must
    // NOT be silently dropped just because a header field shares its label.
    const note = `## PROCEDURE:
Colonoscopy.

## PATIENT DOB
Unable to verify DOB at intake; confirm with front desk.`;
    const { addenda } = buildPdfFillTexts({
      noteText: note,
      sections: SECTIONS,
      headerFields: HEADER, // patient_dob resolves to '' (no DOB in ctx)
      headerCtx: { patientName: 'KUK', visitDate: new Date('2026-07-23'), soapText: note },
    });
    expect(addenda.some((a) => /Unable to verify DOB/.test(a.text))).toBe(true);
  });

  it('a set-aside off-form section produces no addendum (only real content carries)', () => {
    const note = `## PROCEDURE:
Colonoscopy.

## FINDINGS:
_[All AI-drafted content for this section was set aside for your review — see the suggestions below and adopt before signing.]_`;
    const { addenda } = buildPdfFillTexts({
      noteText: note,
      sections: SECTIONS,
      headerFields: [],
      headerCtx: { patientName: null, visitDate: new Date('2026-07-23'), soapText: '' },
    });
    expect(addenda).toEqual([]);
  });
});
