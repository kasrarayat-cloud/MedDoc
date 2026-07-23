// ============================================================================
// Export cleanliness (Stage 1) — a signed export must read as a physician-
// authored clinical document: NO review-screen machinery, NO markdown
// artifacts, NO bracketed markers. This test RENDERS every export surface
// (styled DOCX, PDF, and all clipboard/email formats) from a note seeded with
// the full forbidden-input set and greps the rendered bytes for the forbidden
// pattern class. It also proves the positives (clean "Not documented." / "—"
// conventions, prescriptions present, Rx warnings absent).
// ============================================================================
import { describe, expect, it } from 'vitest';
import JSZip from 'jszip';
import { extractText, getDocumentProxy } from 'unpdf';

import {
  sanitizeExportedSoap,
  EXPORT_EMPTY_SECTION_TEXT,
  EXPORT_EMPTY_CELL,
  type VisitExportData,
} from '../visit-export';
import { EMPTY_SECTION_PLACEHOLDER } from '../soap-format';
import { generateVisitDocx } from '../docx-generator';
import { generateVisitPdf } from '../pdf-generator';
import { formatForEhr, type EhrFormat } from '../ehr-formatters';

// UNIVERSAL forbidden class — review-screen machinery, placeholder wrappers,
// and bracketed markers that must NEVER appear on ANY export surface.
const FORBIDDEN_UNIVERSAL: Array<{ name: string; re: RegExp }> = [
  { name: 'not-documented bracket', re: /\[not documented\]/i },
  { name: 'underscore-bracket wrapper', re: /_\[|\]_/ },
  { name: 'set-aside language', re: /\bset[ -]aside\b/i },
  { name: 'adopt-before-signing', re: /adopt before signing/i },
  { name: 'All AI-drafted', re: /All AI-drafted/i },
  { name: 'Rx review-before-sending banner', re: /review before sending/i },
  { name: 'Rx severity marker', re: /\[(minor|major|critical)\]/i },
];

// Raw-markdown class — must be absent from the FULLY-RENDERED documents (styled
// DOCX + PDF), whose walkers turn `##`/`**` into real headings/bold. Clipboard
// formats for markdown-rendering EHRs (Athena/eCW/generic) intentionally keep
// markdown — it is rendered by the target EHR, not a literal artifact — so this
// class is asserted only where the surface itself is the finished document.
const FORBIDDEN_MARKDOWN: Array<{ name: string; re: RegExp }> = [
  { name: 'unrendered markdown bold', re: /\*\*/ },
  { name: 'unrendered markdown heading', re: /(^|\n)#{1,6}\s/ },
];

function assertClean(surface: string, rendered: string, opts: { markdown?: boolean } = {}) {
  const set = opts.markdown ? [...FORBIDDEN_UNIVERSAL, ...FORBIDDEN_MARKDOWN] : FORBIDDEN_UNIVERSAL;
  for (const { name, re } of set) {
    expect(re.test(rendered), `${surface} leaked forbidden pattern: ${name}`).toBe(false);
  }
}

// A note carrying every dirty input: an ADOPTED prose section (must survive
// verbatim), a SET-ASIDE section (placeholder), an EMPTY section, and a table
// with a "[not documented]" cell alongside the one inconsistent "—" cell.
const RAW_DIRTY_NOTE = [
  '## SUBJECTIVE',
  'Patient reports three days of productive cough and low-grade fever. Denies chest pain or dyspnea.',
  '',
  '## OBJECTIVE',
  EMPTY_SECTION_PLACEHOLDER,
  '',
  '## ASSESSMENT',
  '',
  '## DIAMETER AND REFLUX TIME — Left Leg',
  '| DIAMETER (mm) | REFLUX TIME (seconds) |',
  '| --- | --- |',
  '| GSV at the SFJ | 4.2 | 0.3 |',
  '| SSV at the Proximal Calf | [not documented] | — |',
  '',
  '## PLAN',
  '1. Supportive care and hydration.',
  '2. Return if symptoms worsen.',
].join('\n');

function fixture(): VisitExportData {
  return {
    visitId: 'v_export_clean',
    patientName: 'Test Patient',
    specialty: 'Primary Care',
    chiefComplaint: 'Cough',
    status: 'SIGNED',
    createdAt: new Date('2026-07-23T00:00:00Z'),
    signedAt: new Date('2026-07-23T00:00:00Z'),
    clinicianName: 'Dr. Ada Lovelace',
    clinicianEmail: 'ada@example.test',
    soapText: sanitizeExportedSoap(RAW_DIRTY_NOTE),
    icdCodes: [
      { code: 'J20.9', description: 'Acute bronchitis, unspecified', evidence_quote: 'cough', confidence: 0.9 },
    ],
    em: null,
    procedures: [],
    modifiers: [],
    prescriptions: [
      {
        drug: 'Amoxicillin',
        strength: '500 mg',
        form: 'capsule',
        sig: '1 PO TID',
        quantity: '30',
        refills: '0',
        action: 'increase',
        evidence_quote: '',
      },
    ],
    // Present in the data (review screen + audit still see them) — must NOT render.
    rxWarnings: [
      { severity: 'critical', rx_drug: 'Amoxicillin', message: 'QTPROLONGATIONXYZ interaction risk', evidence_quote: null },
      { severity: 'major', rx_drug: 'Amoxicillin', message: 'RENALADJUSTXYZ needed', evidence_quote: null },
    ],
    referrals: [],
    patientSummary: null,
    headerFields: [],
    formOnly: false,
  };
}

const EHR_FORMATS: EhrFormat[] = ['epic', 'athena', 'cerner', 'eclinicalworks', 'generic'];

describe('export cleanliness — rendered surfaces carry no forbidden patterns', () => {
  const data = fixture();

  it('DOCX (word/document.xml) is clean and correct', async () => {
    const buf = await generateVisitDocx(data);
    const zip = await JSZip.loadAsync(buf);
    const xml = await zip.file('word/document.xml')!.async('string');
    const text = xml.replace(/<[^>]+>/g, ' ');
    assertClean('docx', text, { markdown: true });
    expect(text).toContain(EXPORT_EMPTY_SECTION_TEXT); // empty/set-aside → "Not documented."
    expect(text).toContain(EXPORT_EMPTY_CELL); // table cell → "—"
    expect(text).toContain('Supportive care'); // adopted PLAN survives verbatim
    expect(text).toContain('Amoxicillin'); // prescription renders
    expect(text).not.toContain('QTPROLONGATIONXYZ'); // Rx warning absent
    expect(text).not.toContain('RENALADJUSTXYZ');
  });

  it('PDF (extracted text) is clean and correct', async () => {
    const buf = await generateVisitPdf(data);
    const pdf = await getDocumentProxy(new Uint8Array(buf));
    const { text } = await extractText(pdf, { mergePages: true });
    const flat = Array.isArray(text) ? text.join('\n') : text;
    assertClean('pdf', flat, { markdown: true });
    expect(flat).toContain('Amoxicillin');
    expect(flat).not.toContain('QTPROLONGATIONXYZ');
    expect(flat).not.toContain('RENALADJUSTXYZ');
  });

  it.each(EHR_FORMATS)('EHR/clipboard format "%s" is clean and correct', (fmt) => {
    const rendered = formatForEhr(fmt, data);
    assertClean(`ehr:${fmt}`, rendered);
    expect(rendered).toContain('Amoxicillin');
    expect(rendered).not.toContain('QTPROLONGATIONXYZ');
    expect(rendered).not.toContain('RENALADJUSTXYZ');
  });
});

describe('sanitizeExportedSoap — presentation-only, never fabricates', () => {
  it('turns a set-aside section into header + "Not documented."', () => {
    const out = sanitizeExportedSoap(`## OBJECTIVE\n${EMPTY_SECTION_PLACEHOLDER}\n`);
    expect(out).toContain('## OBJECTIVE');
    expect(out).toContain(EXPORT_EMPTY_SECTION_TEXT);
    expect(out).not.toContain('All AI-drafted');
  });

  it('turns a genuinely empty section into header + "Not documented."', () => {
    const out = sanitizeExportedSoap('## ASSESSMENT\n\n## PLAN\nx');
    const objBlock = out.split('## PLAN')[0];
    expect(objBlock).toMatch(/## ASSESSMENT\n+Not documented\./);
  });

  it('replaces "[not documented]" table cells with "—" (both legs consistent)', () => {
    const out = sanitizeExportedSoap('| SSV | [not documented] | — |');
    expect(out).toBe('| SSV | — | — |');
    expect(out).not.toMatch(/\[not documented\]/i);
  });

  it('NEVER alters an adopted section — renders its text exactly as today', () => {
    const adopted = '## PLAN\n1. Start lisinopril 10 mg daily.\n2. Recheck in 2 weeks.';
    expect(sanitizeExportedSoap(adopted)).toBe(adopted);
  });

  it('never fabricates content for a section that has real text', () => {
    const out = sanitizeExportedSoap('## SUBJECTIVE\nCough x3 days.');
    expect(out).toBe('## SUBJECTIVE\nCough x3 days.');
    expect(out).not.toContain(EXPORT_EMPTY_SECTION_TEXT);
  });

  it('is idempotent', () => {
    const once = sanitizeExportedSoap(RAW_DIRTY_NOTE);
    expect(sanitizeExportedSoap(once)).toBe(once);
  });
});
