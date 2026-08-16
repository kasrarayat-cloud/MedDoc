// ============================================================================
// RULING #117(e) — THE ATTESTATION FOOTER, THROUGH THE REAL CONVERTER.
// ----------------------------------------------------------------------------
// #117(e), verbatim: "PROOF: E2E through the REAL converter, because PAGE COUNT
// IS LIBREOFFICE'S — a multi-page unsigned note shows the draft footer on every
// rendered page, a signed one shows the attestation, form-only shows neither
// chrome in both states."
//
// ⚠️ WHY THIS FILE EXISTS WHEN `gate-attestation-footer.test.ts` ALREADY PASSES.
// That guard is STRUCTURAL: it reads `word/footer1.xml` and the section's
// `w:footerReference w:type`. It is a good guard and it records its own limit in
// as many words — its fixture is ONE PAGE, so "on every page" is asserted over a
// set of size ONE, and `w:type="default"` is a PROXY for what LibreOffice paints.
//
//   A proxy is a claim about a renderer nobody ran.
//
// This file removes the proxy. It builds a genuinely MULTI-PAGE document, sends
// it through the REAL Gotenberg/LibreOffice, and reads the text off EVERY PAGE
// of the rendered PDF. Page count is LibreOffice's, which is the whole reason
// #117(e) asked for it: nothing in the OOXML says how many pages there are.
//
// ⚠️ THE (a)/(e) CONFLICT — THIS FILE FOLLOWS #118(a), AND IT IS LOAD-BEARING.
// #117(e) as literally written says form-only "shows neither chrome IN BOTH
// STATES" (signed AND unsigned). #117(a) says the draft footer lands on every
// page "INCLUDING FORM-ONLY". They contradict. Ruling #118(a) resolved it in
// favour of (a) — it is the emphatic clause, it carries the reachability
// verification, and the tie-break is safety direction: (a) marks MORE.
//
// So the UNSIGNED FORM-ONLY arm below asserts the draft footer IS present, which
// is the OPPOSITE of what (e)'s sentence says. #118(a) predicted exactly this
// ("as (e) is literally written, building its E2E would go RED against this
// implementation") and referred the amendment to the war room. This file is that
// prediction, executed: it is written to #118(a), and the arm is named so the
// war room can invert one assertion if it amends the other way instead.
// ============================================================================
import { describe, expect, it, beforeAll } from 'vitest';
import { extractText, getDocumentProxy } from 'unpdf';

import { generateVisitDocx } from '@/lib/docx-generator';
import {
  DRAFT_FOOTER_LINE,
  signedAttestationLine,
  type VisitExportData,
} from '@/lib/visit-export';

// ---------------------------------------------------------------------------
// The converter. REQUIRED — never skipped.
// ---------------------------------------------------------------------------
// ⚠️ THIS FILE MUST NOT LEARN TO SKIP. A rendered proof that quietly no-ops when
// the sidecar is absent is a green that cannot go red — the decoration class
// this house names on sight. If the converter is unreachable, that is a FAILURE
// of this gate, not a reason to pass it. `beforeAll` health-checks the sidecar
// and throws, so the reason is named once instead of four confusing timeouts.
// ⚠️ THE DEFAULT IS THE IN-NETWORK SERVICE NAME, matching `convert.ts`'s own
// default — because this tier runs INSIDE the `converter` network, not on the
// host. The sidecar's network is `internal: true` and publishing its port is
// both wrong and silently ineffective; see docker-compose.qa.rendered.yml.
const GOTENBERG_URL = process.env.GOTENBERG_URL ?? 'http://gotenberg:3000';
const CONVERT_URL = `${GOTENBERG_URL.replace(/\/$/, '')}/forms/libreoffice/convert`;
const HEALTH_URL = `${GOTENBERG_URL.replace(/\/$/, '')}/health`;

/** LibreOffice cold-starts on the first conversion; a multi-page document is
 *  well inside this but the first call is the slow one. */
const CONVERT_TIMEOUT_MS = 60_000;

async function convert(docx: Uint8Array, filename: string): Promise<Uint8Array> {
  const form = new FormData();
  form.set(
    'files',
    new Blob([docx as unknown as BlobPart], {
      type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    }),
    filename
  );
  const res = await fetch(CONVERT_URL, {
    method: 'POST',
    body: form,
    signal: AbortSignal.timeout(CONVERT_TIMEOUT_MS),
  });
  if (!res.ok) {
    throw new Error(
      `the REAL converter refused ${filename}: HTTP ${res.status}. ` +
        'This gate FAILS rather than skips — see the header.'
    );
  }
  const pdf = new Uint8Array(await res.arrayBuffer());
  if (pdf.byteLength === 0) throw new Error(`converter returned 0 bytes for ${filename}`);
  return pdf;
}

// ---------------------------------------------------------------------------
// The fixture — deliberately long enough that LIBREOFFICE paginates it.
// ---------------------------------------------------------------------------
const SIGNED_AT = new Date('2026-08-15T00:00:00Z');
const CLINICIAN = 'Dr Test';

/** A line from the note BODY. The non-vacuity control for every arm: it proves
 *  the page carries the document, so "no chrome here" can never be satisfied by
 *  a blank or failed render. */
const BODY_MARKER = 'Alpha finding recorded at the bedside';

/** ⚠️ THE FLOOR THAT MAKES "EVERY PAGE" MEAN SOMETHING. Asserted, not hoped:
 *  a fixture that collapsed to one page would make every per-page loop below
 *  trivially true, which is precisely the weakness of the structural guard this
 *  file exists to remove. Three is the smallest count that has a genuine
 *  interior page — first, middle and last are all distinct cases. */
const MIN_PAGES = 3;

/** Long-form findings. Each paragraph is individually addressable so a failure
 *  message can say WHICH page lost its marking. */
function multiPageSoap(): string {
  const paras: string[] = [`## FINDINGS`, ``, BODY_MARKER, ``];
  for (let i = 1; i <= 40; i++) {
    paras.push(
      `Paragraph ${i}. The examination was carried out with the patient supine ` +
        'and the transducer applied in the standard planes. Measurements were ' +
        'obtained in triplicate and averaged. No acute abnormality was ' +
        'identified in the surveyed structures, and the appearances are within ' +
        'expected limits for the stated indication and patient demographic.',
      ''
    );
  }
  return paras.join('\n');
}

function data(over: Partial<VisitExportData>): VisitExportData {
  return {
    visitId: 'v_footer_rendered',
    patientName: 'Footer Fixture',
    specialty: 'gastroenterology',
    chiefComplaint: null,
    status: 'READY',
    createdAt: new Date('2026-08-10T00:00:00Z'),
    signedAt: null,
    clinicianName: CLINICIAN,
    clinicianEmail: 't@example.invalid',
    soapText: multiPageSoap(),
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

interface Rendered {
  pageCount: number;
  /** Per-page visible text, whitespace-normalised. Index 0 is page 1. */
  pages: string[];
}

/** Build → convert → read back, per page. */
async function render(label: string, over: Partial<VisitExportData>): Promise<Rendered> {
  const docx = await generateVisitDocx(data(over));
  const pdf = await convert(new Uint8Array(docx), `${label}.docx`);
  const doc = await getDocumentProxy(pdf);
  const { text } = await extractText(doc, { mergePages: false });
  const pages = (Array.isArray(text) ? text : [String(text)]).map((t) =>
    String(t).replace(/\s+/g, ' ').trim()
  );

  // ⚠️ THE TWO COUNTS MUST AGREE. `numPages` comes from the PDF catalogue and
  // the array from the text extractor; if they ever disagree, a per-page loop
  // silently covers a subset and reports success over it.
  expect(
    pages.length,
    `${label}: extractor returned ${pages.length} pages, catalogue says ${doc.numPages}`
  ).toBe(doc.numPages);

  return { pageCount: doc.numPages, pages };
}

/** Assert `needle` appears on EVERY page, naming the pages that lack it. */
function onEveryPage(label: string, r: Rendered, needle: string) {
  const missing = r.pages
    .map((p, i) => (p.includes(needle) ? null : i + 1))
    .filter((n): n is number => n !== null);
  expect(
    missing,
    `${label}: "${needle}" missing from page(s) ${missing.join(', ')} of ${r.pageCount}`
  ).toEqual([]);
}

/** Assert `needle` appears on NO page, naming the pages that carry it. */
function onNoPage(label: string, r: Rendered, needle: string) {
  const present = r.pages
    .map((p, i) => (p.includes(needle) ? i + 1 : null))
    .filter((n): n is number => n !== null);
  expect(
    present,
    `${label}: "${needle}" present on page(s) ${present.join(', ')} — expected none`
  ).toEqual([]);
}

// ---------------------------------------------------------------------------

describe('RULING #117(e) — the footer as LIBREOFFICE renders it', () => {
  beforeAll(async () => {
    let ok = false;
    try {
      const res = await fetch(HEALTH_URL, { signal: AbortSignal.timeout(10_000) });
      ok = res.ok;
    } catch {
      ok = false;
    }
    if (!ok) {
      throw new Error(
        `#117(e) REQUIRES the real converter and it is unreachable at ${HEALTH_URL}. ` +
          'This gate fails closed on purpose: a rendered proof that skips when the ' +
          'sidecar is missing is a green that cannot go red. Start the sidecar ' +
          '(docker compose -f docker-compose.qa.yml up -d --wait gotenberg) and set ' +
          'GOTENBERG_URL to a reachable base URL.'
      );
    }
  }, 30_000);

  it(
    'UNSIGNED standard: DRAFT on EVERY rendered page, over a genuinely multi-page document (#117a/e)',
    async () => {
      const r = await render('unsigned-standard', {});

      // ⚠️ THE NON-VACUITY FLOOR, FIRST. Every assertion below is a loop over
      // pages; if the fixture were one page they would all pass while proving
      // nothing beyond what the structural guard already proves.
      expect(
        r.pageCount,
        `the fixture rendered ${r.pageCount} page(s) — "every page" needs a real interior page`
      ).toBeGreaterThanOrEqual(MIN_PAGES);

      onEveryPage('unsigned standard', r, DRAFT_FOOTER_LINE);

      // The body is present — this is a real document, not a blank render.
      expect(r.pages.join(' ')).toContain(BODY_MARKER);

      // ⚠️ AND THE SIGNED ATTESTATION IS NOWHERE. A builder that emitted BOTH
      // footers would satisfy the arm above and ship a draft that also claims a
      // signature.
      onNoPage('unsigned standard', r, signedAttestationLine(CLINICIAN, SIGNED_AT));
    },
    120_000
  );

  it(
    'UNSIGNED form-only: marked too — a draft is a draft on anyone’s paper (#117a, per #118a)',
    async () => {
      // ⚠️ THIS ARM IS THE (a)/(e) CONFLICT, RESOLVED BY #118(a). Read the file
      // header before changing it. If the war room amends #118(a) and rules that
      // (e)'s "neither chrome in both states" governs, this becomes onNoPage and
      // `docx-generator.ts:437-439`'s two guards swap order with it.
      const r = await render('unsigned-form-only', { formOnly: true, formTitle: 'WM IOV' });

      expect(r.pageCount).toBeGreaterThanOrEqual(MIN_PAGES);
      onEveryPage('unsigned form-only', r, DRAFT_FOOTER_LINE);
      expect(r.pages.join(' ')).toContain(BODY_MARKER);
    },
    120_000
  );

  it(
    'SIGNED standard: the attestation on EVERY rendered page, and no DRAFT anywhere (#117b/e)',
    async () => {
      const r = await render('signed-standard', { signedAt: SIGNED_AT });

      expect(r.pageCount).toBeGreaterThanOrEqual(MIN_PAGES);
      onEveryPage('signed standard', r, signedAttestationLine(CLINICIAN, SIGNED_AT));

      // ⚠️ EXACT-STRING, AND THE SUBSTRING TRAP IS THE REASON. `DRAFT_FOOTER_LINE`
      // CONTAINS the in-body 'Not yet signed.' — asserting the shorter string
      // would fail on a correct signed document that happens to carry the in-body
      // phrase, and asserting the longer one is the only honest form.
      onNoPage('signed standard', r, DRAFT_FOOTER_LINE);
    },
    120_000
  );

  it(
    'SIGNED form-only: NO QuillMD chrome on ANY page — the form’s own field IS the attestation (#117c/e)',
    async () => {
      const r = await render('signed-form-only', {
        signedAt: SIGNED_AT,
        formOnly: true,
        formTitle: 'WM IOV',
      });

      expect(r.pageCount).toBeGreaterThanOrEqual(MIN_PAGES);

      // ⚠️ THE POSITIVE CONTROL COMES FIRST, BECAUSE THIS IS AN ABSENCE ARM.
      // "Neither chrome" is satisfied perfectly by a blank page, a failed
      // conversion, or an extractor returning empty strings. Establishing that
      // the document IS here is what makes the two absences mean anything.
      expect(
        r.pages.join(' '),
        'the body is absent — the absence assertions below would be vacuous'
      ).toContain(BODY_MARKER);

      onNoPage('signed form-only', r, DRAFT_FOOTER_LINE);
      onNoPage('signed form-only', r, signedAttestationLine(CLINICIAN, SIGNED_AT));
    },
    120_000
  );

  it(
    'the four cells are DISTINCT as RENDERED — a builder ignoring its inputs cannot pass',
    async () => {
      // Cheap, and it closes the door the structural guard closes at the OOXML
      // level: four cells that rendered identically would satisfy several arms
      // above individually while meaning the builder read none of its inputs.
      expect(DRAFT_FOOTER_LINE).not.toBe(signedAttestationLine(CLINICIAN, SIGNED_AT));
      expect(DRAFT_FOOTER_LINE.startsWith('DRAFT')).toBe(true);
      expect(signedAttestationLine(CLINICIAN, SIGNED_AT)).toContain(CLINICIAN);
    }
  );
});
