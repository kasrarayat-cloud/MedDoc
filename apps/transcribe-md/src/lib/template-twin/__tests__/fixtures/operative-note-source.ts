// ============================================================================
// THE SECOND SHAPE — a BLANK colonoscopy operative note, as OOXML.
// ----------------------------------------------------------------------------
// F5-i part 1 recorded that `tests/e2e/fixtures/` held exactly ONE real form —
// `sample-form.docx`, the venous duplex — and that a second SHAPE could not be
// walked because no operative-note template existed to walk. This module is
// that fixture's SOURCE.
//
// ⚠️ IT IS BLANK, AND THAT IS A RULE RATHER THAN A PROPERTY OF THIS FILE.
// AGENTS.md: "The distinction is FILLED vs BLANK, not file type. A blank form
// is a fixture; a filled one never is." Every content control below carries a
// PROMPT ("Enter the indication for the procedure.") and never a value. There
// is no patient, no date of service, no practice, no clinician name, and no
// finding. If you are editing this file, that constraint is the one to preserve.
//
// ⚠️ WHY THE SOURCE IS TRACKED SEPARATELY FROM THE .docx IT PRODUCES.
// The committed binary at `tests/e2e/fixtures/sample-operative-note.docx` is
// what an UPLOAD walk needs — a real file a doctor could drag in. A binary
// nobody can diff is also a binary that drifts silently, so the gate builds a
// package from THIS module in memory and asserts the committed file compiles to
// the identical field set. The bytes are therefore pinned to reviewable text,
// without depending on zip determinism.
//
// ⚠️ IT IS NOT A COPY OF ANY CUSTOMER DOCUMENT. The venous form in this repo is
// a real customer's blank template (a recorded decision). This one is authored
// here from the ordinary structure of a screening-colonoscopy operative note,
// so it carries no third party's layout at all.
// ============================================================================

// ⚠️ THIS FILE DECLARES SIXTEEN CONTROLS AND THE FIXTURE COMPILES TO SEVENTEEN
// FIELDS. The seventeenth is "Practice display name" — a letterhead control in
// the HEADER part, which `buildSyntheticDocx` supplies and this file never
// mentions. Said here because counting the controls below and getting 16
// against the gate's `toBe(17)` looks like an off-by-one in the assertion, and
// the obvious "correction" is to loosen it. The gate asserts that field by name
// for the same reason.

import { buildSyntheticDocx } from '@/lib/note-template-docx/__tests__/synthetic-docx';

/**
 * A dropdown content control. `w:alias` becomes the compiled field's
 * `originalLabel` with `labelSource: 'alias'` (`compiler.ts:1177-1184`), which
 * is why every control here carries one — a form whose controls had no alias
 * would compile to `Field 1`, `Field 2`, … and prove nothing about labels.
 */
function dropdown(id: number, alias: string, options: readonly string[]): string {
  const items = options
    .map(
      (o) =>
        `<w:listItem w:displayText="${o}" w:value="${o.toLowerCase().replace(/[^a-z0-9]+/g, '_')}"/>`,
    )
    .join('');
  return (
    `<w:sdt><w:sdtPr><w:id w:val="${id}"/><w:alias w:val="${alias}"/>` +
    `<w:dropDownList>${items}</w:dropDownList></w:sdtPr>` +
    `<w:sdtContent><w:r><w:t>Choose an item.</w:t></w:r></w:sdtContent></w:sdt>`
  );
}

/** A free-text content control. The prompt is the BLANK state Word shows. */
function textField(id: number, alias: string, prompt: string): string {
  return (
    `<w:sdt><w:sdtPr><w:id w:val="${id}"/><w:alias w:val="${alias}"/><w:text/></w:sdtPr>` +
    `<w:sdtContent><w:r><w:t>${prompt}</w:t></w:r></w:sdtContent></w:sdt>`
  );
}

function heading(text: string): string {
  return `<w:p><w:r><w:t>${text}</w:t></w:r></w:p>`;
}

function labelledLine(label: string, control: string): string {
  return `<w:p><w:r><w:t>${label} </w:t></w:r>${control}</w:p>`;
}

/**
 * ⚠️ THE SPECIMEN TABLE IS DELIBERATE, AND IT IS THE DISCRIMINATING PART OF
 * THIS FIXTURE.
 *
 * A form that refused simply because it had no table would prove nothing about
 * an operative note — it would prove something about tables. This one HAS a
 * table with data cells, and it still carries no measurement row, because
 * `veinGridCellConcept` (`concept-registry.ts:217-226`) only decides
 * `measurement.*` for a row that contains a REFLUX TIME cell. So the refusal
 * has to come from the field set's meaning, not from the document's furniture.
 */
function specimenTable(): string {
  const row = (n: number, site: string) =>
    `<w:tr>` +
    `<w:tc><w:p>${textField(300 + n, `Specimen ${n} site`, site)}</w:p></w:tc>` +
    `<w:tc><w:p>${textField(320 + n, `Specimen ${n} description`, 'Enter specimen description.')}</w:p></w:tc>` +
    `</w:tr>`;
  return (
    `<w:tbl><w:tblGrid><w:gridCol w:w="3600"/><w:gridCol w:w="5400"/></w:tblGrid>` +
    `<w:tr><w:tc><w:p><w:r><w:t>Site</w:t></w:r></w:p></w:tc>` +
    `<w:tc><w:p><w:r><w:t>Specimen description</w:t></w:r></w:p></w:tc></w:tr>` +
    row(1, 'Enter the site this specimen came from.') +
    row(2, 'Enter the site this specimen came from.') +
    `</w:tbl>`
  );
}

/**
 * The blank operative note, as `word/document.xml`.
 *
 * ⚠️ FIELD 108 — "Largest polyp diameter (mm)" — IS LOAD-BEARING AND IS NOT
 * DECORATION. `inferTextKind` (`compiler.ts:1187-1199`) reads the word
 * "diameter" and compiles that control with `kind: 'measurement'`. So this
 * fixture contains a field the COMPILER calls a measurement, and the derivation
 * must STILL answer `no_measurement_rows` — because that bucket is decided by
 * the field's `clinicalConcept`, never by its kind. Remove this control and the
 * gate's sharpest arm becomes vacuous while staying green.
 */
export const OPERATIVE_NOTE_DOCUMENT_XML = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
  xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml"
  xmlns:w15="http://schemas.microsoft.com/office/word/2012/wordml"
  xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <w:body>
    ${heading('COLONOSCOPY — OPERATIVE NOTE')}
    ${heading('PROCEDURE')}
    ${labelledLine('Procedure performed:', textField(101, 'Procedure performed', 'Enter the procedure performed.'))}
    ${labelledLine('Indication:', textField(102, 'Indication', 'Enter the indication for the procedure.'))}
    ${labelledLine('Sedation:', dropdown(103, 'Sedation', ['Monitored anesthesia care', 'Moderate sedation', 'General anesthesia'] as const))}
    ${labelledLine('Bowel preparation quality:', dropdown(104, 'Bowel preparation quality', ['Excellent', 'Good', 'Fair', 'Poor'] as const))}
    ${labelledLine('Extent of examination:', dropdown(105, 'Extent of examination', ['Terminal ileum', 'Cecum', 'Hepatic flexure', 'Splenic flexure', 'Incomplete'] as const))}
    ${heading('FINDINGS')}
    ${labelledLine('Findings:', textField(106, 'Findings', 'Enter the endoscopic findings.'))}
    ${labelledLine('Therapeutic manoeuvres:', textField(107, 'Therapeutic manoeuvres', 'Enter any therapeutic manoeuvres performed.'))}
    ${labelledLine('Largest polyp diameter (mm):', textField(108, 'Largest polyp diameter (mm)', 'Enter the largest polyp diameter in millimetres.'))}
    ${heading('SPECIMENS')}
    ${specimenTable()}
    ${heading('COMPLICATIONS AND DISPOSITION')}
    ${labelledLine('Complications:', textField(109, 'Complications', 'Enter any complications, or state none.'))}
    ${labelledLine('Estimated blood loss:', textField(110, 'Estimated blood loss', 'Enter the estimated blood loss.'))}
    ${labelledLine('Disposition:', dropdown(111, 'Disposition', ['Discharged to recovery', 'Admitted for observation', 'Transferred'] as const))}
    ${labelledLine('Recommended follow-up interval:', textField(112, 'Recommended follow-up interval', 'Enter the recommended follow-up interval.'))}
    <w:sectPr>
      <w:headerReference w:type="default" r:id="rIdHeader"/>
      <w:footerReference w:type="default" r:id="rIdFooter"/>
    </w:sectPr>
  </w:body>
</w:document>`;

/** Build the blank operative-note package in memory, from the source above. */
export function buildOperativeNoteDocx(): Promise<Buffer> {
  return buildSyntheticDocx({ documentXml: OPERATIVE_NOTE_DOCUMENT_XML });
}
