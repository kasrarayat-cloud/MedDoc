// ============================================================================
// F6.1 — A LINE BREAK INSIDE FREE TEXT IS CONTENT, AND IT REACHES THE DOCUMENT
// ----------------------------------------------------------------------------
// THE DEFECT. `docx-generator.ts` emitted each free-text field as ONE
// `TextRun`. A literal `\n` inside `<w:t>` is NOT a line break in OOXML — Word
// collapses it to a space — so every break the author wrote was silently
// flattened. Measured before the fix: `<w:br/>` count **0**, with both lines
// sharing one `<w:t xml:space="preserve">`. The attribute says `preserve` and
// the bytes really do carry the `\n`; it is the RENDERER that drops it, which
// is why reading the XML "looked fine".
//
// THE POPULATION. Measured against production 2026-08-17 by the defect's own
// predicate — split on `/\n\n+/` as the renderer does, then ask whether any
// resulting block still holds a `\n`: **43 of 43** visits with a non-empty
// `patientSummary`. The universal case, not an edge.
//
// THE BLAST RADIUS IS FOUR SURFACES, NOT ONE. The ledger row says "lost in the
// DOCX". Since F3 the pre-sign preview, the signed preview, the Word download
// and the PDF download all converge on `generateVisitDocx` (`visit-pdf.ts`), so
// one flattening reached all four. `ehr-formatters.ts:423` meanwhile passes
// `patientSummary.trim()` into the EHR clipboard as plain text, where `\n`
// survives — so the clipboard and the signed document disagreed about what the
// note said.
//
// ----------------------------------------------------------------------------
// THREE INDEPENDENTLY-FAILING CLAIMS
//
//   A. THE BREAK SURVIVES — for every field in the enumeration, two authored
//      lines reach the document as two runs separated by a real `<w:br/>`.
//   B. THE FIX IS A NO-OP ON BREAK-FREE TEXT — one run, no `break` key, nothing
//      restyled. A fidelity fix that also changes every unaffected document is
//      a bigger change than anybody reviewed.
//   C. THE TREATMENT IS WIRED — the helper is used at exactly the classified
//      call sites, so a site that quietly stops using it reddens.
//
// ----------------------------------------------------------------------------
// ⚠️ WHAT THIS GATE DOES **NOT** WATCH — recorded so its green is not read
// wider than it is.
//
//   · **A NEW free-text field that never calls the helper at all.** Claim C is
//     a census of `freeTextRuns(` CALL SITES; a field added tomorrow with a
//     bare `new TextRun({ text: data.somethingNew })` is invisible to it, and
//     Claim A only knows the four fields named below. This is the honest limit
//     and it is why the treatment lives on a shared helper rather than on the
//     callers — the helper is the thing a future author is likely to reach for,
//     but "likely" is not "must".
//   · **`nativePdfExport`.** A doctor whose template is a CERTIFIED flat PDF
//     receives their own page and never enters `generateVisitDocx`
//     (`export/pdf/route.ts`, `NEXT_PUBLIC_TEMPLATE_NATIVE_PDF` true in prod).
//     Production holds 0 certifications, so no live row takes that path today.
//   · **The SOAP body.** It is CORRECT already and is asserted here only as a
//     control: `renderSoapParagraphs` splits on `\n` and emits a Paragraph per
//     line, so its breaks were never at risk. An arm that "fixed" it would be
//     the numbering-case inversion — repairing the surface that was right.
//   · **`chiefComplaint` and the header-field values.** They route through
//     `metaRows`, whose sources are a trimmed name, a formatted date, a
//     regex-extracted surgeon or a blank — none can carry an authored break.
//     ⚠️ The production control for `chiefComplaint` is VACUOUS: **0** visits
//     have a non-empty one, so "0 carry a newline" says nothing. Classified by
//     reading `resolveHeaderFields`, not by that zero.
// ============================================================================

import { describe, expect, it } from 'vitest';
import { execSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import JSZip from 'jszip';
import { generateVisitDocx } from '../docx-generator';
import type { VisitExportData } from '../visit-export';

const APP_ROOT = path.resolve(__dirname, '../../..');

/** Matches the ONLY thing Word treats as an in-paragraph line break. Proved to
 *  discriminate by the controls in Claim A — it fires on the fixture that has
 *  breaks and reads 0 on the one that does not. */
const BR_RE = /<w:br\s*\/>/g;

function data(over: Partial<VisitExportData>): VisitExportData {
  return {
    visitId: 'v_f61',
    patientName: 'F61 Fixture',
    specialty: 'gastroenterology',
    chiefComplaint: null,
    status: 'READY',
    createdAt: new Date('2026-08-17T00:00:00Z'),
    signedAt: null,
    clinicianName: 'Dr Fixture',
    clinicianEmail: 't@example.invalid',
    soapText: '## SUBJECTIVE\nsoap line one\nsoap line two',
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
  } as VisitExportData;
}

async function documentXml(over: Partial<VisitExportData>): Promise<string> {
  const buf = await generateVisitDocx(data(over));
  const zip = await JSZip.loadAsync(buf);
  return zip.file('word/document.xml')!.async('string');
}

/** The `<w:t>` payloads, in document order. Asserting through the parsed runs
 *  rather than through a substring of the file: text presence is not
 *  membership, and `'a\nb'` CONTAINS `'a'` while being the defect. */
function runTexts(xml: string): string[] {
  return Array.from(xml.matchAll(/<w:t[^>]*>([^<]*)<\/w:t>/g)).map((m) => m[1]);
}

/** True when `first` and `second` are adjacent runs AND a `<w:br/>` sits
 *  between them. Both halves matter: two runs with no break render as one
 *  continuous line, which is the defect wearing a different shape. */
function brSeparates(xml: string, first: string, second: string): boolean {
  const i = xml.indexOf(`>${first}</w:t>`);
  const j = xml.indexOf(`>${second}</w:t>`);
  if (i === -1 || j === -1 || j <= i) return false;
  return /<w:br\s*\/>/.test(xml.slice(i, j));
}

// ---------------------------------------------------------------------------
// THE ENUMERATION. This table IS the item's named set — every site in
// `docx-generator.ts` that renders author-written free text. Claim A iterates
// it; nothing is asserted "for the class" without being listed.
// ---------------------------------------------------------------------------
const FIELDS: Array<{
  name: string;
  /** Production rows carrying a break TODAY, measured 2026-08-17. */
  prodRowsAffected: string;
  over: Partial<VisitExportData>;
  firstLine: string;
  secondLine: string;
}> = [
  {
    name: 'patientSummary (a single break inside one block)',
    prodRowsAffected: '43 of 43',
    over: { patientSummary: 'ALPHA one\nALPHA two' },
    firstLine: 'ALPHA one',
    secondLine: 'ALPHA two',
  },
  {
    name: 'referral.reason',
    prodRowsAffected: '0 of 13 — latent, the code flattens',
    over: {
      referrals: [
        { to: 'Cardiology', urgency: 'routine', reason: 'CHARLIE one\nCHARLIE two' },
      ] as unknown as VisitExportData['referrals'],
    },
    // ⚠️ The indent is part of the expectation: `linePrefix` must reach line
    // TWO. A second line hanging left of its first reads as a different field.
    firstLine: '    CHARLIE one',
    secondLine: '    CHARLIE two',
  },
  {
    name: 'referral.relevant_history',
    prodRowsAffected: '0 of 13 — latent, the code flattens',
    over: {
      referrals: [
        {
          to: 'Cardiology',
          urgency: 'routine',
          reason: 'r',
          relevant_history: 'DELTA one\nDELTA two',
        },
      ] as unknown as VisitExportData['referrals'],
    },
    firstLine: '    DELTA one',
    secondLine: '    DELTA two',
  },
  {
    name: 'modifier.rationale',
    prodRowsAffected: '0 of 14 — latent, the code flattens',
    over: {
      modifiers: [
        { code: '25', rationale: 'ECHO one\nECHO two' },
      ] as unknown as VisitExportData['modifiers'],
    },
    // The `Modifier -NN: ` label rides line one; the continuation carries no
    // indent, matching what the single run looked like before the fix.
    firstLine: 'Modifier -25: ECHO one',
    secondLine: 'ECHO two',
  },
];

describe('F6.1 (A) — the authored break reaches the document', () => {
  for (const f of FIELDS) {
    it(`${f.name} — two runs, separated by a real <w:br/>  [prod: ${f.prodRowsAffected}]`, async () => {
      const xml = await documentXml(f.over);
      const texts = runTexts(xml);

      expect(
        texts,
        `${f.name}: the two authored lines did not arrive as SEPARATE runs. ` +
          'A single run holding a literal \\n is the F6.1 defect — Word ' +
          'renders it as a space.',
      ).toEqual(expect.arrayContaining([f.firstLine, f.secondLine]));

      expect(
        texts.some((t) => t.includes('\n')),
        `${f.name}: a run still carries a literal \\n. That is the defect, ` +
          'whatever else this document got right.',
      ).toBe(false);

      expect(
        brSeparates(xml, f.firstLine, f.secondLine),
        `${f.name}: the runs are adjacent but NO <w:br/> separates them, so ` +
          'they render as one continuous line — the same wrong output by a ' +
          'different route.',
      ).toBe(true);
    });
  }

  it('CONTROL — the SOAP body was already correct and is not touched', async () => {
    const xml = await documentXml({});
    const texts = runTexts(xml);
    // `renderSoapParagraphs` splits on \n into PARAGRAPHS. Asserted so a future
    // change that routes SOAP through the helper is a deliberate decision and
    // not a silent restyle of every note in the system.
    expect(texts).toEqual(expect.arrayContaining(['soap line one', 'soap line two']));
    expect(texts.some((t) => t.includes('soap line one\nsoap line two'))).toBe(false);
  });
});

describe('F6.1 (B) — break-free text is byte-for-byte what it always was', () => {
  it('no <w:br/> is emitted, and the matcher is therefore discriminating', async () => {
    const withBreaks = await documentXml({ patientSummary: 'one\ntwo' });
    const without = await documentXml({ patientSummary: 'one line only' });

    // ⚠️ THE PAIR IS THE CONTROL. A matcher that read 0 on both would be
    // broken, and a matcher that read >0 on both would be matching noise.
    expect(
      (withBreaks.match(BR_RE) || []).length,
      'the fixture WITH a break emitted no <w:br/> — the fix is not applied, ' +
        'or this matcher cannot see one. Either way nothing below is evidence.',
    ).toBeGreaterThan(0);

    expect(
      (without.match(BR_RE) || []).length,
      'a summary with NO authored break emitted a <w:br/>. The fix has ' +
        'started inventing line breaks, which is a fidelity defect in the ' +
        'opposite direction.',
    ).toBe(0);
  });

  it('a single-line field produces exactly ONE run holding exactly that text', async () => {
    const xml = await documentXml({ patientSummary: 'FOXTROT single line' });
    const hits = runTexts(xml).filter((t) => t.includes('FOXTROT'));
    expect(
      hits,
      'the no-break case must be one run, unchanged. More than one means the ' +
        'helper is splitting text nobody asked it to split.',
    ).toEqual(['FOXTROT single line']);
  });

  it('paragraph breaks still make PARAGRAPHS, not <w:br/> pairs', async () => {
    // The `\n\n+` split predates F6.1 and is correct: a blank line is a new
    // paragraph, not two line breaks. Regressing it into breaks would collapse
    // the summary's spacing across every visit.
    const xml = await documentXml({ patientSummary: 'GOLF block one\n\nGOLF block two' });
    expect((xml.match(BR_RE) || []).length).toBe(0);
    expect(runTexts(xml)).toEqual(
      expect.arrayContaining(['GOLF block one', 'GOLF block two']),
    );
  });

  it('an EMPTY line inside free text is pinned, not accidental', async () => {
    // ⚠️ RAISED BY THE REFUTATION PASS, AND PINNED RATHER THAN ASSUMED.
    // `a\n\nb` cannot occur inside a patient-summary BLOCK (the `\n\n+` split
    // consumes it), but a referral reason is not split at all, so it can.
    // `freeTextRuns` yields ['a', '', 'b'] → run, break+empty, break+'b'.
    // The question the pass could not answer by reading: does an EMPTY run
    // still carry its <w:br/>, or does `docx` drop the run and the break with
    // it — silently collapsing a blank line the author wrote?
    const xml = await documentXml({
      referrals: [
        { to: 'Cardiology', urgency: 'routine', reason: 'INDIA one\n\nINDIA two' },
      ] as unknown as VisitExportData['referrals'],
    });
    expect(
      (xml.match(BR_RE) || []).length,
      'an authored BLANK line inside a referral reason produced fewer than ' +
        'two <w:br/>. The empty run was dropped and the blank line with it.',
    ).toBeGreaterThanOrEqual(2);
    expect(runTexts(xml)).toEqual(
      expect.arrayContaining(['    INDIA one', '    INDIA two']),
    );
  });

  it('\\r\\n and a bare \\r are breaks too, and leave no stray \\r behind', async () => {
    const xml = await documentXml({ patientSummary: 'HOTEL one\r\nHOTEL two\rHOTEL three' });
    const texts = runTexts(xml);
    expect(texts).toEqual(
      expect.arrayContaining(['HOTEL one', 'HOTEL two', 'HOTEL three']),
    );
    expect(
      texts.some((t) => t.includes('\r')),
      'a \\r survived inside a run. Splitting on \\n alone leaves it there, ' +
        'and Word renders it as a stray glyph.',
    ).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// (C) THE TREATMENT IS WIRED
// ---------------------------------------------------------------------------

function isCommentLine(hit: string): boolean {
  const text = hit.replace(/^[^:]*:\d+:/, '').replace(/\/\*.*?\*\//g, ' ');
  return /^\s*(\/\/|\*|\/\*)/.test(text) || text.trim() === '';
}

function gitGrep(pattern: string, pathspec: string): string[] {
  try {
    return execSync(`git grep -n -- ${JSON.stringify(pattern)} -- ${pathspec}`, {
      cwd: APP_ROOT,
      encoding: 'utf8',
    })
      .split('\n')
      .filter(Boolean)
      .filter((h) => !isCommentLine(h));
  } catch {
    // `git grep` exits 1 on NO MATCHES. The controls below are what separate
    // that from a traversal that never ran.
    return [];
  }
}

describe('F6.1 (C) — the traversal itself works', () => {
  it('POSITIVE CONTROL — finds a symbol that certainly exists', () => {
    expect(
      gitGrep('generateVisitDocx', "'src'").length,
      'the traversal found no reference to generateVisitDocx, which certainly ' +
        'exists. The instrument is broken — do not read the census below.',
    ).toBeGreaterThan(1);
  });

  it('NEGATIVE CONTROL — empty for a token that is genuinely absent', () => {
    // Assembled at runtime so no literal of it exists in any tracked file,
    // including this one.
    const absent = 'zzzNoSuchSymbol' + 'AnywhereF61zzz';
    expect(gitGrep(absent, "'src'")).toEqual([]);
  });
});

describe('F6.1 (C) — every free-text site renders through the helper', () => {
  /** ⚠️ THIS TABLE IS THE SPEC AND THE CENSUS IS DIFFED AGAINST IT. A call in
   *  the code and not here reddens, and so does a row here with no call. The
   *  count is per FIELD, not per line, and it is a human classification. */
  const EXPECTED_CALL_COUNT = FIELDS.length;

  const calls = gitGrep(
    'freeTextRuns(',
    "'src/lib/docx-generator.ts'",
  ).filter((h) => !/function freeTextRuns/.test(h));

  it(`the helper is called exactly ${EXPECTED_CALL_COUNT} times — one per enumerated field`, () => {
    expect(
      calls.length,
      'the number of freeTextRuns call sites no longer matches the ' +
        'enumeration in FIELDS. Either a free-text field stopped using the ' +
        'helper (the F6.1 defect, restored) or a new one was added and is ' +
        'not covered by claim A. Update BOTH, deliberately.',
    ).toBe(EXPECTED_CALL_COUNT);
  });

  it('the definition still exists and is the only definition', () => {
    const defs = gitGrep('function freeTextRuns', "'src/lib/docx-generator.ts'");
    expect(
      defs.length,
      'a second definition of freeTextRuns would let half the callers get a ' +
        'different behaviour with nothing saying so.',
    ).toBe(1);
  });

  it('no TextRun template literal in the generator carries an embedded \\n', () => {
    // ⚠️ READ THE FILE, DO NOT SHELL OUT. The first version of this arm passed
    // a pattern containing a BACKTICK to `git grep` through `execSync`, which
    // runs via /bin/sh: the backtick opened a command substitution, sh died
    // with "EOF in backquote substitution", `gitGrep` swallowed the non-zero
    // exit as "no matches", and the arm asserted over an EMPTY list — a green
    // that measured nothing. Caught because the shell printed its complaint
    // beside the passing run. This is AGENTS.md's "prose is never a shell
    // argument" arriving inside a test, and the cure is to not use a shell.
    const src = readFileSync(
      path.join(APP_ROOT, 'src/lib/docx-generator.ts'),
      'utf8',
    );

    // Positive control FIRST: the pattern must find the construct at all,
    // otherwise a zero below is blindness rather than cleanliness.
    const templateRuns = Array.from(src.matchAll(/new TextRun\(\{\s*text: `([^`]*)`/g));
    expect(
      templateRuns.length,
      'no `new TextRun({ text: `…`` construct was found in the generator. ' +
        'The matcher is wrong — the zero below would mean nothing.',
    ).toBeGreaterThan(0);

    for (const m of templateRuns) {
      expect(
        m[1].includes('\\n'),
        `a TextRun template literal carries an embedded \\n: ${m[0]}. ` +
          'A literal newline inside <w:t> is not a line break — route it ' +
          'through freeTextRuns.',
      ).toBe(false);
    }
  });
});
