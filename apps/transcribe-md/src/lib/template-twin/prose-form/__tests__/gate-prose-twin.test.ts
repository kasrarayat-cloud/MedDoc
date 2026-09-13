// ============================================================================
// UPLOAD-AND-CERTIFIED · S1 — the five additive proofs for the DERIVED prose twin.
// ----------------------------------------------------------------------------
// A PROSE Word form (labels + blanks, NO controls) is derived into a fillable
// twin by `deriveProseTwin`, and the SAME compiler that certifies a hand-authored
// twin must accept it. These are the five additive proofs (the regenerate /
// colon-twin pattern, ruling #317 — a PATTERN, not an owner-quoted list), adapted
// for a derivation ALGORITHM rather than one pinned artifact:
//   P1 the derived twin carries exactly the enumerated controls, alias-labelled, in order
//   P2 it compiles with zero blocking refusals; every field is a fillable plain-text kind; non-vacuous
//   P3 every derived field has a distinct fieldId
//   P4 INSERT-ONLY: removing the injected controls yields the source byte-for-byte (layout preserved)
//   P5 furniture only: the twin's visible text is the doctor's own labels + "Enter …" prompts — no fabricated content
// Plus the keystone: the derivation SELF-VERIFIES by re-compiling and returns
// null on any mismatch, so a MALFORMED/mis-counted twin can never be produced
// (proved here by a negative control). The four regression tests at the end
// encode the 2026-09-13 adversarial pass (affordance-required detection; measure-
// ment-keyword labels accepted; MC-nested paragraphs not double-wrapped).
// ============================================================================
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { compileTemplateDocx } from '@/lib/note-template-docx';
import {
  deriveProseTwin,
  derivedTwinProbeIsValid,
  proseControlSdt,
} from '../derive-prose-twin';
import {
  buildProseFormDocx,
  PROSE_FORM_DOCUMENT_XML,
  PROSE_LABELS_WITH_BLANK,
  PROSE_BARE_BLANK,
  EXPECTED_DERIVED_ALIASES,
  PROSE_STATIC_LINES,
} from '../fixture';

/** The real compiler, as the derivation's self-verify + the proofs use it. */
function compile(bytes: Uint8Array) {
  return compileTemplateDocx(bytes);
}
/** The verify predicate is the SHARED keystone reader — the same one create-draft
 *  passes on the real path, so the gate cannot certify behaviour production does
 *  not get (one-rule-many-readers). */
const verify = async (bytes: Uint8Array, expected: number): Promise<boolean> => {
  try {
    return derivedTwinProbeIsValid(compile(bytes), expected);
  } catch {
    return false;
  }
};

async function deriveOrThrow() {
  const source = await buildProseFormDocx();
  const twin = await deriveProseTwin(source, verify);
  if (!twin) throw new Error('deriveProseTwin returned null on the fixture — self-verify failed');
  return twin;
}

const PLAIN_TEXT_KINDS = ['narrative_text', 'measurement', 'number'];

describe('S1 — deriveProseTwin: the five additive proofs', () => {
  it('P1 — the derived twin carries exactly the enumerated controls, alias-labelled, in order', async () => {
    const twin = await deriveOrThrow();
    expect(twin.slots.map((s) => s.alias)).toEqual([...EXPECTED_DERIVED_ALIASES]);
    const ir = compile(twin.bytes);
    expect(ir.fields.map((f) => f.originalLabel)).toEqual([...EXPECTED_DERIVED_ALIASES]);
    expect(ir.fields.every((f) => f.labelSource === 'alias')).toBe(true);
    // Six labels-with-blank + one bare blank = seven slots.
    expect(twin.slots.length).toBe(7);
  });

  it('P2 — compiles with zero blocking refusals; every field is a fillable plain-text kind; non-vacuous', async () => {
    const twin = await deriveOrThrow();
    const ir = compile(twin.bytes);
    expect(ir.fields.length).toBeGreaterThan(0); // not vacuously clean
    expect(ir.stats.blockingUnsupported).toBe(0);
    expect(ir.fields.every((f) => PLAIN_TEXT_KINDS.includes(f.kind))).toBe(true);
    // ⚠️ Fix-1 regression: the "Weight:" label compiles to a MEASUREMENT kind, and
    // the keystone must ACCEPT it — a keyword label must not sink the whole form.
    const weight = ir.fields.find((f) => f.originalLabel === 'Weight');
    expect(weight?.kind).toBe('measurement');
  });

  it('P3 — every derived field has a distinct fieldId', async () => {
    const twin = await deriveOrThrow();
    const ir = compile(twin.bytes);
    const ids = ir.fields.map((f) => f.fieldId);
    expect(new Set(ids).size).toBe(ids.length);
    expect(ids.length).toBe(7);
  });

  it('P4 — INSERT-ONLY: removing the injected controls yields the source byte-for-byte', async () => {
    const twin = await deriveOrThrow();
    // Strip every injected <w:sdt>…</w:sdt> block; what remains must be the
    // original document.xml, unchanged. This is the layout-preservation guarantee.
    const stripped = twin.documentXml.replace(/<w:sdt>[\s\S]*?<\/w:sdt>/g, '');
    expect(stripped).toBe(twin.sourceDocumentXml);
    expect(twin.sourceDocumentXml).toBe(PROSE_FORM_DOCUMENT_XML);
    // And the static lines were NOT wrapped (they carry no control). This loop is
    // ALSO the affordance negative control: 'Assessment and Plan:' and 'Findings
    // were as follows:' are bare-colon lines and must survive as intact prose.
    for (const line of PROSE_STATIC_LINES) {
      const paraRe = new RegExp(`<w:p><w:r><w:t[^>]*>${line.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}</w:t></w:r></w:p>`);
      expect(paraRe.test(twin.documentXml), `static line wrapped or altered: ${line}`).toBe(true);
    }
  });

  it('P5 — furniture only: visible text is the doctor’s labels + "Enter …" prompts, no fabricated content', async () => {
    const twin = await deriveOrThrow();
    const runs = [...twin.documentXml.matchAll(/<w:t\b[^>]*>([\s\S]*?)<\/w:t>/g)].map((m) => m[1]);
    const allowedStatic = new Set<string>([
      ...PROSE_STATIC_LINES,
      ...PROSE_LABELS_WITH_BLANK,
      PROSE_BARE_BLANK,
    ]);
    for (const run of runs) {
      const ok = run === '' || run.startsWith('Enter ') || allowedStatic.has(run);
      expect(ok, `unexpected visible run: ${JSON.stringify(run)}`).toBe(true);
    }
    // Every injected control's placeholder is an "Enter …" prompt, never data.
    const prompts = runs.filter((r) => r.startsWith('Enter '));
    expect(prompts.length).toBe(7);
  });

  it('KEYSTONE — the self-verify rejects a twin the compiler disagrees with (negative control)', async () => {
    const source = await buildProseFormDocx();
    // A verify that ALWAYS disagrees stands in for a form the transform got wrong:
    // deriveProseTwin must return null rather than ship unverified bytes.
    const twin = await deriveProseTwin(source, async () => false);
    expect(twin).toBeNull();
  });

  it('a docx that ALREADY has controls is not ours — returns null', async () => {
    // No-controls precondition: build a package whose document.xml has a w:sdt.
    const JSZip = (await import('jszip')).default;
    const withControl = PROSE_FORM_DOCUMENT_XML.replace(
      '</w:body>',
      `<w:p>${proseControlSdt('Existing', 'existing', 5, 'Enter Existing')}</w:p></w:body>`,
    );
    const zip = new JSZip();
    zip.file('[Content_Types].xml', '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="xml" ContentType="application/xml"/><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>');
    zip.file('_rels/.rels', '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>');
    zip.file('word/document.xml', withControl);
    const bytes = await zip.generateAsync({ type: 'uint8array' });
    expect(await deriveProseTwin(bytes, verify)).toBeNull();
  });

  // ── EDGE CASES the fixture (single-run, flat) does not cover ───────────────
  async function pkg(documentXml: string): Promise<Uint8Array> {
    const JSZip = (await import('jszip')).default;
    const z = new JSZip();
    z.file('[Content_Types].xml', '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="xml" ContentType="application/xml"/><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>');
    z.file('_rels/.rels', '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>');
    z.file('word/document.xml', documentXml);
    return z.generateAsync({ type: 'uint8array' });
  }
  const doc = (bodyInner: string, extraNs = '') =>
    `<?xml version="1.0"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"${extraNs}><w:body>${bodyInner}<w:sectPr/></w:body></w:document>`;

  it('⚠️ a MULTI-RUN label (Word splits "PATIENT NAME: ___" across runs) still derives one control, labelled from the joined text', async () => {
    const bytes = await pkg(doc(
      `<w:p w:rsidR="00AB12"><w:r><w:t xml:space="preserve">Patient</w:t></w:r><w:r><w:t xml:space="preserve"> Name</w:t></w:r><w:r><w:t>: ______</w:t></w:r></w:p>`,
    ));
    const twin = await deriveProseTwin(bytes, verify);
    expect(twin).not.toBeNull();
    expect(twin!.slots.map((s) => s.alias)).toEqual(['Patient Name']);
    const ir = compile(twin!.bytes);
    expect(ir.fields.map((f) => f.originalLabel)).toEqual(['Patient Name']);
    expect(ir.stats.blockingUnsupported).toBe(0);
  });

  it('⚠️ a TABLE cell label is NEVER wrapped (tables are a different slice) — the whole form quarantines if that is its only slot', async () => {
    // A body with ONLY a table label and no body-level slot → 0 derivable slots → null.
    const bytes = await pkg(doc(`<w:tbl><w:tr><w:tc><w:p><w:r><w:t>Cell Label: ______</w:t></w:r></w:p></w:tc></w:tr></w:tbl>`));
    const twin = await deriveProseTwin(bytes, verify);
    expect(twin).toBeNull(); // the table paragraph is not a body-level slot; nothing to derive
  });

  it('⚠️ a table + a body label: only the BODY label is wrapped, the table cell is untouched', async () => {
    const bytes = await pkg(doc(
      `<w:p><w:r><w:t>Surgeon: ______</w:t></w:r></w:p>` +
      `<w:tbl><w:tr><w:tc><w:p><w:r><w:t>Cell Label: ______</w:t></w:r></w:p></w:tc></w:tr></w:tbl>`,
    ));
    const twin = await deriveProseTwin(bytes, verify);
    expect(twin).not.toBeNull();
    expect(twin!.slots.map((s) => s.alias)).toEqual(['Surgeon']);
    // the control lands in the body paragraph, NOT inside the table cell
    expect(/<w:tc>[\s\S]*?<w:sdt>/.test(twin!.documentXml)).toBe(false);
    const ir = compile(twin!.bytes);
    expect(ir.fields.length).toBe(1);
  });

  it('a static sentence is NOT wrapped (fail-safe: only labels/blanks become controls)', async () => {
    const bytes = await pkg(doc(`<w:p><w:r><w:t>The patient tolerated the procedure well.</w:t></w:r></w:p>`));
    // No label, no blank → 0 slots → null (quarantine, as today).
    expect(await deriveProseTwin(bytes, verify)).toBeNull();
  });

  // ── 2026-09-13 ADVERSARIAL-PASS REGRESSIONS ────────────────────────────────
  it('⚠️ Findings 2 & 3 — a bare "LABEL:" (section heading / lead-in sentence) is NEVER wrapped: the fill affordance is required', async () => {
    // Section headings and lead-in sentences ARE the "LABEL:" shape; their value
    // is the prose below, not an inline slot. With no fill blank, none is a slot.
    const bytes = await pkg(doc(
      `<w:p><w:r><w:t>Assessment and Plan:</w:t></w:r></w:p>` +
      `<w:p><w:r><w:t>Impression:</w:t></w:r></w:p>` +
      `<w:p><w:r><w:t>Diagnosis:</w:t></w:r></w:p>` +
      `<w:p><w:r><w:t>Findings were as follows:</w:t></w:r></w:p>` +
      `<w:p><w:r><w:t>The following medications were reviewed:</w:t></w:r></w:p>`,
    ));
    // Zero affordance-bearing slots → deriveProseTwin returns null (quarantine).
    expect(await deriveProseTwin(bytes, verify)).toBeNull();
  });

  it('⚠️ Finding 3 — a bare heading beside a real affordance label: only the label is wrapped, the heading stays prose', async () => {
    const bytes = await pkg(doc(
      `<w:p><w:r><w:t>Assessment and Plan:</w:t></w:r></w:p>` +
      `<w:p><w:r><w:t>Surgeon: ______</w:t></w:r></w:p>`,
    ));
    const twin = await deriveProseTwin(bytes, verify);
    expect(twin).not.toBeNull();
    expect(twin!.slots.map((s) => s.alias)).toEqual(['Surgeon']);
    // the heading paragraph is untouched — no control injected into it
    expect(/<w:t>Assessment and Plan:<\/w:t><\/w:r><\/w:p>/.test(twin!.documentXml)).toBe(true);
    expect(compile(twin!.bytes).fields.length).toBe(1);
  });

  it('⚠️ Finding 4 — a <w:p> nested in mc:AlternateContent is NOT double-wrapped (the whole MC block passes through)', async () => {
    const bytes = await pkg(doc(
      `<w:p><w:r><w:t>Surgeon: ______</w:t></w:r></w:p>` +
      `<mc:AlternateContent><mc:Choice Requires="wps"><w:p><w:r><w:t>Diagnosis: ______</w:t></w:r></w:p></mc:Choice>` +
      `<mc:Fallback><w:p><w:r><w:t>Diagnosis: ______</w:t></w:r></w:p></mc:Fallback></mc:AlternateContent>`,
      ' xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006"',
    ));
    const twin = await deriveProseTwin(bytes, verify);
    expect(twin).not.toBeNull();
    // ONLY the body-level label is wrapped; neither MC branch is.
    expect(twin!.slots.map((s) => s.alias)).toEqual(['Surgeon']);
    expect(/<mc:AlternateContent[\s\S]*?<w:sdt>/.test(twin!.documentXml)).toBe(false);
    expect(compile(twin!.bytes).fields.length).toBe(1);
  });

  it('⚠️ fixed-diff A — decorative dividers (====, ----, bullets, ****) are NOT wrapped; only underscore blanks are', async () => {
    // Dividers alone carry no fill affordance → no slot → quarantine (null).
    expect(await deriveProseTwin(await pkg(doc(
      `<w:p><w:r><w:t>==============================</w:t></w:r></w:p>` +
      `<w:p><w:r><w:t>------------------------------</w:t></w:r></w:p>` +
      `<w:p><w:r><w:t>• • • •</w:t></w:r></w:p>`,
    )), verify)).toBeNull();
    // A divider beside a real label and a real underscore blank: only the label
    // and the underscore blank become controls; the divider stays static prose.
    const twin = await deriveProseTwin(await pkg(doc(
      `<w:p><w:r><w:t>==============================</w:t></w:r></w:p>` +
      `<w:p><w:r><w:t>Surgeon: ______</w:t></w:r></w:p>` +
      `<w:p><w:r><w:t>______________________</w:t></w:r></w:p>`,
    )), verify);
    expect(twin).not.toBeNull();
    expect(twin!.slots.map((s) => s.alias)).toEqual(['Surgeon', 'Fill-in']);
    expect(/<w:t>==============================<\/w:t><\/w:r><\/w:p>/.test(twin!.documentXml)).toBe(true);
    expect(compile(twin!.bytes).fields.length).toBe(2);
  });

  it('⚠️ fixed-diff B — a raw ">" inside a quoted attribute (image descr) does not desync the tokenizer', async () => {
    // A valid inline image whose alt-text carries a raw ">" — the tokenizer must
    // skip over quoted attribute values, or every label after it is dropped.
    const bytes = await pkg(doc(
      `<w:p><w:r><w:t>Surgeon: ______</w:t></w:r></w:p>` +
      `<w:p><w:r><w:drawing><wp:docPr id="2" name="p2" descr="a > b"/></w:drawing></w:r></w:p>` +
      `<w:p><w:r><w:t>Assistant: ______</w:t></w:r></w:p>` +
      `<w:p><w:r><w:t>Anesthesia: ______</w:t></w:r></w:p>`,
      ' xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"',
    ));
    const twin = await deriveProseTwin(bytes, verify);
    expect(twin).not.toBeNull();
    expect(twin!.slots.map((s) => s.alias)).toEqual(['Surgeon', 'Assistant', 'Anesthesia']);
    expect(compile(twin!.bytes).fields.length).toBe(3);
  });

  it('⚠️ fixed-diff — a </w:p> inside an XML comment is opaque: depth does not desync, real labels still wrap', async () => {
    const twin = await deriveProseTwin(await pkg(doc(
      `<w:p><w:r><w:t>Surgeon: ______</w:t></w:r></w:p>` +
      `<!-- a stray </w:p> and <w:p> hiding in a comment -->` +
      `<w:p><w:r><w:t>Assistant: ______</w:t></w:r></w:p>`,
    )), verify);
    expect(twin).not.toBeNull();
    expect(twin!.slots.map((s) => s.alias)).toEqual(['Surgeon', 'Assistant']);
    expect(compile(twin!.bytes).fields.length).toBe(2);
  });

  it('⚠️ fixed-diff C — a text box (VML) fill label is NOT wrapped: its inner paragraph is not a body line', async () => {
    // The fill label lives inside <w:txbxContent>; wrapping the OUTER <w:p> would
    // divorce the control from its label. Text boxes are a later slice → skip.
    const box =
      `<w:p><w:r><w:pict><v:shape id="s1" style="width:200pt;height:40pt"><v:textbox>` +
      `<w:txbxContent><w:p><w:r><w:t xml:space="preserve">Diagnosis: ______</w:t></w:r></w:p></w:txbxContent>` +
      `</v:textbox></v:shape></w:pict></w:r></w:p>`;
    // Text box alone → no body-level slot → null (quarantine).
    expect(await deriveProseTwin(await pkg(doc(box,
      ' xmlns:v="urn:schemas-microsoft-com:vml"')), verify)).toBeNull();
    // Text box beside a real body label: only the body label is wrapped, and NO
    // control is injected inside or after the text box.
    const twin = await deriveProseTwin(await pkg(doc(
      `<w:p><w:r><w:t>Surgeon: ______</w:t></w:r></w:p>` + box,
      ' xmlns:v="urn:schemas-microsoft-com:vml"')), verify);
    expect(twin).not.toBeNull();
    expect(twin!.slots.map((s) => s.alias)).toEqual(['Surgeon']);
    expect(/<w:pict>[\s\S]*?<w:sdt>/.test(twin!.documentXml)).toBe(false);
    expect(/<\/w:pict><\/w:r><w:sdt>/.test(twin!.documentXml)).toBe(false);
    expect(compile(twin!.bytes).fields.length).toBe(1);
  });

  it('⚠️ fixed-diff C — a DrawingML text box (wps:txbx) with TWO inner fields is not collapsed to one misplaced control', async () => {
    const box =
      `<w:p><w:r><w:drawing><wp:inline><a:graphic><a:graphicData><wps:wsp><wps:txbx><w:txbxContent>` +
      `<w:p><w:r><w:t xml:space="preserve">Name: ______</w:t></w:r></w:p>` +
      `<w:p><w:r><w:t xml:space="preserve">______</w:t></w:r></w:p>` +
      `</w:txbxContent></wps:txbx></wps:wsp></a:graphicData></a:graphic></wp:inline></w:drawing></w:r></w:p>`;
    // The whole text box is skipped; with no body-level slot the form quarantines
    // rather than shipping ONE misplaced control for two inner fields.
    expect(await deriveProseTwin(await pkg(doc(box,
      ' xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"' +
      ' xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"' +
      ' xmlns:wps="http://schemas.microsoft.com/office/word/2010/wordprocessingShape"')), verify)).toBeNull();
  });

  it('⚠️ fixed-diff D — numbered/bracketed/checkbox fill labels are detected (owner S1 scope), aliases drop the ordinal', async () => {
    const twin = await deriveProseTwin(await pkg(doc(
      `<w:p><w:r><w:t>Surgeon: ______</w:t></w:r></w:p>` +
      `<w:p><w:r><w:t>1. Primary diagnosis: ______</w:t></w:r></w:p>` +
      `<w:p><w:r><w:t>2. Secondary diagnosis: ______</w:t></w:r></w:p>` +
      `<w:p><w:r><w:t>(3) Tertiary diagnosis: ______</w:t></w:r></w:p>` +
      `<w:p><w:r><w:t>[4] Quaternary: ______</w:t></w:r></w:p>` +
      `<w:p><w:r><w:t>☐ Other: ______</w:t></w:r></w:p>`,
    )), verify);
    expect(twin).not.toBeNull();
    // No field dropped; every alias is the label, not the ordinal.
    expect(twin!.slots.map((s) => s.alias)).toEqual([
      'Surgeon', 'Primary diagnosis', 'Secondary diagnosis', 'Tertiary diagnosis', 'Quaternary', 'Other',
    ]);
    expect(compile(twin!.bytes).fields.map((f) => f.originalLabel)).toEqual([
      'Surgeon', 'Primary diagnosis', 'Secondary diagnosis', 'Tertiary diagnosis', 'Quaternary', 'Other',
    ]);
    // The ordinal text stays VISIBLE in the document (insert-only).
    expect(twin!.documentXml).toContain('1. Primary diagnosis: ______');
  });

  it('⚠️ fixed-diff P — single-letter clinical prefixes are PRESERVED distinctly, never stripped as ordinals', async () => {
    // "T. Bili"/"D. Bili" (total/direct bilirubin) and TNM "T./N./M. Stage" are
    // single-letter + punctuation — indistinguishable from a lettered ordinal by
    // shape. Stripping them COLLAPSED distinct labels to one alias. Single-letter
    // markers are no longer stripped: each keeps its full, distinct label.
    const twin = await deriveProseTwin(await pkg(doc(
      `<w:p><w:r><w:t>T. Bili: ______</w:t></w:r></w:p>` +
      `<w:p><w:r><w:t>D. Bili: ______</w:t></w:r></w:p>` +
      `<w:p><w:r><w:t>T. Stage: ______</w:t></w:r></w:p>` +
      `<w:p><w:r><w:t>N. Stage: ______</w:t></w:r></w:p>` +
      `<w:p><w:r><w:t>M. Stage: ______</w:t></w:r></w:p>`,
    )), verify);
    expect(twin).not.toBeNull();
    // Five DISTINCT aliases — the collapse bug (all → "Bili"/"Stage") is fixed.
    expect(twin!.slots.map((s) => s.alias)).toEqual([
      'T. Bili', 'D. Bili', 'T. Stage', 'N. Stage', 'M. Stage',
    ]);
    expect(new Set(twin!.slots.map((s) => s.alias)).size).toBe(5);
  });

  it('⚠️ fixed-diff P — a lettered ordinal keeps its prefix (accepted minor) but the field is still detected', async () => {
    // The trade for P: a lettered ordinal ("a)") is NOT stripped, so it stays in the
    // alias. The field is still present and fillable; the ordinal is visible at the
    // confirmation step. Far preferable to a collapsed/corrupted clinical label.
    const twin = await deriveProseTwin(await pkg(doc(
      `<w:p><w:r><w:t>a) Allergies: ______</w:t></w:r></w:p>`,
    )), verify);
    expect(twin).not.toBeNull();
    expect(twin!.slots.map((s) => s.alias)).toEqual(['a) Allergies']);
  });

  it('⚠️ fixed-diff D — the marker strip does NOT eat a real label ("B12 level")', async () => {
    const twin = await deriveProseTwin(await pkg(doc(
      `<w:p><w:r><w:t>B12 level: ______</w:t></w:r></w:p>`,
    )), verify);
    expect(twin).not.toBeNull();
    expect(twin!.slots.map((s) => s.alias)).toEqual(['B12 level']);
  });

  it('⚠️ fixed-diff Q — a colon label with trailing unit/format-hint after the blank is still detected', async () => {
    const twin = await deriveProseTwin(await pkg(doc(
      `<w:p><w:r><w:t>Patient name: ______________________</w:t></w:r></w:p>` +
      `<w:p><w:r><w:t xml:space="preserve">Date of birth: ______ (mm/dd/yyyy)</w:t></w:r></w:p>` +
      `<w:p><w:r><w:t xml:space="preserve">Total time spent: ______ minutes</w:t></w:r></w:p>` +
      `<w:p><w:r><w:t>Referring physician: ______________________</w:t></w:r></w:p>`,
    )), verify);
    expect(twin).not.toBeNull();
    // All four labeled blanks are detected; the alias is the label before the colon.
    expect(twin!.slots.map((s) => s.alias)).toEqual([
      'Patient name', 'Date of birth', 'Total time spent', 'Referring physician',
    ]);
    // The trailing hint/unit stays visible in the document (insert-only).
    expect(twin!.documentXml).toContain('(mm/dd/yyyy)');
    expect(twin!.documentXml).toContain('minutes');
  });

  it('⚠️ fixed-diff Q — the COLON-LESS anchor still rejects a sentence with an embedded blank', async () => {
    // Relaxing only the colon form must NOT re-admit "the patient was seen ___ for
    // evaluation" (no colon → weak signal → keep the end anchor).
    expect(await deriveProseTwin(await pkg(doc(
      `<w:p><w:r><w:t>The patient was seen ______ for evaluation of the lesion</w:t></w:r></w:p>`,
    )), verify)).toBeNull();
  });

  it('⚠️ fixed-diff D — a numbered BARE blank ("1. ____") is a blank slot', async () => {
    const twin = await deriveProseTwin(await pkg(doc(
      `<w:p><w:r><w:t>Surgeon: ______</w:t></w:r></w:p>` +
      `<w:p><w:r><w:t>1. ______</w:t></w:r></w:p>`,
    )), verify);
    expect(twin).not.toBeNull();
    expect(twin!.slots.map((s) => s.kind)).toEqual(['label', 'blank']);
  });

  it('⚠️ fixed-diff R — a label split across runs by <w:tab/> / <w:br/> is joined with a space, not fused', async () => {
    const twin = await deriveProseTwin(await pkg(doc(
      `<w:p><w:r><w:t xml:space="preserve">Patient</w:t></w:r><w:tab/><w:r><w:t xml:space="preserve">Name: ______</w:t></w:r></w:p>` +
      `<w:p><w:r><w:t xml:space="preserve">Referring</w:t></w:r><w:br/><w:r><w:t xml:space="preserve">Physician: ______</w:t></w:r></w:p>`,
    )), verify);
    expect(twin).not.toBeNull();
    // Words are separated, not concatenated ("PatientName"/"ReferringPhysician").
    expect(twin!.slots.map((s) => s.alias)).toEqual(['Patient Name', 'Referring Physician']);
  });

  it('drift guard — proseControlSdt matches regenerate-consult-form.ts sdt() shape', () => {
    // regenerate-consult-form.ts self-executes main() on import, so its sdt cannot
    // be imported; assert the two builders emit the same OOXML shape by reading the
    // source, so they cannot silently diverge (one-rule-many-readers).
    const regen = readFileSync(
      join(__dirname, '..', '..', '..', '..', '..', 'scripts', 'regenerate-consult-form.ts'),
      'utf8',
    );
    const mine = proseControlSdt('A', 'b', 7, 'Enter A');
    // Both wrap: <w:sdt><w:sdtPr><w:alias/><w:tag/><w:id/><w:text/></w:sdtPr><w:sdtContent><w:r><w:t xml:space="preserve">…
    expect(mine).toContain('<w:sdt><w:sdtPr><w:alias w:val="A"/><w:tag w:val="b"/>');
    expect(mine).toContain('<w:id w:val="7"/><w:text/></w:sdtPr><w:sdtContent>');
    expect(mine).toContain('<w:r><w:t xml:space="preserve">Enter A</w:t></w:r></w:sdtContent></w:sdt>');
    expect(regen).toContain('<w:alias w:val="${alias}"/><w:tag w:val="${tag}"/>');
    expect(regen).toContain('<w:id w:val="${id}"/><w:text/></w:sdtPr><w:sdtContent>');
  });
});
