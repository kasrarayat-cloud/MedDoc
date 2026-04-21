import { describe, it, expect } from 'vitest';
import {
  Document,
  Packer,
  Paragraph,
  TextRun,
} from 'docx';
import mammoth from 'mammoth';

import { fillTemplate } from './template-docx-generator';

/** Build a minimal .docx containing the given body text — used to
 *  generate realistic docxtemplater input for each test case. */
async function buildTestDocx(lines: string[]): Promise<Buffer> {
  const doc = new Document({
    sections: [
      {
        children: lines.map(
          (text) =>
            new Paragraph({
              children: [new TextRun({ text })],
            })
        ),
      },
    ],
  });
  return (await Packer.toBuffer(doc)) as unknown as Buffer;
}

async function extractText(buffer: Buffer): Promise<string> {
  const result = await mammoth.extractRawText({ buffer });
  return result.value.trim();
}

describe('fillTemplate', () => {
  it('replaces a single {{token}} with its content', async () => {
    const template = await buildTestDocx(['HPI: {{hpi}}']);
    const filled = fillTemplate(template, { hpi: 'Patient presents with cough.' });
    const text = await extractText(filled);
    expect(text).toBe('HPI: Patient presents with cough.');
  });

  it('replaces multiple tokens in document order', async () => {
    const template = await buildTestDocx([
      'CC: {{chief_complaint}}',
      'HPI: {{hpi}}',
      'Plan: {{plan}}',
    ]);
    const filled = fillTemplate(template, {
      chief_complaint: 'Cough',
      hpi: '3 days of productive cough',
      plan: 'Start amoxicillin, return in 1 week',
    });
    const text = await extractText(filled);
    expect(text).toContain('CC: Cough');
    expect(text).toContain('HPI: 3 days of productive cough');
    expect(text).toContain('Plan: Start amoxicillin, return in 1 week');
  });

  it('renders empty for tokens missing from content (nullGetter hook)', async () => {
    const template = await buildTestDocx([
      'HPI: {{hpi}}',
      'Exam: {{exam}}',
    ]);
    const filled = fillTemplate(template, { hpi: 'Only HPI was filled.' });
    const text = await extractText(filled);
    expect(text).toContain('HPI: Only HPI was filled.');
    // mammoth trims trailing whitespace per line, so `Exam: ` (with
    // the placeholder collapsed to empty) reads as `Exam:` — the
    // key invariant is that the label still appears and the literal
    // `{{exam}}` placeholder has been replaced.
    expect(text).toContain('Exam:');
    expect(text).not.toContain('{{exam}}');
    expect(text).not.toContain('{{{exam}}}');
  });

  it('renders empty for unsupported tokens the doctor added', async () => {
    const template = await buildTestDocx([
      'Standard: {{hpi}}',
      'Custom: {{my_custom_field}}',
    ]);
    const filled = fillTemplate(template, { hpi: 'Filled HPI' });
    const text = await extractText(filled);
    expect(text).toContain('Standard: Filled HPI');
    expect(text).toContain('Custom:'); // trailing space stripped by mammoth
    expect(text).not.toContain('{{my_custom_field}}');
  });

  it('renders a template with zero tokens unchanged', async () => {
    const template = await buildTestDocx([
      'Plain heading',
      'Body with no placeholders.',
    ]);
    const filled = fillTemplate(template, {});
    const text = await extractText(filled);
    expect(text).toContain('Plain heading');
    expect(text).toContain('Body with no placeholders.');
  });
});
