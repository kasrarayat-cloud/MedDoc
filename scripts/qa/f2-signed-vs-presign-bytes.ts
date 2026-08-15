// ============================================================================
// F2 — WHAT DOES SIGNING CHANGE IN THE DOCUMENT? MEASURED IN BYTES.
// ----------------------------------------------------------------------------
// Ruling #114 recorded a signed-vs-pre-sign divergence and WITHDREW both
// proposed mechanisms. Its instruction was explicit: measure, do not theorise.
//
// This is the measurement. It is SYNTHETIC by construction — no visit id, no
// database, no production read. A doctor's note is never a smoke target, and
// F1's `settle-word-numbering.ts` was correctly declined on exactly that
// ground; this probe exists so the question can be answered without it.
//
// WHAT IT DOES. Both surfaces call `previewVisitDocumentAction`, which for
// every production visit reaches the SAME builder by the same route:
//
//     pre-sign : styledDocument(…, cacheable=true )  ─┐
//     signed   : styledDocument(…, cacheable=false)  ─┴→ loadVisitExportData
//                                                        → generateVisitDocx
//
// The signed branch's alternative — serving stored roundtrip-verified native
// bytes — is DEAD in production: 0 fill manifests, measured. So the builder is
// shared, and the only things that can move the bytes are the three
// signed-gated branches INSIDE `loadVisitExportData`:
//
//     :87  body   soapFinal            → signedSoap ?? soapFinal
//     :138 E/M    override?.code??code → signedCode ?? override?.code ?? code
//     :148 date   createdAt            → signedAt ?? createdAt
//
// This probe renders the same underlying row in both states and DIFFS
// `word/document.xml`, one branch at a time, so each is confirmed or refuted on
// its own rather than as a bundle.
//
// ⚠️ IT IS BUILT TO BE ABLE TO SAY "IDENTICAL". The BASELINE scenario carries
// production's actually-measured common shape (body identical, no E/M, signed
// the same day) and MUST render byte-identical. If every scenario reported a
// difference the probe would be measuring its own construction, not the code.
//
// Run:  npx tsx scripts/qa/f2-signed-vs-presign-bytes.ts
// ============================================================================
import JSZip from 'jszip';

import { generateVisitDocx } from '../../apps/transcribe-md/src/lib/docx-generator';
import {
  projectEmForDisplay,
  resolveHeaderFields,
} from '../../apps/transcribe-md/src/lib/visit-export';

const CREATED = new Date('2026-08-10T14:00:00Z');
/** A LATER DAY on purpose — the date branch is invisible when they coincide,
 *  and 26 of production's 27 signed visits coincide. */
const SIGNED_LATER = new Date('2026-08-13T09:30:00Z');

const NOTE = [
  '## POSTOPERATIVE FINDINGS',
  '',
  '1. Alpha finding',
  '2. Beta finding',
  '',
  '## RECOMMENDATIONS',
  '',
  '1. First recommendation',
  '2. Second recommendation',
  '',
].join('\n');

/** A form whose header asks for the DATE OF SURGERY by name. */
const HEADER_FIELDS = [
  { key: 'patient_name', label: 'PATIENT NAME', order: 1 },
  { key: 'date_of_surgery', label: 'DATE OF SURGERY', order: 2 },
] as never;

interface Row {
  soapFinal: string;
  signedSoap: string | null;
  em: { code: string; signedCode?: string } | null;
  headerFields: unknown;
  createdAt: Date;
  signedAt: Date;
}

/** Mirrors `loadVisitExportData`'s projection for the requested state — the
 *  three branches, and nothing else, so a difference is attributable. */
function project(row: Row, signed: boolean) {
  const soapText = signed ? (row.signedSoap ?? row.soapFinal) : row.soapFinal;
  return {
    visitId: 'v_f2',
    patientName: 'F2 Synthetic',
    specialty: 'gastroenterology',
    chiefComplaint: null,
    status: signed ? 'SIGNED' : 'READY',
    createdAt: row.createdAt,
    signedAt: signed ? row.signedAt : null,
    clinicianName: 'Dr Probe',
    clinicianEmail: 'probe@example.invalid',
    soapText,
    icdCodes: [],
    em: projectEmForDisplay(row.em as never, signed, true),
    procedures: [],
    modifiers: [],
    prescriptions: [],
    rxWarnings: [],
    referrals: [],
    patientSummary: null,
    headerFields: resolveHeaderFields(row.headerFields as never, {
      patientName: 'F2 Synthetic',
      // THE BRANCH: `visit.signedAt ?? visit.createdAt`.
      visitDate: signed ? row.signedAt : row.createdAt,
      soapText,
      dictationText: null,
    }),
    formOnly: false,
    formTitle: null,
    formSignature: null,
  } as never;
}

async function documentXml(data: never): Promise<string> {
  const zip = await JSZip.loadAsync(await generateVisitDocx(data));
  return zip.file('word/document.xml')!.async('string');
}

/** ⚠️ `<w:t(?:\s[^>]*)?>` — NOT `<w:t[^>]*>`. The lazy form also matches
 *  `<w:tc>` (table cell) and `<w:tbl>`, whose closing `</w:t>` is the one
 *  belonging to a run INSIDE the cell — so a single cell is captured as one
 *  enormous "visible string" of raw XML. This probe's BASELINE control caught
 *  it on first execution: the control demanded IDENTICAL and reported a
 *  difference between two documents that are byte-identical. The repo's
 *  substring-trap rule, in the probe written to measure a fidelity defect. */
const visibleText = (xml: string) =>
  [...xml.matchAll(/<w:t(?:\s[^>]*)?>([\s\S]*?)<\/w:t>/g)].map((m) => m[1]).join('␟');

/** EVERY delta, not the first.
 *
 *  ⚠️ The first version returned only the earliest difference, and every
 *  scenario reported the SAME one — the signing chrome, which sits above the
 *  note. So the BODY and E/M arms "passed" on a difference that had nothing to
 *  do with body or E/M: a check correct about the wrong quantity, and it would
 *  have stayed green with those branches deleted. */
function deltas(a: string, b: string): string[] {
  const [xa, xb] = [visibleText(a).split('␟'), visibleText(b).split('␟')];
  const out: string[] = [];
  for (let i = 0; i < Math.max(xa.length, xb.length); i++) {
    if (xa[i] !== xb[i]) out.push(`${JSON.stringify(xa[i] ?? null)} → ${JSON.stringify(xb[i] ?? null)}`);
  }
  return out;
}

const BASE: Row = {
  soapFinal: NOTE,
  signedSoap: NOTE,
  em: null,
  headerFields: null,
  createdAt: CREATED,
  signedAt: new Date(CREATED),
};

const SCENARIOS: Array<{ name: string; row: Row; expect: 'identical' | 'differs' }> = [
  // The control. Production's measured common shape: 27 of 27 bodies identical,
  // 21 of 27 with no E/M, 26 of 27 signed the same day.
  { name: 'BASELINE — production’s common shape', row: BASE, expect: 'identical' },
  {
    name: 'BODY — signedSoap differs from soapFinal  (prod: 0 of 27)',
    row: { ...BASE, signedSoap: NOTE.replace('Beta finding', 'Beta finding, revised') },
    expect: 'differs',
  },
  {
    name: 'E/M — signedCode differs from code        (prod: 1 of 27)',
    row: { ...BASE, em: { code: '99215', signedCode: '99214' } },
    expect: 'differs',
  },
  {
    name: 'DATE — DATE OF SURGERY, signed a later day (prod: 0 of 27 today)',
    row: { ...BASE, headerFields: HEADER_FIELDS, signedAt: SIGNED_LATER },
    expect: 'differs',
  },
];

(async () => {
  // ARM 1 — what signing changes on its own, with every content branch held
  // still. Whatever appears here is unconditional: it lands on EVERY visit.
  const baseChrome = deltas(
    await documentXml(project(BASE, false)),
    await documentXml(project(BASE, true)),
  );
  console.log('ARM 1 — signing chrome, on a row where NO content branch fires:');
  for (const d of baseChrome) console.log(`   pre-sign ${d}`);
  console.log(`   (${baseChrome.length} delta(s) — these ride on every signed visit)\n`);

  // ARM 2 — each content branch ISOLATED: signed-with-branch against
  // signed-baseline, so the chrome above cancels and what remains is the
  // branch's own contribution.
  const signedBase = await documentXml(project(BASE, true));
  console.log('ARM 2 — each content branch, isolated from the chrome:');
  for (const s of SCENARIOS.slice(1)) {
    const own = deltas(signedBase, await documentXml(project(s.row, true)));
    console.log(`   ${own.length ? 'differs' : 'IDENTICAL'} — ${s.name}`);
    for (const d of own) console.log(`      ${d}`);
  }
  process.exit(0);
})();
