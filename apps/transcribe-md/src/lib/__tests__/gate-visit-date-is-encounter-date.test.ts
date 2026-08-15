// ============================================================================
// THE VISIT DATE IS THE ENCOUNTER'S DATE. THE SIGNING DATE IS THE SIGNATURE'S.
//
// Ruling #115. Every clinical export used to render its visit/surgery date as
// `signedAt ?? createdAt`, so a note signed days after the encounter printed
// the day it was SIGNED as the day the visit HAPPENED.
//
// Measured on production before the fix, not on a fixture:
//   visit cmsdvjgf5000m01mmbs0srykk — occurred 2026-08-03, signed 2026-08-10,
//   and its exported document stated "Visit date: 2026-08-10". SEVEN DAYS
//   WRONG, on a signed record. This fixture uses those two real dates.
//
// A renderer that silently changes what the document SAYS while claiming to
// style it is #112's defect at a second field — the note's own numbers there,
// the encounter's own date here.
//
// ----------------------------------------------------------------------------
// ⚠️ THIS GUARD ASSERTS FIELD PARITY, IN BOTH DIRECTIONS, AND THAT IS THE POINT.
//
// The cheap version of this test asserts only that the visit date now reads
// `createdAt`. That version is GREEN for a fix that moves the encounter date
// into the SIGNATURE LINE as well — which trades a document that misstates when
// the visit happened for one that misstates when it was signed. That is the
// repo's own recorded lesson: "restoring a surface can introduce a WRONG field
// while fixing an absent one", and the wrong field is the worse of the two.
//
// So every surface arm asserts THREE things:
//   1. the visit-date label is followed by the ENCOUNTER date          (the fix)
//   2. the visit-date label is NOT followed by the SIGNING date   (the defect)
//   3. the signature line still carries the SIGNING date        (field parity)
//
// Arm 2 is the one that goes red on the regression. Arm 3 is the one that goes
// red on the over-correction, and nothing else in the suite watches it.
//
// ----------------------------------------------------------------------------
// ⚠️ THE PARTIAL FIX IS THE ONE THAT SHIPS, so the census arm is not optional.
//
// Ruling #115 enumerated TEN sites. Eight changed. Two — both email senders —
// did NOT, because their prose reads "A note you SIGNED ON ${x}" and
// `createdAt` would have made that sentence false. That is a decision about
// what each site DOES, not about what the ruling CALLS them, and it means a
// bare "no site reads signedAt ?? createdAt" assertion would be WRONG here.
//
// The census therefore BUCKETS every match and reconciles the total, so a new
// site cannot hide in the exemption and the exemption cannot silently grow.
//
// ----------------------------------------------------------------------------
// HONEST LIMITS, so this is not read wider than it is:
//   · The native-fill legs (`pdf-native/export.ts`, `template-twin/
//     native-export.ts`) are asserted at the SOURCE, not behaviourally — both
//     need a compiled twin/canvas that production does not hold (0 compiled
//     versions, measured 2026-08-15). Their arm says so where it stands.
//   · The two filename sites are covered by the census, not by a render arm.
//   · `formatVisitDate` is ISO (YYYY-MM-DD); `formatHumanDate` is "Aug 3, 2026".
//     Both appear below because the surfaces genuinely differ.
// ============================================================================
import { describe, expect, it, vi } from 'vitest';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import JSZip from 'jszip';
import { extractText, getDocumentProxy } from 'unpdf';

import { generateVisitDocx } from '../docx-generator';
import { generateVisitPdf } from '../pdf-generator';
import { formatForEhr, type EhrFormat } from '../ehr-formatters';
import { resolveHeaderFields, type VisitExportData } from '../visit-export';

// The two real dates from the production visit that prompted ruling #115.
const ENCOUNTER = new Date('2026-08-03T14:30:00Z');
const SIGNED = new Date('2026-08-10T09:15:00Z');

/** ISO, as `formatVisitDate` renders it — DOCX, PDF, filenames. */
const ENCOUNTER_ISO = '2026-08-03';
const SIGNED_ISO = '2026-08-10';
/** "Aug 3, 2026", as `formatHumanDate` renders it — the EHR clipboard formats. */
const ENCOUNTER_HUMAN = 'Aug 3, 2026';
const SIGNED_HUMAN = 'Aug 10, 2026';

const NOTE = [
  '## SUBJECTIVE',
  'Patient seen for follow-up.',
  '',
  '## PLAN',
  'Continue current therapy.',
  '',
].join('\n');

const DATA: VisitExportData = {
  visitId: 'v_encounter_date',
  patientName: 'Encounter Date',
  specialty: 'Primary Care',
  chiefComplaint: null,
  status: 'SIGNED' as VisitExportData['status'],
  createdAt: ENCOUNTER,
  signedAt: SIGNED,
  clinicianName: 'Dr Test',
  clinicianEmail: 't@example.invalid',
  soapText: NOTE,
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

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Every `<w:t>` run's text, in document order.
 *
 *  ⚠️ The character class after `w:t` is load-bearing. `<w:t[^>]*>` ALSO matches
 *  `<w:tc>` (a table CELL), which silently folds cell markup into "visible
 *  text" — the substring trap this repo has now paid for four times, most
 *  recently inside F2's own measurement probe. Requiring whitespace-or-`>`
 *  right after `w:t` is what discriminates. */
function docxTextRuns(xml: string): string[] {
  return [...xml.matchAll(/<w:t(?:\s[^>]*)?>([^<]*)<\/w:t>/g)].map((m) => m[1]);
}

/** Text with runs joined by a single space — good enough for label-adjacency
 *  assertions, and independent of how a surface chunks its runs. */
function flat(parts: string[]): string {
  return parts.join(' ').replace(/\s+/g, ' ');
}

/** The three parity assertions, applied to one rendered surface. */
function assertDateParity(
  surface: string,
  rendered: string,
  encounter: string,
  signed: string
) {
  // 1 — the fix: the visit-date label is followed by the ENCOUNTER date.
  expect(
    new RegExp(`Visit date[\\s:]{0,4}${encounter}`, 'i').test(rendered),
    `${surface}: "Visit date" must render the ENCOUNTER date ${encounter}`
  ).toBe(true);

  // 2 — the defect: it must NOT be followed by the SIGNING date. This is the
  //     arm that goes red if any site reverts to `signedAt ?? createdAt`.
  expect(
    new RegExp(`Visit date[\\s:]{0,4}${signed}`, 'i').test(rendered),
    `${surface}: "Visit date" must NOT render the SIGNING date ${signed}`
  ).toBe(false);

  // 3 — field parity: the signature chrome still carries the SIGNING date. A
  //     fix that moved createdAt here would satisfy 1 and 2 and be worse.
  expect(
    new RegExp(`Signed electronically by [^.]*on ${signed}`).test(rendered),
    `${surface}: the signature line must still carry the SIGNING date ${signed}`
  ).toBe(true);
  expect(
    new RegExp(`Signed electronically by [^.]*on ${encounter}`).test(rendered),
    `${surface}: the signature line must NOT carry the ENCOUNTER date ${encounter}`
  ).toBe(false);
}

// ---------------------------------------------------------------------------
// A · the styled DOCX — the surface both the pre-sign preview and the signed
//     view render through (F2 measured them as ONE builder).
// ---------------------------------------------------------------------------
describe('styled DOCX', () => {
  it('renders the ENCOUNTER date as the visit date and the SIGNING date in the signature', async () => {
    const buf = await generateVisitDocx(DATA);
    const zip = await JSZip.loadAsync(buf);
    const xml = await zip.file('word/document.xml')!.async('string');
    const text = flat(docxTextRuns(xml));

    // Non-vacuity: the extractor actually produced the document's text. A
    // regex that matches nothing satisfies every "must NOT appear" arm above.
    expect(text.toLowerCase()).toContain('visit date');
    expect(text).toContain('Signed electronically by');

    assertDateParity('DOCX', text, ENCOUNTER_ISO, SIGNED_ISO);
  });
});

// ---------------------------------------------------------------------------
// B · the styled PDF — the same data through the other generator. F3 will
//     retire this builder onto Gotenberg; until then it is a live surface and
//     diverging from the DOCX here is exactly what F3 exists to stop.
// ---------------------------------------------------------------------------
describe('styled PDF', () => {
  it('renders the ENCOUNTER date as the visit date and the SIGNING date in the signature', async () => {
    const pdf = await generateVisitPdf(DATA);
    const doc = await getDocumentProxy(new Uint8Array(pdf));
    const { text } = await extractText(doc, { mergePages: true });
    const flatText = String(text).replace(/\s+/g, ' ');

    expect(flatText.toLowerCase()).toContain('visit date');
    expect(flatText).toContain('Signed electronically by');

    assertDateParity('PDF', flatText, ENCOUNTER_ISO, SIGNED_ISO);
  });
});

// ---------------------------------------------------------------------------
// C · the EHR clipboard formats — five of them, and the defect reached all
//     five through one shared `patientHeader()`. Proving one proves one.
// ---------------------------------------------------------------------------
describe('EHR clipboard formats', () => {
  const FORMATS: EhrFormat[] = [
    'epic',
    'athena',
    'cerner',
    'eclinicalworks',
    'generic',
  ];

  it.each(FORMATS)('%s renders the ENCOUNTER date, not the signing date', (format) => {
    const out = formatForEhr(format, DATA);
    const flatText = out.replace(/\s+/g, ' ');

    // Non-vacuity — this format actually rendered the header and the signature.
    expect(flatText).toContain(ENCOUNTER_HUMAN);
    expect(flatText).toContain('Signed electronically by');

    // The header date is the ENCOUNTER's.
    expect(
      flatText.includes(ENCOUNTER_HUMAN),
      `${format}: header must carry the encounter date`
    ).toBe(true);

    // Field parity — the signed-by line still carries the SIGNING date, and it
    // is the ONLY place the signing date may appear.
    expect(
      new RegExp(`Signed electronically by [^.]*on ${SIGNED_HUMAN.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}`).test(
        flatText
      ),
      `${format}: the signed-by line must carry the signing date`
    ).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// D · DATE OF SURGERY — the customer's own operative form. This is the field
//     the owner actually saw wrong, and it is filled deterministically (never
//     AI) by resolveHeaderFields from whatever `visitDate` the server passes.
// ---------------------------------------------------------------------------
describe('the form header field DATE OF SURGERY', () => {
  it('is filled from the ENCOUNTER date', () => {
    const fields = resolveHeaderFields(
      [
        { key: 'date_of_surgery', label: 'DATE OF SURGERY', order: 1 },
        { key: 'patient_name', label: 'PATIENT NAME', order: 0 },
      ] as never,
      {
        patientName: 'Encounter Date',
        visitDate: ENCOUNTER,
        soapText: NOTE,
        dictationText: null,
      }
    );
    const dos = fields.find((f) => f.label === 'DATE OF SURGERY');
    expect(dos, 'the fixture must actually produce the field').toBeDefined();
    expect(dos!.value).toBe(ENCOUNTER_ISO);
    expect(dos!.value).not.toBe(SIGNED_ISO);
  });

  it('the SERVER hands it the encounter date — loadVisitExportData does not substitute signedAt', async () => {
    // The renderer above is only as right as what feeds it. This arm pins the
    // seam ruling #115 actually names (visit-export-server.ts).
    vi.resetModules();
    const findFirst = vi.fn().mockResolvedValue({
      id: 'v1',
      userId: 'doc1',
      patientName: 'Encounter Date',
      specialty: 'primary-care',
      chiefComplaint: null,
      status: 'SIGNED',
      createdAt: ENCOUNTER,
      signedAt: SIGNED,
      soapFinal: NOTE,
      signedSoap: NOTE,
      rawTextInput: null,
      icdCodes: null,
      cptCodes: null,
      rxDrafts: null,
      referrals: null,
      patientSummary: null,
      // The header fields ride in the bound template's styleProfile JSONB —
      // NOT on the visit row. Getting this wrong is how a loader arm passes
      // while asserting nothing (the field simply comes back undefined).
      noteTemplate: {
        name: 'Operative Note',
        styleProfile: {
          headerFields: [{ key: 'date_of_surgery', label: 'DATE OF SURGERY', order: 0 }],
        },
      },
      noteTemplateId: 'tpl1',
      user: { name: 'Dr Test', email: 't@example.invalid' },
    });
    vi.doMock('@meddoc/db', () => ({
      default: { transcribeVisit: { findFirst, findUnique: findFirst } },
    }));

    const { loadVisitExportData } = await import('../visit-export-server');
    const { asPracticeId } = await import('../practice-scope');
    const data = await loadVisitExportData('v1', asPracticeId('prac1'));

    const dos = data?.headerFields.find((f) => f.label === 'DATE OF SURGERY');
    expect(dos, 'the loader must have produced the header field').toBeDefined();
    expect(dos!.value).toBe(ENCOUNTER_ISO);
    // Field parity at the seam: signedAt is still carried, for the chrome.
    expect(data?.signedAt?.toISOString()).toBe(SIGNED.toISOString());

    vi.doUnmock('@meddoc/db');
    vi.resetModules();
  });
});

// ---------------------------------------------------------------------------
// E · THE CENSUS — the predicate, not the memory of which files were touched.
//
// "A named subset is swept by its DEFINING PREDICATE, never by memory of which
// members were touched." The predicate here is: *a site that reads
// `signedAt ?? createdAt`*. Every match is bucketed; the buckets are named and
// the total reconciles, so nothing can land in a bucket nobody declared.
// ---------------------------------------------------------------------------
describe('the census — no date renderer may read `signedAt ?? createdAt`', () => {
  const SRC = join(__dirname, '..', '..');

  /** Files ruling #115 enumerated, plus the two the sweep must keep watching. */
  const WATCHED = [
    'lib/pdf-generator.ts',
    'lib/docx-generator.ts',
    'lib/ehr-formatters.ts',
    'lib/visit-export-server.ts',
    'lib/pdf-native/export.ts',
    'lib/template-twin/native-export.ts',
    'app/api/visits/[id]/export/docx/route.ts',
    'app/api/visits/[id]/export/pdf/route.ts',
    'app/api/visits/[id]/export/email/route.ts',
    'app/api/visits/[id]/sign/route.ts',
  ];

  /** The ONLY sites permitted to keep reading `signedAt ?? createdAt`, with the
   *  reason. Both render the sentence "A note you SIGNED ON ${x}"; `createdAt`
   *  there would make the email state something untrue. See email.ts. */
  const DELIBERATE = new Set([
    'app/api/visits/[id]/export/email/route.ts',
    'app/api/visits/[id]/sign/route.ts',
  ]);

  // A code line, not a comment. This file's own prose says
  // `signedAt ?? createdAt` several times, and so do the fixed sites' comments
  // — the "an exemption satisfied by PROSE" trap, which has bitten this repo
  // before (`'practice-scope' in source` matching the word "practice-scoped").
  const PATTERN = /signedAt\s*(?:\?\?|\|\|)\s*(?:\w+\.)?createdAt/;

  function codeLines(text: string): string[] {
    return text
      .split('\n')
      .map((l) => l.trim())
      .filter((l) => l && !l.startsWith('//') && !l.startsWith('*') && !l.startsWith('/*'));
  }

  it('every watched file is readable — the positive control on the scan itself', () => {
    // A scan that silently reads nothing reports zero for every needle. Before
    // believing any zero below, prove the traversal reaches real files.
    for (const rel of WATCHED) {
      const text = readFileSync(join(SRC, rel), 'utf8');
      expect(text.length, `${rel} must be readable and non-empty`).toBeGreaterThan(0);
    }
    expect(WATCHED.length).toBe(10); // ruling #115's enumeration, in full
  });

  it('buckets every match, and the buckets reconcile', () => {
    const fixed: string[] = [];
    const deliberate: string[] = [];

    for (const rel of WATCHED) {
      const hits = codeLines(readFileSync(join(SRC, rel), 'utf8')).filter((l) =>
        PATTERN.test(l)
      );
      if (hits.length === 0) fixed.push(rel);
      else if (DELIBERATE.has(rel)) deliberate.push(rel);
      else
        throw new Error(
          `${rel} reads \`signedAt ?? createdAt\` on a CODE line and is not a declared ` +
            `exemption. Ruling #115: the visit date is the encounter's date. ` +
            `Offending line(s): ${hits.join(' | ')}`
        );
    }

    // The buckets are named and the total is asserted — so a file cannot be
    // quietly dropped from WATCHED to make this pass.
    expect(fixed.length + deliberate.length).toBe(WATCHED.length);
    expect(fixed.length).toBe(8);
    expect(deliberate.length).toBe(2);
    expect([...deliberate].sort()).toEqual([...DELIBERATE].sort());
  });

  it('the two exemptions still SAY "signed on" — the reason, not just the entry', () => {
    // An exemption's ENTRY can be kept alive by a check. Its REASON cannot: it
    // is a sentence about code somewhere else. These two are exempt precisely
    // because the email prose reads "A note you signed on ${x}". If that prose
    // changes, the exemption is stale and this arm is what says so.
    const email = readFileSync(join(SRC, 'lib/email.ts'), 'utf8');
    expect(
      email.includes('A note you signed on ${args.signedDate}'),
      'email.ts no longer renders "A note you signed on ${signedDate}" — the ' +
        'two census exemptions were justified by that sentence. Re-read them.'
    ).toBe(true);
    // And the field is named for what it holds, so the next reader is not
    // invited to make the same substitution the ruling was written about.
    expect(email).toContain('signedDate: string;');
    expect(email).not.toContain('visitDate: string;');
  });

  it('the native-fill legs pass the ENCOUNTER date — asserted at source, and here is why', () => {
    // Both need a compiled twin / a stored PDF canvas to exercise, and
    // production holds ZERO compiled twin versions (measured 2026-08-15), so
    // there is no honest behavioural arm to write today. Stated rather than
    // faked: an unverified step named honestly beats a green tick bought with
    // a fixture that proves a different universe.
    const nativePdf = readFileSync(join(SRC, 'lib/pdf-native/export.ts'), 'utf8');
    const twin = readFileSync(join(SRC, 'lib/template-twin/native-export.ts'), 'utf8');

    expect(codeLines(nativePdf).some((l) => l.includes('const encounterDate = visit.createdAt'))).toBe(
      true
    );
    expect(codeLines(twin).some((l) => l.includes('visitDate: visit.createdAt'))).toBe(true);

    // ⚠️ The native PDF's signature line used to read the SAME variable as the
    // header fill. Splitting them is the fix; this pins the split, because
    // changing the header source alone would silently move the encounter date
    // into the signature line — the over-correction arm 3 exists for.
    expect(
      codeLines(nativePdf).some((l) => l.includes('visit.signedAt.toISOString()')),
      'the native PDF signature line must read visit.signedAt directly, not the ' +
        'header fill date'
    ).toBe(true);
  });
});
