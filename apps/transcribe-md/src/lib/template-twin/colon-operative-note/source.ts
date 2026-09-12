// ============================================================================
// SLICE 0 (#317) — the owner's colon OPERATIVE NOTE, authored as a native DOCX
// Template Twin. Built to the structure the owner enumerated, reproducing the
// layout of `colon_blank_answers.pdf` (the owner-confirmed source; the named
// `colon_questions_only.pdf` was not retained — board/PDF-UPLOAD-NOT-RETAINED).
//
// Every fillable slot is a Word CONTENT CONTROL (w:sdt) identified by w:alias,
// which the compiler (`note-template-docx/compiler.ts`) turns into a field. The
// three Findings and three Recommendations slots deliberately reuse their base
// label — `fieldId` is salted by structural POSITION, not label, so each of the
// six compiles to a distinct field.
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

function heading(text: string): string {
  return `<w:p><w:r><w:t>${text}</w:t></w:r></w:p>`;
}

/** A label run followed by its inline control, e.g. "Patient Name: [ ]". */
function labelledLine(label: string, control: string): string {
  return `<w:p><w:r><w:t>${label} </w:t></w:r>${control}</w:p>`;
}

/** A numbered slot line, e.g. "1. [ ]", inside a numbered section. */
function numberedSlot(n: number, control: string): string {
  return `<w:p><w:r><w:t>${n}. </w:t></w:r>${control}</w:p>`;
}

// The controls, in DOCUMENT ORDER (the order the compiler walks them and the
// order they are declared below). Aliases mirror the form's field names.
// LABELS (5) · SECTION BODIES: Procedure/Preop Dx/Consent/Description + DD/DT (6)
// · NUMBERED SLOTS: Findings 1–3, Recommendations 1–3 (6) = 17 controls.
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
  'Findings 1',
  'Findings 2',
  'Findings 3',
  'Recommendations 1',
  'Recommendations 2',
  'Recommendations 3',
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
    ${numberedSlot(1, textField(109, 'Findings 1', 'Enter finding 1.'))}
    ${numberedSlot(2, textField(110, 'Findings 2', 'Enter finding 2.'))}
    ${numberedSlot(3, textField(111, 'Findings 3', 'Enter finding 3.'))}
    ${heading('RECOMMENDATIONS:')}
    ${numberedSlot(1, textField(112, 'Recommendations 1', 'Enter recommendation 1.'))}
    ${numberedSlot(2, textField(113, 'Recommendations 2', 'Enter recommendation 2.'))}
    ${numberedSlot(3, textField(114, 'Recommendations 3', 'Enter recommendation 3.'))}
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
