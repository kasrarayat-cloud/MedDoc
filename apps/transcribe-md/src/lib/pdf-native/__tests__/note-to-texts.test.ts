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
    const texts = buildPdfFillTexts({
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
  });

  it('omits a section absent from the note (leaves that region blank)', () => {
    const texts = buildPdfFillTexts({
      noteText: '## PROCEDURE:\nColonoscopy.',
      sections: SECTIONS,
      headerFields: [],
      headerCtx: { patientName: null, visitDate: new Date('2026-07-23'), soapText: '' },
    });
    expect(texts.procedure).toBe('Colonoscopy.');
    expect(texts).not.toHaveProperty('recommendations');
  });
});
