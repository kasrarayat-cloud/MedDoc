// ============================================================================
// SLICE 0 (#317) — the owner's colon OPERATIVE NOTE, authored as a native DOCX
// Template Twin. Built to the structure the owner enumerated, reproducing the
// layout of `colon_blank_answers.pdf` (the owner-confirmed source; the named
// `colon_questions_only.pdf` was not retained — board/PDF-UPLOAD-NOT-RETAINED).
//
// Every fillable slot is a Word CONTENT CONTROL (w:sdt) identified by w:alias,
// which the compiler (`note-template-docx/compiler.ts`) turns into a field.
//
// ⚠️ #319 — THE THREE FINDINGS AND THREE RECOMMENDATIONS SLOTS SHARE ONE
// IDENTITY ON PURPOSE, SO THEY DISTRIBUTE. Each Findings slot carries the SAME
// alias ("Findings") AND the same tag ("findings"), and each is ALONE in its
// paragraph (no leading "N." run). That is exactly what a #313 bullet group
// requires — shared declared identity (G3), sole-in-paragraph (G4), one unbroken
// run (G5), same scaffold (G6) — so `distributeListItems` places ONE dictated
// finding per slot instead of the whole joined list in every slot. `fieldId` is
// salted by structural POSITION, so the three still compile to distinct fields.
// (The bullet group also needs its three mappings identical (G7); the certify
// act pins them, since the model could otherwise propose three slightly
// different ones for three identical labels.)
//
// The visible "1. 2. 3." numbering the earlier draft carried is dropped: a
// leading number RUN is visible text in the paragraph, which disqualifies the
// control from being sole-in-paragraph and breaks distribution outright. The
// slots render as consecutive lines under the section heading — clinically the
// same numbered list, and the content (one finding per line) is what fills.
//
// ⚠️ AUTHORED ONCE, PINNED BY SHA. `fieldId` is salted with the whole-package
// sha256 and JSZip is not a reproducible-archive writer, so the PACKAGE identity
// is not reproducible — but the word/document.xml IS deterministic and is what
// this module pins. Regenerating the package mints a new identity that no longer
// matches its certificate; the committed .docx is produced once and never
// re-emitted to "get the same form."
// ============================================================================
import JSZip from 'jszip';

/** A free-text content control. `prompt` is the blank state Word shows. */
function textField(id: number, alias: string, prompt: string): string {
  return (
    `<w:sdt><w:sdtPr><w:id w:val="${id}"/><w:alias w:val="${alias}"/><w:text/></w:sdtPr>` +
    `<w:sdtContent><w:r><w:t>${prompt}</w:t></w:r></w:sdtContent></w:sdt>`
  );
}

/** A control with a SHARED declared identity — the same `alias` AND `tag` on
 *  every slot of a numbered section, which is what lets the three join one #313
 *  bullet group (G3). `alias` still wins as the label source, so `labelSource`
 *  stays 'alias' and the tag is carried alongside it. */
function taggedField(id: number, alias: string, tag: string, prompt: string): string {
  return (
    `<w:sdt><w:sdtPr><w:id w:val="${id}"/><w:alias w:val="${alias}"/><w:tag w:val="${tag}"/><w:text/></w:sdtPr>` +
    `<w:sdtContent><w:r><w:t>${prompt}</w:t></w:r></w:sdtContent></w:sdt>`
  );
}

function heading(text: string): string {
  return `<w:p><w:r><w:t>${text}</w:t></w:r></w:p>`;
}

/** A label run followed by its inline control, e.g. "Patient Name: [ ]". */
function labelledLine(label: string, control: string): string {
  return `<w:p><w:r><w:t>${label} </w:t></w:r>${control}</w:p>`;
}

/** A bullet slot: the control ALONE in its paragraph (no leading number run), so
 *  `soleParagraphControlOf` accepts it (G4) and the section's slots distribute
 *  one dictated item each. A visible "N." run here would break that. */
function bulletSlot(control: string): string {
  return `<w:p>${control}</w:p>`;
}

// The controls, in DOCUMENT ORDER (the order the compiler walks them and the
// order they are declared below), as their compiled labels. `alias` is the label
// source, so this is the `originalLabel` sequence P1 asserts.
// LABELS (5) · SECTION BODIES: Procedure/Preop Dx/Consent/Description + DD/DT (6)
// · NUMBERED SLOTS: three "Findings" + three "Recommendations" (6) = 17 controls.
// ⚠️ THE NUMBERED SLOTS SHARE A LABEL — that is the #313 bullet-group identity
// (G3), not an accident, so this list carries the repeats. `fieldId` is salted
// by structural position, so the three still compile to distinct fields.
// DD/DT print last on the form (after "Electronically Signed"), so they are last
// in document order even though they are "section bodies" in the owner's list.
export const COLON_TWIN_ALIASES = [
  'Patient Name',
  'Patient DOB',
  'Patient ID',
  'Date of Surgery',
  'Surgeon',
  'Procedure',
  'Preoperative Diagnosis',
  'Consent',
  'Description of Procedure',
  'Findings',
  'Findings',
  'Findings',
  'Recommendations',
  'Recommendations',
  'Recommendations',
  'DD',
  'DT',
] as const;

export const COLON_TWIN_CONTROL_COUNT = COLON_TWIN_ALIASES.length; // 17

export const COLON_OPERATIVE_NOTE_DOCUMENT_XML = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
  xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml"
  xmlns:w15="http://schemas.microsoft.com/office/word/2012/wordml"
  xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <w:body>
    ${heading('OPERATIVE NOTE')}
    ${labelledLine('PATIENT NAME:', textField(100, 'Patient Name', 'Enter the patient name.'))}
    ${labelledLine('PATIENT DOB:', textField(101, 'Patient DOB', 'Enter the patient date of birth.'))}
    ${labelledLine('PATIENT ID #:', textField(102, 'Patient ID', 'Enter the patient identifier.'))}
    ${labelledLine('DATE OF SURGERY:', textField(103, 'Date of Surgery', 'Enter the date of surgery.'))}
    ${labelledLine('SURGEON:', textField(104, 'Surgeon', 'Enter the surgeon.'))}
    ${heading('PROCEDURE:')}
    <w:p>${textField(105, 'Procedure', 'Enter the procedure performed.')}</w:p>
    ${heading('PREOPERATIVE DIAGNOSIS:')}
    <w:p>${textField(106, 'Preoperative Diagnosis', 'Enter the preoperative diagnosis.')}</w:p>
    ${heading('CONSENT:')}
    <w:p>${textField(107, 'Consent', 'Enter the consent statement.')}</w:p>
    ${heading('DESCRIPTION OF PROCEDURE:')}
    <w:p>${textField(108, 'Description of Procedure', 'Enter the description of the procedure.')}</w:p>
    ${heading('POSTOPERATIVE FINDINGS:')}
    ${bulletSlot(taggedField(109, 'Findings', 'findings', 'Enter a finding.'))}
    ${bulletSlot(taggedField(110, 'Findings', 'findings', 'Enter a finding.'))}
    ${bulletSlot(taggedField(111, 'Findings', 'findings', 'Enter a finding.'))}
    ${heading('RECOMMENDATIONS:')}
    ${bulletSlot(taggedField(112, 'Recommendations', 'recommendations', 'Enter a recommendation.'))}
    ${bulletSlot(taggedField(113, 'Recommendations', 'recommendations', 'Enter a recommendation.'))}
    ${bulletSlot(taggedField(114, 'Recommendations', 'recommendations', 'Enter a recommendation.'))}
    ${heading('Electronically Signed')}
    ${labelledLine('DD:', textField(115, 'DD', 'Enter the dictation date.'))}
    ${labelledLine('DT:', textField(116, 'DT', 'Enter the transcription date.'))}
  </w:body>
</w:document>`;

// A minimal, clean OPC skeleton — NO header/footer, so the package carries
// exactly the 17 body controls above and nothing leaks in from furniture parts.
// inspectDocxPackage requires only [Content_Types].xml, _rels/.rels, and the
// officeDocument relationship pointing at word/document.xml; headers, footers,
// styles and numbering are all optional.
const CONTENT_TYPES = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>`;

const ROOT_RELATIONSHIPS = `<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>`;

/** Build the blank colon operative-note package in memory, from the source above. */
export function buildColonOperativeNoteDocx(): Promise<Buffer> {
  const zip = new JSZip();
  zip.file('[Content_Types].xml', CONTENT_TYPES);
  zip.file('_rels/.rels', ROOT_RELATIONSHIPS);
  zip.file('word/document.xml', COLON_OPERATIVE_NOTE_DOCUMENT_XML);
  return zip.generateAsync({
    type: 'nodebuffer',
    compression: 'DEFLATE',
    compressionOptions: { level: 6 },
  });
}
