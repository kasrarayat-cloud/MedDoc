// ============================================================================
// S2 — the materialised fill-line is the field's BLANK STATE (owner ruling,
// 2026-09-14): shown when blank, REPLACED by the value when filled, never both.
// Proves the relocation against the REAL S1 derivation + compiler.
// ============================================================================
import { describe, expect, it } from 'vitest';
import JSZip from 'jszip';

import { compileTemplateDocx } from '@/lib/note-template-docx';
import { deriveProseTwin, derivedTwinProbeIsValid } from '../../prose-form/derive-prose-twin';
import { linesToProseDocx } from '../pdf-to-prose-docx';
import { relocateFillLinesToBlankState, FILL_LINE_BLANK } from '../fill-line-blank-state';

const verify = async (bytes: Uint8Array, expected: number): Promise<boolean> => {
  try {
    return derivedTwinProbeIsValid(compileTemplateDocx(bytes), expected);
  } catch {
    return false;
  }
};

async function docXml(bytes: Uint8Array): Promise<string> {
  const zip = await JSZip.loadAsync(bytes);
  return zip.file('word/document.xml')!.async('string');
}

/** A twin derived from the S2 prose shape (colon labels + a numbered slot), with
 *  the materialised underscore affordance — exactly what create-draft feeds. */
async function derivedTwin(): Promise<{ bytes: Uint8Array; slots: number }> {
  const docx = await linesToProseDocx([
    'PATIENT NAME: ______',
    'PROCEDURE: ______',
    '1. ______',
  ]);
  const d = await deriveProseTwin(docx, verify);
  return { bytes: d!.bytes, slots: d!.slots.length };
}

describe('S2 — fill-line becomes the blank state (never both)', () => {
  it('moves the materialised line OFF the label and INTO the control content', async () => {
    const { bytes, slots } = await derivedTwin();
    expect(slots).toBe(3);
    const before = await docXml(bytes);
    // Before: the underscores sit in the label run, outside the control.
    expect(before).toMatch(/PATIENT NAME: ______<\/w:t><\/w:r><w:sdt/);

    const out = await relocateFillLinesToBlankState(bytes, slots, verify);
    expect(out).not.toBeNull();
    const after = await docXml(out!);

    // The label run no longer carries the underscores…
    expect(after).toMatch(/PATIENT NAME: <\/w:t><\/w:r><w:sdt/);
    expect(after).not.toMatch(/______<\/w:t><\/w:r><w:sdt/);
    // …and each control's CONTENT is now the fill line.
    expect((after.match(new RegExp(FILL_LINE_BLANK, 'g')) ?? []).length).toBe(3);
  });

  it('preserves the control count and kinds (the keystone still holds)', async () => {
    const { bytes, slots } = await derivedTwin();
    const out = await relocateFillLinesToBlankState(bytes, slots, verify);
    const ir = compileTemplateDocx(out!);
    expect(ir.fields.length).toBe(3);
    expect(ir.stats.blockingUnsupported).toBe(0);
    expect(ir.fields.every((f) => f.kind === 'narrative_text')).toBe(true);
  });

  it('⚠️ FILLED → the value alone: a fill replaces the whole sdtContent, so no line survives', async () => {
    const { bytes, slots } = await derivedTwin();
    const out = await relocateFillLinesToBlankState(bytes, slots, verify);
    // Simulate the renderer clearing/filling a control: it replaces the WHOLE
    // w:sdtContent subtree (certification-lifecycle #164). After that, NO fill
    // line remains anywhere — the doctor sees "PATIENT NAME: John", never
    // "PATIENT NAME: ______John".
    const filled = (await docXml(out!)).replace(
      /<w:sdtContent>[\s\S]*?<\/w:sdtContent>/g,
      '<w:sdtContent><w:r><w:t>Jane Roe</w:t></w:r></w:sdtContent>',
    );
    expect(filled).not.toContain(FILL_LINE_BLANK);
    expect(filled).not.toMatch(/_{2,}/); // no underscores at all once filled
    expect(filled).toContain('PATIENT NAME: '); // the label survives, blank of furniture
    expect(filled).toContain('Jane Roe');
  });

  it('does NOT touch underscores that are not a control affordance (a body divider)', async () => {
    // A standalone divider line becomes a "Fill-in" control via isBlankFillLine,
    // but a divider EMBEDDED mid-text with no following control must be left
    // alone. Craft a doc where a run has underscores NOT before a <w:sdt>.
    const zip = new JSZip();
    zip.file('[Content_Types].xml', '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>');
    zip.file('_rels/.rels', '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>');
    // A paragraph with a trailing underscore run and NO control after it.
    zip.file('word/document.xml',
      '<?xml version="1.0"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>' +
      '<w:p><w:r><w:t xml:space="preserve">a divider ______</w:t></w:r></w:p>' +
      '</w:body></w:document>');
    const bytes = await zip.generateAsync({ type: 'uint8array' });
    // No controls → verify(…, 0) is trivially true but there is nothing to move;
    // the regex leaves the divider (no <w:sdt> follows) → out === xml → null.
    const out = await relocateFillLinesToBlankState(bytes, 0, verify);
    expect(out).toBeNull();
  });

  it('is fail-safe: an unrecognised (no-control) package returns null, keeping the twin', async () => {
    const empty = await linesToProseDocx(['Just prose, no fields.']);
    expect(await relocateFillLinesToBlankState(empty, 0, verify)).toBeNull();
  });

  // ⚠️ ADVERSARIAL FIX (2026-09-14): a real text-layer blank with TRAILING
  // FURNITURE ("Total time: ______ minutes") puts the underscores in the MIDDLE
  // of the label — the control lands at the paragraph END. It must be LEFT ALONE:
  // NEVER strip the label furniture while still filling the control (that renders
  // the line beside the value — "both", strictly worse than untransformed).
  it('leaves a NON-ADJACENT fill line (trailing unit/format hint) untouched — no double line', async () => {
    // These derive one control each (S1's colon form is un-anchored for a unit).
    const docx = await linesToProseDocx([
      'PATIENT NAME: ______', // adjacent (materialised) — WILL relocate
      'Total time: ______ minutes', // trailing unit — must NOT relocate
      'DOB: ______ (mm/dd/yyyy)', // trailing format hint — must NOT relocate
    ]);
    const d = await deriveProseTwin(docx, verify);
    const out = await relocateFillLinesToBlankState(d!.bytes, d!.slots.length, verify);
    expect(out).not.toBeNull();
    const after = await docXml(out!);

    // The adjacent one relocated: label cleaned, control holds the line.
    expect(after).toMatch(/PATIENT NAME: <\/w:t><\/w:r><w:sdt/);
    // The trailing-furniture ones are UNCHANGED: underscores stay in the label,
    // control content stays the prompt — NOT a line. So a fill shows the value
    // once (beside the untouched label), never a SECOND line inside the control.
    expect(after).toContain('Total time: ______ minutes');
    expect(after).toContain('DOB: ______ (mm/dd/yyyy)');
    expect(after).toContain('Enter Total time'); // prompt not replaced by a line
    expect(after).toContain('Enter DOB');
    // Exactly ONE control shows the fill line (the adjacent PATIENT NAME).
    expect((after.match(new RegExp(FILL_LINE_BLANK, 'g')) ?? []).length).toBe(1);
    // And no control's content is a line-beside-label-line double: the only
    // sdtContent underscores belong to the single relocated control.
  });

  it('handles an alias/label carrying an XML entity without corrupting it', async () => {
    const docx = await linesToProseDocx(['Height & weight: ______']);
    const d = await deriveProseTwin(docx, verify);
    const out = await relocateFillLinesToBlankState(d!.bytes, d!.slots.length, verify);
    expect(out).not.toBeNull();
    const after = await docXml(out!);
    expect(after).toContain('Height &amp; weight: </w:t>'); // entity intact, underscores stripped
    expect(after).toContain(FILL_LINE_BLANK);
  });
});
