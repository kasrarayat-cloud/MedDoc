// ============================================================================
// S1 test fixture — a PROSE Word form with NO content controls.
// ----------------------------------------------------------------------------
// This is the INPUT to `deriveProseTwin`: a realistic minimal operative/consult
// form written as plain paragraphs — a heading, colon labels WITH fill blanks, a
// bare fill blank, section headings, and static sentences. It carries ZERO
// `w:sdt`. It stands in for "a Word form with blank lines and no controls" (the
// owner's reference case) so the derivation and its five proofs can run without a
// real (PHI-bearing) upload.
//
// ⚠️ AFFORDANCE-REQUIRED (2026-09-13). A fillable slot must carry an explicit fill
// blank ("LABEL: ______" or a bare "______" line). A BARE "LABEL:" (colon, no
// blank) is deliberately AMBIGUOUS — it is the shape of a section heading and of
// a lead-in sentence — so the fixture carries two such lines ("Assessment and
// Plan:", "Findings were as follows:") as NEGATIVE controls that MUST stay prose.
// "Weight: ______" is a POSITIVE control for a measurement-keyword label: it must
// derive and compile as a fillable field, not sink the whole form.
//
// Single-run paragraphs on purpose: the dominant real Word-form shape, and the
// shape regenerate-consult-form.ts also matched. Fancier run splits and
// nested-container cases are exercised by the derivation's own tokenizer tests.
//
// NOT a tracked .docx — built in-memory by the test, so the pre-commit fixture
// allowlist (blank/filled .docx hook) is untouched.
// ============================================================================
import JSZip from 'jszip';

/** Static paragraphs (heading, section headings, sentences) — must remain prose
 *  (no control). The two bare "LABEL:" lines are the affordance negative
 *  controls: a section heading and a lead-in sentence. */
export const PROSE_STATIC_LINES = [
  'OPERATIVE NOTE',
  'Assessment and Plan:',
  'Findings were as follows:',
  'The patient tolerated the procedure well.',
] as const;

/** The label lines the derivation must turn into controls, in document order.
 *  Each carries an explicit fill blank (the affordance). "Weight" is a
 *  measurement-keyword label — it must derive as a fillable field. */
export const PROSE_LABELS_WITH_BLANK = [
  'Patient Name: ______',
  'Date of Service: ______',
  'Weight: ______',
  'Preoperative Diagnosis: ______',
  'Procedure Performed: ______',
  'Description of Procedure: ______',
] as const;

/** A bare fill-blank line — one control (kind 'blank'). */
export const PROSE_BARE_BLANK = '______________________';

/** The aliases the derivation is expected to produce, in order. Labels keep their
 *  text verbatim (colon and trailing blank trimmed); the bare blank → 'Fill-in'. */
export const EXPECTED_DERIVED_ALIASES = [
  'Patient Name',
  'Date of Service',
  'Weight',
  'Preoperative Diagnosis',
  'Procedure Performed',
  'Description of Procedure',
  'Fill-in',
] as const;

function para(text: string): string {
  return `<w:p><w:r><w:t xml:space="preserve">${text.replace(/&/g, '&amp;').replace(/</g, '&lt;')}</w:t></w:r></w:p>`;
}

/** The prose form's `word/document.xml` — heading, six colon labels each with a
 *  fill blank, a bare blank, two bare-colon negative controls, and a closing
 *  sentence. No `w:sdt` anywhere. */
export const PROSE_FORM_DOCUMENT_XML =
  `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>` +
  `<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>` +
  para(PROSE_STATIC_LINES[0]) +
  PROSE_LABELS_WITH_BLANK.map(para).join('') +
  para(PROSE_BARE_BLANK) +
  para(PROSE_STATIC_LINES[1]) +
  para(PROSE_STATIC_LINES[2]) +
  para(PROSE_STATIC_LINES[3]) +
  `<w:sectPr><w:pgSz w:w="12240" w:h="15840"/></w:sectPr>` +
  `</w:body></w:document>`;

const CONTENT_TYPES_XML =
  `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>` +
  `<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">` +
  `<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>` +
  `<Default Extension="xml" ContentType="application/xml"/>` +
  `<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>` +
  `</Types>`;

const RELS_XML =
  `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>` +
  `<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">` +
  `<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>` +
  `</Relationships>`;

/** Build the prose form .docx bytes (the derivation INPUT). */
export async function buildProseFormDocx(): Promise<Uint8Array> {
  const zip = new JSZip();
  zip.file('[Content_Types].xml', CONTENT_TYPES_XML);
  zip.file('_rels/.rels', RELS_XML);
  zip.file('word/document.xml', PROSE_FORM_DOCUMENT_XML);
  return zip.generateAsync({ type: 'uint8array' });
}
