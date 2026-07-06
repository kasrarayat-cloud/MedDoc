import { describe, expect, it } from 'vitest';
import JSZip from 'jszip';
import { docxToTextWithControls, choiceMarker } from '../docx-content-controls';

const NS = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"';

/** Minimal WordprocessingML with a run + a dropdown content control + a
 *  second run, wrapped in one paragraph. Mirrors the real IOV shape. */
function dropdownParagraph(labelText: string, options: string[], tailText: string): string {
  const items = options
    .map((o) => `<w:listItem w:displayText="${o}" w:value="${o}"/>`)
    .join('');
  return `<w:p>
    <w:r><w:t xml:space="preserve">${labelText}</w:t></w:r>
    <w:sdt>
      <w:sdtPr><w:dropDownList><w:listItem w:displayText="Choose an item." w:value=""/>${items}</w:dropDownList></w:sdtPr>
      <w:sdtContent><w:r><w:t>Choose an item.</w:t></w:r></w:sdtContent>
    </w:sdt>
    <w:r><w:t xml:space="preserve">${tailText}</w:t></w:r>
  </w:p>`;
}

async function makeDocx(bodyXml: string): Promise<Uint8Array> {
  const zip = new JSZip();
  zip.file(
    'word/document.xml',
    `<?xml version="1.0"?><w:document ${NS}><w:body>${bodyXml}</w:body></w:document>`
  );
  return zip.generateAsync({ type: 'uint8array' });
}

describe('docxToTextWithControls', () => {
  it('renders a dropdown as an inline choice marker, dropping the placeholder', async () => {
    const bytes = await makeDocx(
      dropdownParagraph('SIDE OF EXAM: ', ['Bilateral Detailed', 'Bilateral Screening'], '')
    );
    const { text, dropdownCount } = await docxToTextWithControls(bytes);
    expect(dropdownCount).toBe(1);
    expect(text).toContain('SIDE OF EXAM: {{one of: Bilateral Detailed | Bilateral Screening}}');
    expect(text).not.toContain('Choose an item.');
  });

  it('preserves the carrier sentence for inline slots (interdependent chain)', async () => {
    const bytes = await makeDocx(
      dropdownParagraph(
        'The ',
        ['great saphenous vein', 'small saphenous vein'],
        ' from the SFJ'
      )
    );
    const { text } = await docxToTextWithControls(bytes);
    expect(text).toBe('The {{one of: great saphenous vein | small saphenous vein}} from the SFJ');
  });

  it('reports 0 dropdowns for a plain docx (caller falls back to mammoth)', async () => {
    const bytes = await makeDocx('<w:p><w:r><w:t>Plain note, no dropdowns.</w:t></w:r></w:p>');
    const { text, dropdownCount } = await docxToTextWithControls(bytes);
    expect(dropdownCount).toBe(0);
    expect(text).toContain('Plain note, no dropdowns.');
  });

  it('choiceMarker joins options with the pipe delimiter', () => {
    expect(choiceMarker(['a', 'b', 'c'])).toBe('{{one of: a | b | c}}');
  });
});
