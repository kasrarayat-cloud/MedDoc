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

/** A `git grep -n` hit line whose match sits in a whole-line comment.
 *
 *  ⚠️ THIS EXISTS BECAUSE THE GATE REDDENED AGAINST ITS OWN AUTHOR ON ITS FIRST
 *  RUN, and the arm that caught it had a comment asserting it could not:
 *  *"the call shape, which no comment in this repo writes."* `gate-c2b`'s
 *  explanatory prose wrote exactly that shape. The stale sentence there was
 *  corrected in the same commit — but relying on "no comment says this" is the
 *  substring trap wearing a promise, so the filter is here as well.
 *
 *  HONEST LIMIT: this is a LINE-level filter. A trailing comment after real
 *  code on the same line is not stripped, which is the conservative direction —
 *  it can only ever report MORE than the truth, never fewer. A false red is a
 *  minute of reading; a false green is a second PDF builder nobody noticed. */
function isCommentLine(hit: string): boolean {
  const text = hit.replace(/^[^:]*:\d+:/, '');
  return /^\s*(\/\/|\*|\/\*)/.test(text);
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
    expect(gitGrep('zzzNoSuchSymbolAnywhereF3zzz', "'src' 'tests'")).toEqual([]);
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
    expect(gitGrep("from '@/lib/pdf-generator'", "'src' 'tests' 'scripts'")).toEqual([]);
    expect(gitGrep("from '../pdf-generator'", "'src' 'tests'")).toEqual([]);
    expect(gitGrep("from './pdf-generator'", "'src'")).toEqual([]);
    // The CALL shape. Comment lines are filtered by `gitGrep` — see the note on
    // `isCommentLine` for the run on which that turned out to be necessary.
    expect(gitGrep('await generateVisitPdf(', "'src' 'tests' 'scripts'")).toEqual([]);
  });

  it('CONTROL — the comment filter does not hide a real CODE hit', () => {
    // The filter above is the kind of leniency that turns a gate into a
    // decoration, so it is pinned in both directions on its own instrument.
    expect(isCommentLine("a.ts:1:  // await generateVisitPdf(data)")).toBe(true);
    expect(isCommentLine("a.ts:1:   * await generateVisitPdf(data)")).toBe(true);
    expect(isCommentLine("a.ts:1:  const p = await generateVisitPdf(data);")).toBe(false);
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
      convertDocxToPdf: async () => ({ pdf: new Uint8Array([0x25, 0x50, 0x44, 0x46]), reason: null }),
    }));
    const { renderVisitPdf: subject } = await import('../visit-pdf');

    const out = await subject(DATA);
    expect(out.subarray(0, 4).toString('ascii')).toBe('%PDF');
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

    expect(
      code,
      'the route no longer BRANCHES on VisitPdfUnavailableError, so a sidecar ' +
        'outage reaches the doctor as a generic 500 with no mention of the ' +
        'Word export that would still have worked',
    ).toMatch(/instanceof\s+VisitPdfUnavailableError/);
    expect(code, 'the named branch does not answer 503').toContain('503');
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
