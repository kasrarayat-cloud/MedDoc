// ============================================================================
// F6.4 — EVERY MARKDOWN HEADING DEPTH REACHES THE DOCUMENT AS A HEADING
// ----------------------------------------------------------------------------
// `docx-generator` matched `^##\s+` only. A `###` line fell through to the
// plain-paragraph branch and printed ITS OWN HASHES into the signed document,
// while `ehr-formatters.ts:88` strips `^#{1,6}\s+` and the clipboard read the
// same note correctly. **Two surfaces, one note, two different records** — and
// since F3 the DOCX side is FOUR surfaces (pre-sign preview, signed preview,
// Word download, PDF download), because they all converge on
// `generateVisitDocx`.
//
// MEASURED ON PRODUCTION 2026-08-20 before a line was changed:
//
//     ##   282 heading lines / 47 visits
//     ###    8 heading lines /  3 visits   <- rendered as literal `### …`
//     #      0
//     headings with LEADING whitespace: 0
//
// ⚠️ WHY THIS GATE EXISTS AND NOT JUST THE EXPORT-CLEANLINESS ARM.
// `export-cleanliness.test.ts`'s heading arm is what SHOULD have caught this
// and could not — it was vacuous for TWO independent reasons (see the comment
// on `FORBIDDEN_MARKDOWN` there). That arm is now able to go red and is the
// broad net. This file pins the specific decisions the fix made, because a
// "no forbidden pattern" assertion is satisfied just as well by a renderer
// that DROPS the heading entirely.
//
// ⚠️ THE BYTE-IDENTITY ARM IS THE LOAD-BEARING ONE. The fix's whole safety
// claim is that the 282 existing `##` lines DO NOT MOVE. That is asserted
// against a paragraph captured by rendering `origin/main`'s own generator —
// a measurement, not an argument.
// ============================================================================
import { describe, expect, it } from 'vitest';
import JSZip from 'jszip';

import { generateVisitDocx } from '../docx-generator';
import { formatForEhr } from '../ehr-formatters';
import type { VisitExportData } from '../visit-export';

/** The heading detector `export-cleanliness` uses, restated here so this gate
 *  fails if the two ever disagree about what an unrendered heading looks
 *  like. `[ \t]*` is required: the tag strip turns a paragraph's OPENING tags
 *  into spaces, so a leaked heading reads `"\n      ### x"`. */
const UNRENDERED_HEADING_RE = /(^|\n)[ \t]*#{1,6}\s/;

/** Paragraph-aware strip — `</w:p>` and `<w:br/>` are the only tags that mean
 *  "line ends here"; every other tag boundary separates runs of one line. */
function docxTextFromXml(xml: string): string {
  return xml
    .replace(/<w:br\b[^>]*\/?>/g, '\n')
    .replace(/<\/w:p>/g, '\n')
    .replace(/<[^>]+>/g, ' ');
}

function fixture(soapText: string): VisitExportData {
  return {
    visitId: 'v_f64',
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
  };
}

async function renderDocxXml(soapText: string): Promise<string> {
  const buf = await generateVisitDocx(fixture(soapText));
  const zip = await JSZip.loadAsync(buf);
  return zip.file('word/document.xml')!.async('string');
}

/** The `<w:p>…</w:p>` element carrying `needle`, verbatim. */
function paragraphContaining(xml: string, needle: string): string {
  const all = xml.match(/<w:p\b[\s\S]*?<\/w:p>/g) ?? [];
  const hit = all.filter((p) => p.includes(needle));
  // ⚠️ NON-VACUITY: "no paragraph" and "the wrong paragraph" must not both
  // read as a pass, and two hits means the needle is not discriminating.
  expect(hit.length, `expected exactly one paragraph containing ${needle}`).toBe(1);
  return hit[0];
}

// Captured 2026-08-20 by rendering `origin/main`'s OWN `docx-generator.ts`
// (restored from git into the worktree, rendered, then restored from a scratch
// copy — never from git). If a future edit changes how a `##` section heading
// reaches Word, this string is what says so.
const MAIN_H2_PARAGRAPH =
  '<w:p><w:pPr><w:spacing w:after="80" w:before="160"/></w:pPr>' +
  '<w:r><w:rPr><w:b/><w:bCs/><w:sz w:val="24"/><w:szCs w:val="24"/></w:rPr>' +
  '<w:t xml:space="preserve">SUBJECTIVE</w:t></w:r></w:p>';

describe('F6.4 — markdown heading depths reach the DOCX as headings', () => {
  it('`##` renders BYTE-IDENTICALLY to what main shipped — the 282 live lines do not move', async () => {
    const xml = await renderDocxXml('## SUBJECTIVE\nCough x3 days.');
    expect(paragraphContaining(xml, 'SUBJECTIVE')).toBe(MAIN_H2_PARAGRAPH);
  });

  it.each([1, 2, 3, 4, 5, 6])(
    'depth %i renders as a heading — the text survives and the hashes do not',
    async (depth) => {
      const marker = `HeadingDepth${depth}Marker`;
      const xml = await renderDocxXml(`${'#'.repeat(depth)} ${marker}\nBody text.`);
      const text = docxTextFromXml(xml);

      expect(text.includes('\n'), 'stripped text carries no newline — detector vacuous').toBe(true);
      expect(text).toContain(marker);
      expect(UNRENDERED_HEADING_RE.test(text), `depth ${depth} leaked its hashes`).toBe(false);
      // The hashes are gone from the RUN, not merely absent from a line start.
      expect(paragraphContaining(xml, marker)).not.toContain('#');
    }
  );

  it.each([1, 2, 3, 4, 5, 6])(
    'depth %i agrees with the EHR clipboard about the heading TEXT',
    async (depth) => {
      const marker = `ParityDepth${depth}Marker`;
      const soap = `${'#'.repeat(depth)} ${marker}\nBody text.`;
      const docx = docxTextFromXml(await renderDocxXml(soap));
      // `epic` is the format that strips markdown rather than forwarding it
      // for the target EHR to render (athena/eCW/generic deliberately keep it).
      const ehr = formatForEhr('epic', fixture(soap));

      expect(docx).toContain(marker);
      expect(ehr).toContain(marker);
      expect(ehr).not.toContain(`${'#'.repeat(depth)} ${marker}`);
    }
  );

  it('`###`+ is BOLD but visibly SUBORDINATE — two tiers, no invented ladder', async () => {
    const section = paragraphContaining(await renderDocxXml('## SectionMark\nx'), 'SectionMark');
    const sub = paragraphContaining(await renderDocxXml('### SubMark\nx'), 'SubMark');

    // Both are headings: bold.
    expect(section).toContain('<w:b/>');
    expect(sub).toContain('<w:b/>');
    // The section keeps the larger size; the subsection sits at body size.
    // ⚠️ Asserted as an INEQUALITY between the two, not as a pinned number on
    // the subsection — a gate that pins "no w:sz at all" would redden on a
    // future body-size token change that is not this decision.
    expect(section).toContain('w:sz w:val="24"');
    expect(sub).not.toContain('w:sz w:val="24"');
  });

  it('a heading with LEADING whitespace is still a heading (forward-only: prod holds 0)', async () => {
    const xml = await renderDocxXml('   ## IndentedMark\nx');
    expect(paragraphContaining(xml, 'IndentedMark')).not.toContain('#');
  });

  it('a `#` that is NOT a heading is left alone — the false-positive direction', async () => {
    // ⚠️ THE ARM EVERYBODY SKIPS. Widening `^##` to `^#{1,6}` risks eating
    // content, and "no hashes anywhere" would be satisfied by a renderer that
    // silently deleted this line's `#`.
    const xml = await renderDocxXml('## PLAN\nRepeat study #3 in six months.\n#NotAHeading');
    const text = docxTextFromXml(xml);
    expect(text).toContain('Repeat study #3 in six months.');
    expect(text).toContain('#NotAHeading');
    // …and neither one trips the detector, because neither is `#{1,6}` + space.
    expect(UNRENDERED_HEADING_RE.test(text)).toBe(false);
  });

  it('SEVEN hashes is NOT a heading — the honest limit, recorded as a measurement', async () => {
    // ⚠️ STATED SO THE FIX IS NOT READ WIDER THAN IT IS. `#{1,6}` is the
    // CommonMark ceiling, so `####### x` renders literally and NEITHER
    // detector objects — the same blind spot in both, deliberately, because
    // they share the depth bound. Production holds **0** such lines (measured
    // 2026-08-20, same query shape that returned 282 `##` / 8 `###`).
    const xml = await renderDocxXml('####### SevenHashMark\nx');
    const text = docxTextFromXml(xml);
    expect(text).toContain('####### SevenHashMark');
    expect(UNRENDERED_HEADING_RE.test(text)).toBe(false);
  });

  it('form-only section boundaries stay at `##` — re-aligning them would SPLIT a bilateral study', async () => {
    // ⚠️ THE REFUTATION PASS FOUND THIS: `form-only.ts` carried a comment
    // saying its `^##\s+` matched the generator's level, and F6.4 made that
    // sentence false. The comment is corrected — and the BEHAVIOUR is pinned
    // here, because a future reader "closing the divergence" by widening
    // `SECTION_HEADING_RE` to `#{1,6}` would make every `### Right` a section
    // boundary and renumber each half of a bilateral study from 1.
    const { renumberFormSections } = await import('../form-only');
    const soap = [
      '## FINDINGS',
      '### Right',
      'Vessel patent.  No thrombus seen.',
      '### Left',
      'Vessel patent.  Reflux noted.',
    ].join('\n');
    const out = renumberFormSections(soap);
    // The `#{3,}` bail keeps structured sub-blocks out of renumbering
    // entirely — so the section is returned untouched, as ONE section.
    expect(out).toBe(soap);
  });

  it('POSITIVE CONTROL — the detector fires on a document that really did leak', () => {
    // Shape taken verbatim from the pre-fix rendering measured on 2026-08-20:
    // `</w:p>` became `\n`, the paragraph's own opening tags became spaces.
    const leaked = 'CLINICAL NOTE  \n      ### Bilateral lower extremity  \n      Reflux present.';
    expect(UNRENDERED_HEADING_RE.test(leaked)).toBe(true);
    // And the pre-`[ \t]*` regex — the one that shipped — could not see it.
    expect(/(^|\n)#{1,6}\s/.test(leaked)).toBe(false);
  });
});
