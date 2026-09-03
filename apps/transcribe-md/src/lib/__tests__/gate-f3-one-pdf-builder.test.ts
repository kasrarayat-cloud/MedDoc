// ============================================================================
// F3 — ONE PDF builder. Asserted by TRAVERSAL, not by a spot-check.
// ----------------------------------------------------------------------------
// Ruling #113 retired `pdf-generator.ts` and converged the PDF export onto
// `generateVisitDocx` → Gotenberg. Ruling #116 scoped it: five callers, three
// converged, two deleted outright.
//
// ⚠️ WHY THIS FILE EXISTS AT ALL, AND WHY IT IS A TRAVERSAL.
// `gate-c2b-export-parity.test.ts` used to compare the two builders' page
// geometry. That comparison DIED WITH THE SECOND BUILDER — and its reasoning
// was replaced by an argument ("two artifacts from one set of bytes cannot
// carry two page sizes") which is only as good as its premise. This file gates
// the premise. If a second PDF path is ever reintroduced, C2-b's comment
// becomes a lie and nothing in C2-b would notice; THIS reddens.
//
// ⚠️ AND IT ASSERTS ABSENCE, WHICH MEANS IT NEEDS CONTROLS MORE THAN MOST.
// A traversal that silently walks nothing reports the same clean zero as a
// codebase with nothing to find. Every absence arm below is paired with a
// positive control on the same instrument.
// ============================================================================

import { execSync } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';

import { describe, expect, it, vi } from 'vitest';

import { VisitPdfUnavailableError, renderVisitPdf } from '../visit-pdf';
import type { VisitExportData } from '../visit-export';

// ---------------------------------------------------------------------------
// The traversal. `git grep` over TRACKED files only — an untracked scratch file
// is not something the product ships, and including one would make this gate
// red for reasons that have nothing to do with the product.
// ---------------------------------------------------------------------------
const APP_ROOT = `${__dirname}/../../..`;

/** ⚠️ EVERY ABSENCE NEEDLE EXCLUDES `__tests__`, AND THE REASON IS NOT TIDINESS.
 *
 *  A guard cannot be written in the language it bans. This file's own arms
 *  contain the literal strings `from '@/lib/pdf-generator'` and `from 'pdfkit'`
 *  as CODE — not as comments, so the comment filter cannot help — and they
 *  matched themselves the moment the file became tracked.
 *
 *  ⚠️ AND "THE MOMENT IT BECAME TRACKED" IS THE PART WORTH KEEPING. `git grep`
 *  reads TRACKED files only, so on the first run — with this file still
 *  untracked — every arm passed. The same code went red on the next run for no
 *  reason but a `git add`. A gate whose result depends on the index state of
 *  its own source was green for the wrong reason once already.
 *
 *  Tests do not ship, so excluding them costs nothing the product cares about;
 *  a reintroduced builder lives in `src`, not in a spec. */
const SRC_AND_SCRIPTS = "'src' 'scripts' ':(exclude)src/**/__tests__/**'";
const SRC_ONLY = "'src' ':(exclude)src/**/__tests__/**'";

/** A `git grep -n` hit line whose match sits in a whole-line comment.
 *
 *  ⚠️ THIS EXISTS BECAUSE THE GATE REDDENED AGAINST ITS OWN AUTHOR ON ITS FIRST
 *  RUN, and the arm that caught it had a comment asserting it could not:
 *  *"the call shape, which no comment in this repo writes."* `gate-c2b`'s
 *  explanatory prose wrote exactly that shape. The stale sentence there was
 *  corrected in the same commit — but relying on "no comment says this" is the
 *  substring trap wearing a promise, so the filter is here as well.
 *
 *  ⚠️ AND ITS FIRST "HONEST LIMIT" WAS INVERTED, WHICH IS WORSE THAN HAVING
 *  NONE. It claimed the filter "can only ever report MORE than the truth, never
 *  fewer". False: `/^\s*(\/\/|\*|\/\*)/` matched a LEADING BLOCK COMMENT on a
 *  line that then carries real code —
 *
 *      /* legacy path *\/ const pdf = await generateVisitPdf(data);
 *
 *  — so a live call was classified as prose and the arm went green. A stated
 *  limit that points the wrong way is a licence the reader grants on false
 *  information. Found by the refutation pass; the control below now covers that
 *  shape, which the first version's control did not.
 *
 *  The filter now closes block comments before deciding, so a line is prose
 *  only if NOTHING but comment survives. */
function isCommentLine(hit: string): boolean {
  const text = hit
    .replace(/^[^:]*:\d+:/, '')
    // Strip CLOSED block comments first — what remains is code, if any.
    .replace(/\/\*.*?\*\//g, ' ');
  return /^\s*(\/\/|\*|\/\*)/.test(text) || text.trim() === '';
}

function gitGrep(pattern: string, pathspec: string): string[] {
  try {
    return execSync(
      `git grep -n -- ${JSON.stringify(pattern)} -- ${pathspec}`,
      { cwd: APP_ROOT, encoding: 'utf8' },
    )
      .split('\n')
      .filter(Boolean)
      .filter((h) => !isCommentLine(h));
  } catch {
    // `git grep` exits 1 on NO MATCHES. That is the expected shape for every
    // absence arm here, so it is not an error — but see the control below,
    // which is what distinguishes "no matches" from "the traversal is broken".
    return [];
  }
}

describe('F3 — the traversal itself works', () => {
  it('POSITIVE CONTROL — git grep finds something that certainly exists', () => {
    // Without this, every zero below could mean "the search never ran": a wrong
    // cwd, an unavailable git, a bad pathspec. All three return [] silently.
    const hits = gitGrep('generateVisitDocx', "'src' 'tests'");
    expect(
      hits.length,
      'the traversal found NO reference to generateVisitDocx, which certainly ' +
        'exists. The instrument is broken, so every absence assertion in this ' +
        'file is meaningless — do not read the zeros below as evidence.',
    ).toBeGreaterThan(5);
  });

  it('NEGATIVE CONTROL — it returns empty for a token that is really absent', () => {
    // ⚠️ THE SENTINEL IS ASSEMBLED AT RUNTIME so no literal of it exists in any
    // tracked file — including this one. Written as a literal, it matched ITS
    // OWN SOURCE LINE the moment the file was committed, and the control that
    // proves the traversal can return empty was the third arm in this file to
    // fail that way. A control that cannot hold still is not a control.
    const absent = 'zzzNoSuchSymbol' + 'AnywhereF3zzz';
    expect(gitGrep(absent, "'src' 'tests'")).toEqual([]);
  });
});

describe('F3 — the retired builder is GONE, by traversal', () => {
  it('the module file does not exist', () => {
    expect(
      existsSync(`${APP_ROOT}/src/lib/pdf-generator.ts`),
      'pdf-generator.ts is back. Ruling #113 is delete-don\'t-hide: a second ' +
        'PDF builder is the drift this whole item exists to end.',
    ).toBe(false);
    // Control on the same predicate — the checker can see a file that IS there.
    expect(existsSync(`${APP_ROOT}/src/lib/docx-generator.ts`)).toBe(true);
  });

  it('nothing IMPORTS it, and nothing CALLS it', () => {
    // ⚠️ MATCH THE IMPORT SHAPE, NOT THE BARE WORD. This file, and several
    // others, mention `generateVisitPdf` in prose explaining the retirement —
    // the census named those comment sites precisely because a bare-word grep
    // reports a finished retirement as incomplete. That is the substring trap
    // this house has now met five times, so the needle is the import path.
    expect(gitGrep("from '@/lib/pdf-generator'", SRC_AND_SCRIPTS)).toEqual([]);
    expect(gitGrep("from '../pdf-generator'", SRC_ONLY)).toEqual([]);
    expect(gitGrep("from './pdf-generator'", SRC_ONLY)).toEqual([]);
    // The CALL shape. Comment lines are filtered by `gitGrep` — see the note on
    // `isCommentLine` for the run on which that turned out to be necessary.
    expect(gitGrep('await generateVisitPdf(', SRC_AND_SCRIPTS)).toEqual([]);
  });

  it('CONTROL — the comment filter does not hide a real CODE hit', () => {
    // The filter above is the kind of leniency that turns a gate into a
    // decoration, so it is pinned in both directions on its own instrument.
    expect(isCommentLine("a.ts:1:  // await generateVisitPdf(data)")).toBe(true);
    expect(isCommentLine("a.ts:1:   * await generateVisitPdf(data)")).toBe(true);
    expect(isCommentLine("a.ts:1:  const p = await generateVisitPdf(data);")).toBe(false);
    // ⚠️ THE SHAPE THE FIRST VERSION MISSED, and the reason its stated limit
    // was inverted: a closed block comment followed by live code on one line.
    expect(
      isCommentLine("a.ts:1:  /* legacy */ const p = await generateVisitPdf(data);"),
      'a leading block comment must not launder the code after it',
    ).toBe(false);
  });

  it('⚠️ NO OTHER MODULE MAY BUILD A PDF FROM SCRATCH — the ban is on the LIBRARY, not the filename', () => {
    // ⚠️ THE GATE'S TITLE SAYS "ONE PDF BUILDER"; ITS FIRST VERSION BANNED ONE
    // FILE PATH. `pdfkit` is still a dependency, so a new
    // `src/lib/export/pdf-fallback.ts` importing it and wired in as a
    // `.catch(() => buildFallbackPdf(data))` would satisfy every absence arm
    // above — the retired PATH absent, no retired IMPORT, no retired CALL —
    // while restoring precisely the second builder #113 exists to end.
    // A name is not a capability. Found by the refutation pass.
    //
    // ⚠️ THE PATHSPEC EXCLUDES `__tests__`, AND IT HAS TO — this arm's own
    // source line contains the needle, so its first run matched ITSELF and went
    // red. That is the substring trap in a fresh costume: a guard cannot be
    // written in the language it bans without excluding the place it is
    // written. Tests do not ship, so excluding them costs nothing real.
    expect(gitGrep("from 'pdfkit'", SRC_ONLY)).toEqual([]);
    expect(gitGrep("require('pdfkit')", SRC_ONLY)).toEqual([]);
    // `pdf-lib` is a DELIBERATE exception and is named rather than silently
    // permitted: `pdf-native/export.ts` fills the doctor's OWN certified page
    // and is a different product surface, not a styled re-creation. It is the
    // one live producer this gate does not converge, by ruling #113's scope.
    const pdfLib = gitGrep("from 'pdf-lib'", SRC_ONLY);
    expect(
      pdfLib.every((h) => h.includes('pdf-native/') || h.includes('template-twin/')),
      `pdf-lib is used outside the native-fill surfaces:\n  ${pdfLib.join('\n  ')}`,
    ).toBe(true);
  });

  it('CONTROL — the same needle shapes DO find the surviving builder', () => {
    // Proves the four assertions above are discriminating rather than agreeing.
    // A typo in a needle produces [] just as convincingly as a clean tree.
    expect(gitGrep('await generateVisitDocx(', "'src' 'tests'").length).toBeGreaterThan(3);
    expect(gitGrep("from '../docx-generator'", "'src'").length).toBeGreaterThan(0);
  });
});

describe('F3 — every route that emits a visit PDF reaches the ONE renderer', () => {
  // ⚠️ THE WATCHED SET IS #116's CENSUS, BY JOB. Three sites converge; two were
  // deleted because they rendered a signed note only to read `.byteLength` into
  // a write-only column. Both halves are asserted — a set that only checks the
  // survivors cannot notice the deleted ones coming back.
  const CONVERGED = [
    'src/app/api/visits/[id]/export/pdf/route.ts',
    'src/app/api/patients/[id]/export/route.ts',
    'src/app/api/settings/export-data/route.ts',
  ];
  const DELETED_OUTRIGHT = [
    'src/app/api/visits/[id]/sign/route.ts',
    'src/app/api/visits/[id]/export/email/route.ts',
  ];

  it('each converged caller imports the shared renderer', () => {
    for (const rel of CONVERGED) {
      const src = readFileSync(`${APP_ROOT}/${rel}`, 'utf8');
      // Non-vacuity first: an unreadable or moved file must not pass by being
      // empty. Every one of these is a real route with real content.
      expect(src.length, `${rel} read as empty`).toBeGreaterThan(500);
      expect(src, `${rel} does not reach the shared PDF renderer`).toContain(
        "from '@/lib/visit-pdf'",
      );
      expect(src, `${rel} imports the renderer but never calls it`).toContain(
        'renderVisitPdf(',
      );
    }
  });

  it('⚠️ the two DELETED sites render no PDF at all — #116(b) stays executed', () => {
    // The failure this catches is a well-meaning future edit "restoring" the
    // delivery size, which would put a Gotenberg network round-trip inside
    // POST /sign for a column nothing reads.
    for (const rel of DELETED_OUTRIGHT) {
      const src = readFileSync(`${APP_ROOT}/${rel}`, 'utf8');
      expect(src.length, `${rel} read as empty`).toBeGreaterThan(500);
      const code = src
        .replace(/\/\*[\s\S]*?\*\//g, ' ')
        .split('\n')
        .map((l) => l.replace(/(^|[^:])\/\/.*$/, '$1'))
        .join('\n');
      // Comments are stripped because both files EXPLAIN the deletion, and an
      // explanation must never redden the guard that its own change created.
      expect(
        code,
        `${rel} renders a PDF again. Ruling #116(b) deleted that render: the ` +
          'document was dropped and only .byteLength kept, for a column with ' +
          'no reader anywhere in the application.',
      ).not.toContain('renderVisitPdf(');
      expect(code).not.toContain('generateVisitPdf(');
    }
  });

  it('CONTROL — the comment stripper does not hide a real call', () => {
    const strip = (t: string) =>
      t.replace(/\/\*[\s\S]*?\*\//g, ' ')
        .split('\n')
        .map((l) => l.replace(/(^|[^:])\/\/.*$/, '$1'))
        .join('\n');
    expect(strip('// we removed renderVisitPdf( here')).not.toContain('renderVisitPdf(');
    expect(strip('const p = await renderVisitPdf(data);')).toContain('renderVisitPdf(');
  });
});

describe('F3 — the renderer REFUSES rather than substituting', () => {
  // ⚠️ THIS IS THE ARM THAT PROTECTS A DOCTOR, and it is why `convertDocxToPdf`'s
  // fail-open contract is translated in `visit-pdf.ts` instead of at each call
  // site. A preview falls back; an export must not.
  const DATA = {
    visitId: 'v_f3',
    patientName: 'F3 Fixture',
    specialty: 'Primary Care',
    chiefComplaint: 'Cough',
    status: 'SIGNED',
    createdAt: new Date('2026-08-01T00:00:00Z'),
    signedAt: new Date('2026-08-01T00:00:00Z'),
    clinicianName: 'Dr. Ada Lovelace',
    clinicianEmail: 'ada@example.test',
    soapText: 'Subjective\nCough.\n\nPlan\nRest.',
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
  } as unknown as VisitExportData;

  it('throws a NAMED error carrying the converter\'s reason — never a DOCX in a PDF\'s clothes', async () => {
    vi.resetModules();
    vi.doMock('../docx-preview/convert', () => ({
      convertDocxToPdf: async () => ({ pdf: null, reason: 'timeout' }),
    }));
    const { renderVisitPdf: subject, VisitPdfUnavailableError: Err } = await import('../visit-pdf');

    await expect(subject(DATA)).rejects.toBeInstanceOf(Err);
    await expect(subject(DATA)).rejects.toMatchObject({ reason: 'timeout' });
    vi.doUnmock('../docx-preview/convert');
    vi.resetModules();
  });

  it('CONTROL — it RESOLVES when the converter succeeds, so the arm above is not vacuous', async () => {
    // ⚠️ A guard proven only in the RED direction is half-proven. Without this,
    // a `renderVisitPdf` that threw unconditionally would satisfy every
    // assertion above while breaking the download for every doctor.
    vi.resetModules();
    vi.doMock('../docx-preview/convert', () => ({
      convertDocxToPdf: async () => ({
        pdf: new Uint8Array([0x25, 0x50, 0x44, 0x46]),
        reason: null,
        flatten: 'applied',
      }),
    }));
    const { renderVisitPdf: subject } = await import('../visit-pdf');

    const out = await subject(DATA);
    expect(out.pdf.subarray(0, 4).toString('ascii')).toBe('%PDF');
    // the outcome travels with the bytes — see the loudness arm in
    // `gate-pdf-flatten-is-loud.test.ts`
    expect(out.flatten).toBe('applied');
    vi.doUnmock('../docx-preview/convert');
    vi.resetModules();
  });

  it('⚠️ a 200 carrying a NON-PDF body is REFUSED, not streamed as application/pdf', async () => {
    // ⚠️ THIS WAS REACHABLE IN THE FIRST DRAFT AND IT IS THE WORST ARTIFACT THE
    // module's own header forbids. `convertDocxToPdf` checks the LENGTH of a 200
    // body and never its CONTENT, so a mis-proxied sidecar answering
    // `200 <html>502 Bad Gateway</html>` produced a non-empty Uint8Array that
    // went straight to the route and out as Content-Type: application/pdf.
    // The doctor downloads a "signed record" that is not a PDF.
    vi.resetModules();
    vi.doMock('../docx-preview/convert', () => ({
      convertDocxToPdf: async () => ({
        pdf: new TextEncoder().encode('<html>502 Bad Gateway</html>'),
        reason: null,
      }),
    }));
    const { renderVisitPdf: subject, VisitPdfUnavailableError: Err } = await import('../visit-pdf');

    await expect(subject(DATA)).rejects.toBeInstanceOf(Err);
    vi.doUnmock('../docx-preview/convert');
    vi.resetModules();
  });

  it('the error type is exported and carries the reason — callers can branch on it', () => {
    // The PDF route returns 503 + the reason on this type specifically. If it
    // stopped being exported, that branch would silently become unreachable and
    // the doctor would get a generic 500 with no guidance.
    const e = new VisitPdfUnavailableError('converter_error');
    expect(e).toBeInstanceOf(Error);
    expect(e.reason).toBe('converter_error');
    expect(e.name).toBe('VisitPdfUnavailableError');
    expect(typeof renderVisitPdf).toBe('function');
  });

  it('the PDF route surfaces the refusal as a NAMED 503, not a bare 500', () => {
    // ⚠️ THIS ARM'S FIRST VERSION WAS A FALSE GREEN, AND ITS OWN MUTATION PROOF
    // IS WHAT SAID SO. It asserted the file CONTAINED `VisitPdfUnavailableError`
    // and a `503` somewhere near an `apiError(`. Neutering the branch to
    // `if (false) {` left both strings exactly where they were — the import
    // line still named the type, the dead block still held the 503 — so the arm
    // passed on a route that had stopped distinguishing a sidecar outage from a
    // crash. Text presence is not behaviour; the CONDITION is what carries the
    // meaning, so the condition is what is asserted.
    const src = readFileSync(
      `${APP_ROOT}/src/app/api/visits/[id]/export/pdf/route.ts`,
      'utf8',
    );
    const code = src
      .replace(/\/\*[\s\S]*?\*\//g, ' ')
      .split('\n')
      .map((l) => l.replace(/(^|[^:])\/\/.*$/, '$1'))
      .join('\n');

    // ⚠️ ONE REGEX, NOT TWO `toContain`s — BOUND TO THE BRANCH.
    // A second draft asserted the condition and, separately, that `503` appeared
    // anywhere in the file. Changing the branch's own `apiError(…, 503)` to 500
    // while any other 503 literal existed would have passed. The status must be
    // matched INSIDE the guarded block.
    expect(
      code,
      'the route no longer BRANCHES on VisitPdfUnavailableError and answer 503 ' +
        'inside that branch, so a sidecar outage reaches the doctor as a ' +
        'generic 500 with no mention of the Word export that still works',
    ).toMatch(/instanceof\s+VisitPdfUnavailableError\s*\)\s*\{[\s\S]{0,600}?503/);
    // Non-vacuity: the stripper must not have returned an empty file.
    expect(code.length, 'the comment stripper ate the route').toBeGreaterThan(1000);
  });
});

// ---------------------------------------------------------------------------
// ⚠️ HONEST LIMITS, RECORDED SO THIS GATE IS NOT READ WIDER THAN IT IS.
//
// 1. THE CONVERSION LEG IS NOT EXERCISED HERE. Every arm above mocks
//    `convertDocxToPdf`. Nothing in this suite posts bytes to Gotenberg, so
//    "the DOCX is clean ⇒ the PDF is clean" — the argument that let
//    `export-cleanliness` and the metadata-PHI arms retire their PDF halves —
//    is an ARGUMENT, not a measurement, and it is stated as one.
//
//    What DOES measure it: `gate-c2b-export-parity.test.ts`'s font block pins
//    the converter image and the deploy that rebuilds it, and the E2E export
//    pack renders through the real sidecar. Neither lives in this file.
//
// 2. IT DOES NOT PROVE THE PDF'S CONTENT MATCHES THE WORD FILE'S. It proves
//    they are produced from ONE set of bytes by ONE converter. That is the
//    structural claim ruling #113 asked for; byte-level content parity across
//    the four surfaces is not asserted anywhere and never was.
//
// 3. THE ROUTE LIST IS HAND-KEPT, which this house knows goes stale. It is
//    #116's census, and the census was taken by traversal — but a SIXTH caller
//    added tomorrow would not appear here on its own. The import-shape arms
//    above are what would catch it reaching for the retired module; a new
//    caller reaching for the RIGHT module and doing the wrong thing with it is
//    not covered.
// ---------------------------------------------------------------------------
