// ============================================================================
// F6.2 — THE INJECTED `CLINICAL NOTE` HEADING LABELS CONTENT, OR IT IS ABSENT
// ----------------------------------------------------------------------------
// F6.2 was filed as *"`CLINICAL NOTE` heading renders on an EMPTY note — a
// heading over nothing is a document asserting content it does not have"*, and
// re-verified 2026-08-16 as **REFUTED AS WORDED, do NOT close, RESTATE**:
// `renderSoapParagraphs` returns EARLY on `!soap.trim()` with *"No SOAP note
// available."* and never pushes the heading, so for a whitespace-empty note the
// described defect cannot occur.
//
// ⚠️ THE REFUTATION WAS CORRECT AND THE CONCERN WAS STILL REAL. The early
// return guards on the RAW STRING being blank. The heading's actual claim is
// about the RENDERED BODY, and those are not the same predicate — a note whose
// text is non-blank can still render to nothing.
//
// THE REACHABLE INSTANCE, found by running the code rather than reading it:
// a note consisting only of markdown table SEPARATOR rows (`|---|---|`).
//
//     soap.trim()            -> non-empty, so NO early return
//     heading pushed         -> `◆  CLINICAL NOTE`
//     the line matches TABLE_ROW_RE      -> buffered, never emitted as prose
//     flushTable -> renderMarkdownTable  -> every row is a separator, so
//                                           `rows.length === 0` -> returns null
//     result: the heading, and nothing under it.
//
// MEASURED ON PRODUCTION 2026-08-21 BEFORE A LINE WAS CHANGED — 49 visits,
// `deletedAt IS NULL`, note text resolved exactly as `visit-export-server.ts`
// resolves it (`signedSoap ?? soapFinal` when signed, `soapFinal` otherwise):
//
//     notes empty after trim                     1     -> early return, correct today
//     notes non-empty                           48
//     notes that are headings ONLY (no prose)    0     (floor: 12 non-blank lines)
//     notes reaching this defect                 0
//
// So the fix protects **0 production rows today** and that is stated rather
// than hidden. It is worth landing anyway for the reason the early return
// exists at all: the invariant is *the chrome heading labels something*, and
// nothing asserted it, so a one-line reordering of that early return would
// reintroduce the filed defect with every gate still green.
//
// ⚠️ AND THE FIX MUST NOT EDITORIALIZE THE DOCTOR'S NOTE — the arm below named
// *"the note's OWN empty heading still renders"* is the load-bearing one.
// `## FINDINGS` with nothing under it is CONTENT THE NOTE CONTAINS; suppressing
// it would be the renderer deciding what the record says, which is the class
// ruling #112 ("the note's own numbers are CONTENT"), F6.1 and F6.4 all exist
// to prevent. Only the **injected** QuillMD chrome heading is in scope.
//
//     MEASURED, same query: 295 heading lines across the 48 non-empty notes —
//     which reconciles EXACTLY against `check-em-note-shape-artifacts.sh`'s own
//     projection control ("295 lines delivered = 295 headings"), so the
//     detector here and the shipped one agree about what a heading is.
//     Of those 295: 4 are followed by a DEEPER heading (`## FINDINGS` ->
//     `### Right Leg` — nested, legitimate, content), 2 by a same-or-shallower
//     one (genuinely contentless), 0 sit at end-of-note. The 2 live in ONE
//     unsigned visit and this gate deliberately leaves them rendered.
//
// ⚠️ THE FIRST DRAFT OF THAT MEASUREMENT SAID **6**, because its predicate was
// "heading followed by heading" and it counted the four nested ones. Recorded
// because it is this house's own wrong-quantity class caught in the act: the
// depth comparison is what makes the number mean what its name says.
// ============================================================================
import { describe, expect, it } from 'vitest';
import JSZip from 'jszip';

import { generateVisitDocx } from '../docx-generator';
import type { VisitExportData } from '../visit-export';

const INJECTED_HEADING = 'CLINICAL NOTE';
const EMPTY_PLACEHOLDER = 'No SOAP note available.';

function fixture(soapText: string, over: Partial<VisitExportData> = {}): VisitExportData {
  return {
    visitId: 'v_f62',
    patientName: 'Test Patient',
    specialty: 'Primary Care',
    chiefComplaint: 'Cough',
    status: 'SIGNED',
    createdAt: new Date('2026-07-23T00:00:00Z'),
    signedAt: new Date('2026-07-23T00:00:00Z'),
    clinicianName: 'Dr. Ada Lovelace',
    clinicianEmail: 'ada@example.test',
    soapText,
    icdCodes: [],
    em: null,
    procedures: [],
    modifiers: [],
    prescriptions: [],
    rxWarnings: [],
    referrals: [],
    patientSummary: null,
    headerFields: [],
    formOnly: false,
    formTitle: null,
    formSignature: null,
    ...over,
  };
}

async function renderDocxXml(
  soapText: string,
  over: Partial<VisitExportData> = {}
): Promise<string> {
  const buf = await generateVisitDocx(fixture(soapText, over));
  const zip = await JSZip.loadAsync(buf);
  return zip.file('word/document.xml')!.async('string');
}

/** Paragraph-aware strip — `</w:p>` and `<w:br/>` are the only tags meaning
 *  "line ends here". Mirrors `gate-f64-docx-heading-depths.test.ts`. */
function docxTextFromXml(xml: string): string {
  return xml
    .replace(/<w:br\b[^>]*\/?>/g, '\n')
    .replace(/<\/w:p>/g, '\n')
    .replace(/<[^>]+>/g, ' ');
}

describe('F6.2 — the injected CLINICAL NOTE heading labels content, or is absent', () => {
  // ── the BICONDITIONAL. Neither half is worth anything alone: a renderer that
  //    never emits the heading satisfies every absence arm below, and one that
  //    always emits it satisfies every presence arm.
  it('a note with prose GETS the injected heading — the false-green control', async () => {
    const xml = await renderDocxXml('## SUBJECTIVE\nCough for three days.');
    expect(xml).toContain(INJECTED_HEADING);
    expect(docxTextFromXml(xml)).toContain('Cough for three days.');
  });

  it('a whitespace-only note gets NO heading and DOES get the placeholder', async () => {
    const xml = await renderDocxXml('   \n\n  \t \n');
    expect(xml).not.toContain(INJECTED_HEADING);
    expect(docxTextFromXml(xml)).toContain(EMPTY_PLACEHOLDER);
  });

  it('an EMPTY-STRING note gets NO heading and DOES get the placeholder', async () => {
    const xml = await renderDocxXml('');
    expect(xml).not.toContain(INJECTED_HEADING);
    expect(docxTextFromXml(xml)).toContain(EMPTY_PLACEHOLDER);
  });

  // ── THE DEFECT. Non-blank text that renders to nothing.
  it.each([
    ['one separator row', '|---|---|'],
    ['two separator rows', '|---|---|\n|:--|--:|'],
    ['separator rows around blank lines', '\n|---|---|\n\n| --- | --- |\n\n'],
  ])(
    'a note that is only table separators (%s) does not get a heading over nothing',
    async (_label, soap) => {
      const xml = await renderDocxXml(soap);
      // The note text is genuinely non-blank, so the RAW-STRING early return
      // cannot fire. This is the predicate gap the fix closes.
      expect(soap.trim().length, 'fixture must not be blank, or it proves nothing').toBeGreaterThan(0);
      expect(xml).not.toContain(INJECTED_HEADING);
      expect(docxTextFromXml(xml)).toContain(EMPTY_PLACEHOLDER);
    }
  );

  // ── FIDELITY. The half that stops the fix becoming the worse bug.
  it("the NOTE'S OWN empty heading still renders — the fix touches chrome, not content", async () => {
    // Exactly the shape production holds: `## FINDINGS` with nothing under it,
    // followed by a same-depth heading. One prod visit, two such headings.
    const xml = await renderDocxXml('## FINDINGS\n\n## IMPRESSION\n\nNo acute findings.');
    const text = docxTextFromXml(xml);
    expect(xml).toContain(INJECTED_HEADING);
    expect(text).toContain('FINDINGS');
    expect(text).toContain('IMPRESSION');
    expect(text).not.toContain(EMPTY_PLACEHOLDER);
  });

  it('a note that is ONLY headings still renders every one of them', async () => {
    // `.trim()` sees this as non-empty and so does the body — headings ARE
    // renderable content. This is the case the 2026-08-16 re-verification
    // raised as "structurally present but contentless"; the answer is that the
    // note has content, it is just all structure. 0 production rows.
    const xml = await renderDocxXml('## SUBJECTIVE\n## OBJECTIVE\n## ASSESSMENT\n## PLAN');
    const text = docxTextFromXml(xml);
    expect(xml).toContain(INJECTED_HEADING);
    for (const h of ['SUBJECTIVE', 'OBJECTIVE', 'ASSESSMENT', 'PLAN']) {
      expect(text).toContain(h);
    }
    expect(text).not.toContain(EMPTY_PLACEHOLDER);
  });

  it('a real markdown table is content — the heading stays', async () => {
    const xml = await renderDocxXml('| Vessel | Reflux |\n|---|---|\n| GSV | 0.4 s |');
    const text = docxTextFromXml(xml);
    expect(xml).toContain(INJECTED_HEADING);
    expect(text).toContain('GSV');
    expect(text).not.toContain(EMPTY_PLACEHOLDER);
  });

  // ── FORM-ONLY. The heading is already suppressed there by design; assert the
  //    placeholder decision too, so a future edit cannot quietly inject chrome
  //    into an export whose entire contract is "no QuillMD chrome".
  it('form-only never gets the injected heading, with content or without', async () => {
    const withProse = await renderDocxXml('## FINDINGS\nNormal study.', { formOnly: true });
    const withNothing = await renderDocxXml('|---|---|', { formOnly: true });
    expect(withProse).not.toContain(INJECTED_HEADING);
    expect(withNothing).not.toContain(INJECTED_HEADING);
    expect(docxTextFromXml(withProse)).toContain('Normal study.');
  });
});
