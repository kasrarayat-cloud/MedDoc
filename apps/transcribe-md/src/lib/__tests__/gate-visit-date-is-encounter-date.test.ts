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
// ⚠️ WHAT `createdAt` ACTUALLY IS, SAID PLAINLY SO THE NEXT READER IS NOT MISLED.
//
// There is NO `encounterDate` column on `TranscribeVisit` and never has been.
// `createdAt` is `@default(now())`, set when the doctor SUBMITS THE NEW-VISIT
// FORM — before any audio exists. So the honest claim this guard enforces is:
//
//     the visit date is the date the visit was OPENED, not the date it was
//     SIGNED — a strict improvement, and not literally the encounter date.
//
// It is the best available proxy and it is right for the overwhelming majority
// (a visit is opened and recorded in one sitting). Two known skews, both
// recorded rather than hidden:
//   · `inputMode: 'audio_upload'` — uploading last Tuesday's dictation stamps
//     today. Still closer than `signedAt`, so not a regression.
//   · a visit opened during clinic prep and recorded the next day makes
//     `createdAt` PRECEDE the encounter — the one direction where the new value
//     can be worse than the old. Bounded at ~48h by the stale-visit sweep.
// A real encounter-date column is the proper long-term answer; it is a schema
// question, not a renderer one, and is noted for the war room in ruling #115.
//
// ----------------------------------------------------------------------------
// ⚠️ THIS GUARD ASSERTS FIELD PARITY, IN BOTH DIRECTIONS, AND THAT IS THE POINT.
//
// The cheap version asserts only that the visit date now reads `createdAt`.
// That version is GREEN for a fix that moves the encounter date into the
// SIGNATURE LINE as well — trading a document that misstates when the visit
// happened for one that misstates when it was signed. The repo's own lesson:
// "restoring a surface can introduce a WRONG field while fixing an absent one",
// and the wrong field is the worse of the two.
//
// So every surface arm asserts:
//   1. the visit-date label is followed by the ENCOUNTER date          (the fix)
//   2. the visit-date label is NOT followed by the SIGNING date   (the defect)
//   3. the signature line still carries the SIGNING date        (field parity)
//   4. the signature line does NOT carry the encounter date  (over-correction)
//
// ⚠️ ARMS 3 AND 4 WERE ONCE BOUGHT WITH A FIXTURE SHAPE PRODUCTION DOES NOT
// HOLD. They matched `Signed electronically by [^.]*on <date>` — and `[^.]*`
// cannot cross the period in a real clinician name. With `Dr. Test` (the shape
// production actually carries) arm 3 went RED on fully-correct code and arm 4
// was VACUOUS: it could never fail, for the exact regression it exists to
// catch. The fixture is now period-bearing and the name is escaped INTO the
// regex rather than wildcarded over.
//
// ----------------------------------------------------------------------------
// ⚠️ FOUR FALSE GREENS WERE DEMONSTRATED AGAINST THE FIRST VERSION OF THIS FILE
// by an adversarial pass, every one a one-line edit. They are named at the
// census block below, because the repairs are the interesting part.
//
// HONEST LIMITS, so this is not read wider than it is:
//   · The two native-fill legs have NO behavioural arm — they need a stored PDF
//     canvas / a compiled twin. ⚠️ The earlier excuse for that cited "zero
//     compiled twin versions", which is a measurement of a DIFFERENT mechanism:
//     `pdf-native` is LIVE in production. Real gap, real path.
//   · `formatVisitDate` is UTC-truncating (`toISOString().slice(0,10)`) while
//     every in-app date renderer is LOCAL. An evening encounter can print the
//     next day in the document and the current day on screen. PRE-EXISTING and
//     not introduced here — but this change makes the field a claim a doctor
//     will check against a schedule, so it is now load-bearing. The fixtures
//     below sit mid-day UTC and therefore CANNOT come out false on it.
// ============================================================================
import { describe, expect, it, vi } from 'vitest';
import { readFileSync, readdirSync } from 'node:fs';
import { join, relative, sep } from 'node:path';
import JSZip from 'jszip';

import { generateVisitDocx } from '../docx-generator';
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

/** ⚠️ PERIOD-BEARING ON PURPOSE — this is the shape production carries, and the
 *  previous fixture's `Dr Test` was what made arms 3 and 4 pass. */
const CLINICIAN = 'Dr. Test';

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
  clinicianName: CLINICIAN,
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

function esc(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

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

function flat(parts: string[]): string {
  return parts.join(' ').replace(/\s+/g, ' ');
}

/** The four parity assertions, applied to one rendered surface. */
function assertDateParity(
  surface: string,
  rendered: string,
  encounter: string,
  signed: string
) {
  expect(
    new RegExp(`Visit date[\\s:]{0,4}${esc(encounter)}`, 'i').test(rendered),
    `${surface}: "Visit date" must render the ENCOUNTER date ${encounter}`
  ).toBe(true);

  expect(
    new RegExp(`Visit date[\\s:]{0,4}${esc(signed)}`, 'i').test(rendered),
    `${surface}: "Visit date" must NOT render the SIGNING date ${signed}`
  ).toBe(false);

  // ⚠️ The clinician name is escaped INTO the pattern. The old `[^.]*` could
  // not cross the period in "Dr. Test" — arm 3 false-RED, arm 4 vacuous.
  const sigLine = `Signed electronically by ${esc(CLINICIAN)} on `;
  expect(
    new RegExp(`${sigLine}${esc(signed)}`).test(rendered),
    `${surface}: the signature line must still carry the SIGNING date ${signed}`
  ).toBe(true);
  expect(
    new RegExp(`${sigLine}${esc(encounter)}`).test(rendered),
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

    // Non-vacuity: the extractor actually produced the document's text.
    expect(text.toLowerCase()).toContain('visit date');
    expect(text).toContain('Signed electronically by');

    assertDateParity('DOCX', text, ENCOUNTER_ISO, SIGNED_ISO);
  });
});

// ---------------------------------------------------------------------------
// B · the styled PDF — RETIRED WITH THE SECOND GENERATOR (ruling #113).
// ---------------------------------------------------------------------------
// This block rendered `generateVisitPdf` and asserted the same date parity the
// DOCX block above asserts. There is no longer "the other generator": the PDF
// download is LibreOffice's render of the DOCX block A just checked, so the two
// arms had become one assertion written twice.
//
// ⚠️ THIS IS NOT A COVERAGE REDUCTION FOR RULING #115, AND THE REASON MATTERS.
// #115's ten sites are all in code that builds the DOCX or the clipboard text;
// none of them lived in the PDF builder alone. Block A still fails if any of
// them regresses.

// ---------------------------------------------------------------------------
// C · the EHR clipboard formats — five of them, reached through ONE shared
//     `patientHeader()`. Proving one proves one.
// ---------------------------------------------------------------------------
describe('EHR clipboard formats', () => {
  const FORMATS: EhrFormat[] = ['epic', 'athena', 'cerner', 'eclinicalworks', 'generic'];

  it.each(FORMATS)('%s renders the ENCOUNTER date, not the signing date', (format) => {
    const out = formatForEhr(format, DATA);
    const flatText = out.replace(/\s+/g, ' ');

    // Non-vacuity — this format actually rendered a header and a signature.
    expect(flatText).toContain(ENCOUNTER_HUMAN);
    expect(flatText).toContain('Signed electronically by');

    // ⚠️ THE REAL NEGATIVE ARM. The previous version had TWO assertions with
    // ONE predicate — `includes(ENCOUNTER_HUMAN)` stated twice — and no
    // "must not carry the signing date" check at all. The regression was
    // caught only by accident, through the non-vacuity line above.
    //
    // The header is the text BEFORE the signature block, so the signing date
    // must not appear in it while still appearing in the signed-by line.
    const sigIdx = flatText.indexOf('Signed electronically by');
    const header = flatText.slice(0, sigIdx);
    expect(
      header.includes(ENCOUNTER_HUMAN),
      `${format}: the header must carry the encounter date`
    ).toBe(true);
    expect(
      header.includes(SIGNED_HUMAN),
      `${format}: the header must NOT carry the signing date`
    ).toBe(false);

    // Field parity — the signed-by line still carries the SIGNING date.
    expect(
      new RegExp(`Signed electronically by ${esc(CLINICIAN)} on ${esc(SIGNED_HUMAN)}`).test(
        flatText
      ),
      `${format}: the signed-by line must carry the signing date`
    ).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// D · DATE OF SURGERY — the customer's own operative form. This is the field
//     the owner actually saw wrong.
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
      // while asserting nothing (the field comes back undefined).
      noteTemplate: {
        name: 'Operative Note',
        styleProfile: {
          headerFields: [{ key: 'date_of_surgery', label: 'DATE OF SURGERY', order: 0 }],
        },
      },
      noteTemplateId: 'tpl1',
      user: { name: CLINICIAN, email: 't@example.invalid' },
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
    expect(data?.signedAt?.toISOString()).toBe(SIGNED.toISOString());

    vi.doUnmock('@meddoc/db');
    vi.resetModules();
  });
});

// ---------------------------------------------------------------------------
// D2 · THE FORM-ONLY SHAPE — and it is here because the fixture above CANNOT
//      express it, which is the wrong-universe class in its proof-side form.
//
// ⚠️ Arms A and B assert a "Visit date" row that `renderPatientBlock` emits
// only in the ELSE of `headerFields.length > 0`. On the template that prompted
// ruling #115 — which HAS header fields, and is form-only — that row never
// renders, and the QuillMD signature footer arms 3/4 key on is replaced by the
// form's own block. So the surfaces the customer actually receives were, until
// this arm, covered by nothing that renders a document.
//
// This is also where ruling #115-b lives: DD (dictation) and DT (transcription)
// are ENCOUNTER-adjacent dates that were rendering `signedAt`, so #115's own
// fix left the operative form asserting the procedure happened on the 3rd and
// was dictated on the 10th. A self-contradicting clinical form is worse than a
// uniformly wrong one.
// ---------------------------------------------------------------------------
describe('form-only export — the customer operative form', () => {
  const FORM_DATA: VisitExportData = {
    ...DATA,
    formOnly: true,
    formTitle: 'Operative Note',
    formSignature: { dd: true, dt: true },
    headerFields: [{ label: 'DATE OF SURGERY', value: ENCOUNTER_ISO }],
  };

  it('DOCX: DATE OF SURGERY, DD and DT all carry the ENCOUNTER date; only the attestation carries the SIGNING date', async () => {
    const buf = await generateVisitDocx(FORM_DATA);
    const zip = await JSZip.loadAsync(buf);
    const xml = await zip.file('word/document.xml')!.async('string');
    const text = flat(docxTextRuns(xml));

    // Non-vacuity: the form-only branch really did render its own block.
    expect(text).toContain('DATE OF SURGERY');
    expect(text).toContain('DD:');
    expect(text).toContain('DT:');
    expect(text).toContain('Electronically Signed');

    expect(text).toContain(`DD: ${ENCOUNTER_ISO}`);
    expect(text).toContain(`DT: ${ENCOUNTER_ISO}`);
    // The defect: the dictation lines must not claim the signing day.
    expect(text).not.toContain(`DD: ${SIGNED_ISO}`);
    expect(text).not.toContain(`DT: ${SIGNED_ISO}`);
    // Field parity: the attestation still carries the signing date, and it is
    // the ONLY place the signing date is allowed to appear on this form.
    expect(
      new RegExp(`Electronically Signed – ${esc(CLINICIAN)}\\s+${esc(SIGNED_ISO)}`).test(text),
      'the form attestation must carry the SIGNING date'
    ).toBe(true);
    expect(
      (text.match(new RegExp(esc(SIGNED_ISO), 'g')) ?? []).length,
      'the signing date must appear EXACTLY once on a form-only export — in the attestation'
    ).toBe(1);
  });

  // The PDF form arm retired with the second generator (ruling #113) — same
  // reasoning as block B. `formSignatureLines` is shared, and the DOCX arm
  // directly above exercises it, so #115-b's `DD:`/`DT:` fix is still gated.
});

// ---------------------------------------------------------------------------
// E · THE CENSUS — the predicate, not the memory of which files were touched.
//
// ⚠️ THE FIRST VERSION OF THIS BLOCK CLAIMED EXACTLY THAT AND IMPLEMENTED CLOSER
// TO THE OPPOSITE. A refutation pass demonstrated FOUR false greens against it,
// each a one-line edit and none of them exotic:
//
//   · the TERNARY   `signedAt ? signedAt : createdAt`   — the pattern missed it
//   · a LINE BREAK  `signedAt ??\n  createdAt`          — the scan was per-line,
//     and that is simply what Prettier emits one nesting level deeper
//   · a NEW FILE rendering a visit date                 — WATCHED is hand-kept
//   · moving the CONSUMPTION one hop while leaving the grepped marker line in
//     place — the source arms asserted TEXT PRESENCE, not what is passed
//
// The last is the worst: it re-broke DATE OF SURGERY, the field the owner
// actually saw wrong, with all thirteen arms green.
//
// So this block now matches comment-stripped source with NEWLINES COLLAPSED,
// covers the ternary as well as `??`/`||`, DISCOVERS candidate files by walking
// the tree instead of trusting a list, and asserts CONSUMPTION on the native
// legs rather than the presence of a string.
//
// ⚠️ AND THE BUCKET TOTALS ARE DERIVED, NOT MAGIC NUMBERS. `toBe(8)` meant that
// adding a legitimately-correct new file to WATCHED turned the guard RED until
// two constants were also edited — so the cheapest response was to leave the
// new file out. A guard whose path of least resistance is "don't watch it" is a
// guard that shrinks.
// ---------------------------------------------------------------------------
describe('the census — no date renderer may fall back to the signing date', () => {
  const SRC = join(__dirname, '..', '..');

  /** Ruling #115's ten, plus `lib/form-only.ts` — which the ruling did NOT name
   *  and which the refutation pass found rendering DD:/DT: from `signedAt`
   *  (ruling #115-b). It is here because the sweep that produced the ten could
   *  not see a BARE `signedAt`. */
  const WATCHED = [
    // ⚠️ `lib/pdf-generator.ts` was one of #115's ten and is GONE — retired by
    // ruling #113. It is replaced here rather than merely dropped: shrinking a
    // watched set is how coverage disappears quietly, so the module that now
    // sits on that path takes its slot. `lib/visit-pdf.ts` renders no date
    // today, which is exactly the state this census must keep it in — the day
    // it learns to format one, it is already watched.
    'lib/visit-pdf.ts',
    'lib/docx-generator.ts',
    'lib/ehr-formatters.ts',
    'lib/visit-export-server.ts',
    'lib/pdf-native/export.ts',
    'lib/template-twin/native-export.ts',
    'lib/form-only.ts',
    'app/api/visits/[id]/export/docx/route.ts',
    'app/api/visits/[id]/export/pdf/route.ts',
    'app/api/visits/[id]/export/email/route.ts',
    'app/api/visits/[id]/sign/route.ts',
  ];

  /** The ONLY sites permitted to keep falling back to the signing date. Both
   *  render "A note you SIGNED ON ${x}"; `createdAt` there would make the email
   *  state something untrue. See email.ts. */
  const DELIBERATE = new Set([
    'app/api/visits/[id]/export/email/route.ts',
    'app/api/visits/[id]/sign/route.ts',
  ]);

  /** Every spelling of "fall back from signedAt to createdAt" a formatter, a
   *  refactor or a tired human can produce. The ternary and the line break are
   *  here because both were DEMONSTRATED as false greens, not imagined. */
  const FALLBACK_PATTERNS: Array<{ name: string; re: RegExp }> = [
    { name: 'nullish/or coalesce', re: /signedAt\s*(?:\?\?|\|\|)\s*(?:\w+\.)?createdAt/ },
    { name: 'ternary', re: /signedAt\s*\?[^?:]*:\s*(?:\w+\.)?createdAt/ },
  ];

  /** Comment-stripped, whitespace-collapsed source.
   *
   *  ⚠️ COLLAPSING THE NEWLINES IS THE POINT — the previous version matched
   *  line-by-line, so `signedAt ??\n  createdAt` was invisible to every
   *  pattern. Stripping comments still matters for the opposite reason: this
   *  file's own prose contains the offending expression repeatedly, and an
   *  exemption satisfied by PROSE is a trap this repo has paid for four times. */
  function codeText(text: string): string {
    return text
      .replace(/\/\*[\s\S]*?\*\//g, ' ')
      .split('\n')
      .map((l) => l.replace(/\/\/.*$/, ''))
      .join('\n')
      .replace(/\s+/g, ' ');
  }

  function hits(text: string): string[] {
    const flatSrc = codeText(text);
    return FALLBACK_PATTERNS.filter((p) => p.re.test(flatSrc)).map((p) => p.name);
  }

  it('the scan discriminates — positive AND negative control on its own patterns', () => {
    // A pattern proven only against the shape it was written for has agreed
    // with its author. Each must fire on its own spelling and stay silent on
    // correct code and on prose.
    expect(
      hits('const d = visit.signedAt ??\n      visit.createdAt;'),
      'a line-broken ?? must be caught'
    ).toContain('nullish/or coalesce');
    expect(
      hits('const d = visit.signedAt ? visit.signedAt : visit.createdAt;'),
      'a ternary must be caught'
    ).toContain('ternary');
    expect(hits('const d = visit.createdAt;'), 'correct code must not match').toEqual([]);
    expect(
      hits('// this used to read signedAt ?? createdAt before #115'),
      'a COMMENT must never satisfy the census'
    ).toEqual([]);
  });

  it('every watched file is readable — the positive control on the traversal', () => {
    for (const rel of WATCHED) {
      expect(
        readFileSync(join(SRC, rel), 'utf8').length,
        `${rel} must be readable and non-empty`
      ).toBeGreaterThan(0);
    }
  });

  it('buckets every match, and the buckets reconcile — totals DERIVED', () => {
    const fixed: string[] = [];
    const deliberate: string[] = [];

    for (const rel of WATCHED) {
      const found = hits(readFileSync(join(SRC, rel), 'utf8'));
      if (found.length === 0) fixed.push(rel);
      else if (DELIBERATE.has(rel)) deliberate.push(rel);
      else
        throw new Error(
          `${rel} falls back to the SIGNING date (${found.join(', ')}) and is not a ` +
            `declared exemption. Ruling #115: the visit date is the encounter's date.`
        );
    }

    expect(fixed.length + deliberate.length).toBe(WATCHED.length);
    expect(deliberate.length).toBe(DELIBERATE.size);
    expect(fixed.length).toBe(WATCHED.length - DELIBERATE.size);
    expect([...deliberate].sort()).toEqual([...DELIBERATE].sort());
  });

  it('DISCOVERS date-rendering files by walking the tree — WATCHED cannot go stale', () => {
    // ⚠️ THE HAND-KEPT LIST IS THE FAILURE MODE THIS ARM EXISTS FOR. A new file
    // that falls back to the signing date is invisible to a fixed list, and
    // "a per-caller list is kept complete by hand, and hand-kept lists are
    // wrong eventually". So: walk the tree, and require every offender to be
    // WATCHED. The list stops being a promise and becomes a consequence.
    const stack = [SRC];
    const offenders: string[] = [];
    let scanned = 0;
    while (stack.length) {
      const dir = stack.pop()!;
      for (const ent of readdirSync(dir, { withFileTypes: true })) {
        const full = join(dir, ent.name);
        if (ent.isDirectory()) {
          if (ent.name === 'node_modules' || ent.name === '__tests__') continue;
          stack.push(full);
        } else if (/\.tsx?$/.test(ent.name) && !/\.test\.tsx?$/.test(ent.name)) {
          scanned += 1;
          if (hits(readFileSync(full, 'utf8')).length) {
            offenders.push(relative(SRC, full).split(sep).join('/'));
          }
        }
      }
    }

    // Non-vacuity: a traversal that covers nothing returns zero offenders and
    // looks exactly like success.
    expect(scanned, 'the tree walk must reach real source files').toBeGreaterThan(300);

    expect(
      offenders.filter((f) => !WATCHED.includes(f)),
      'these files fall back to the SIGNING date and nothing watches them — ' +
        'add them to WATCHED (and fix them). Ruling #115.'
    ).toEqual([]);
    expect(
      offenders.filter((f) => !DELIBERATE.has(f)),
      'every surviving offender must be a declared exemption'
    ).toEqual([]);
  });

  it('the two exemptions still SAY "signed on" — the reason, not just the entry', () => {
    // A gate can keep an exemption PRESENT. It cannot keep it HONEST: the
    // reason is a sentence about code somewhere else.
    const email = readFileSync(join(SRC, 'lib/email.ts'), 'utf8');
    expect(
      email.includes('A note you signed on ${args.signedDate}'),
      'email.ts no longer renders "A note you signed on ${signedDate}" — the ' +
        'two census exemptions were justified by that sentence. Re-read them.'
    ).toBe(true);
    expect(email).toContain('signedDate: string;');
    expect(email).not.toContain('visitDate: string;');
  });

  it('the native-fill legs pass the encounter date BY CONSUMPTION, not by a marker', () => {
    // ⚠️ THIS ARM REPLACES A DEMONSTRATED FALSE GREEN. It used to assert that a
    // line containing `const encounterDate = visit.createdAt` existed. Keeping
    // that line and passing something else one hop later —
    //     const headerDate = visit.signedAt ? visit.signedAt : visit.createdAt;
    //     visitDate: headerDate,
    // — left all thirteen arms green while DATE OF SURGERY rendered the signing
    // date again. Presence of a string is not consumption of a value.
    //
    // HONEST LIMIT: these two legs still have no BEHAVIOURAL arm — pdf-native
    // needs a stored PDF canvas, the twin a compiled version. ⚠️ The earlier
    // excuse cited "zero compiled TWIN versions", which measures a DIFFERENT
    // mechanism: pdf-native is LIVE in production, with certified templates and
    // signed visits bound to them. A real gap on a real path.
    const nativePdf = codeText(readFileSync(join(SRC, 'lib/pdf-native/export.ts'), 'utf8'));
    const twin = codeText(readFileSync(join(SRC, 'lib/template-twin/native-export.ts'), 'utf8'));

    const bind = /const\s+(\w+)\s*=\s*visit\.createdAt\s*;/.exec(nativePdf);
    expect(bind, 'pdf-native must bind the encounter date to a named local').not.toBeNull();
    const encounterIdent = bind![1];
    expect(
      new RegExp(`visitDate:\\s*${encounterIdent}\\b`).test(nativePdf),
      `pdf-native must pass ${encounterIdent} (bound to visit.createdAt) as visitDate`
    ).toBe(true);
    expect(
      /visitDate:\s*[^,]*signedAt/.test(nativePdf),
      'pdf-native must not pass any signedAt-derived value as visitDate'
    ).toBe(false);

    expect(/visitDate:\s*visit\.createdAt\b/.test(twin)).toBe(true);
    expect(/visitDate:\s*[^,]*signedAt/.test(twin)).toBe(false);

    // ⚠️ The split is pinned on BOTH sides. The previous version watched only
    // the signature half — which the header-side mutation leaves untouched.
    expect(
      /visit\.signedAt\.toISOString\(\)/.test(nativePdf),
      'the native PDF signature line must read visit.signedAt directly'
    ).toBe(true);
    expect(
      new RegExp(`Electronically signed[^\`]*\\$\\{${encounterIdent}`).test(nativePdf),
      'the native PDF signature line must NOT render the encounter date'
    ).toBe(false);
  });
});
