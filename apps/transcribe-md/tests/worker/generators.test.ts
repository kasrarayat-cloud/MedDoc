import { describe, expect, it } from 'vitest';
import JSZip from 'jszip';
import type { VisitExportData } from '@/lib/visit-export';
import { generateVisitPdf } from '@/lib/pdf-generator';
import { generateVisitDocx } from '@/lib/docx-generator';

function mkVisit(overrides: Partial<VisitExportData> = {}): VisitExportData {
  return {
    visitId: 'vtest',
    patientName: 'Jane Doe',
    specialty: 'Cardiology',
    chiefComplaint: 'Chest tightness',
    status: 'SIGNED',
    createdAt: new Date('2026-04-19T12:00:00Z'),
    signedAt: new Date('2026-04-19T12:30:00Z'),
    clinicianName: 'Ayesha Khan',
    clinicianEmail: 'akhan@example.com',
    soapText:
      '## Subjective\n**Chief Complaint:** Chest tightness.\n\n## Plan\n1. Increase lisinopril to 20 mg.',
    icdCodes: [
      {
        code: 'I10',
        description: 'Essential (primary) hypertension',
        evidence_quote: 'HTN not at goal',
        confidence: 0.95,
      },
    ],
    em: {
      code: '99214',
      description: 'Established patient, moderate complexity',
      reasoning: {
        problems: [{ description: 'HTN', status: 'unstable' }],
        data: 'reviewed BP log',
        risk: 'moderate',
      },
      evidence_quote: 'Increase lisinopril to 20 mg',
    },
    procedures: [],
    modifiers: [],
    prescriptions: [
      {
        drug: 'Lisinopril',
        strength: '20 mg',
        form: 'tablet',
        sig: 'Take 1 tablet by mouth daily',
        quantity: '90',
        refills: '3',
        action: 'increase',
        evidence_quote: 'Increase lisinopril to 20 mg',
      },
    ],
    rxWarnings: [],
    referrals: [],
    patientSummary: 'Today we talked about your blood pressure…',
    headerFields: [],
    formOnly: false,
    ...overrides,
  };
}

describe('generateVisitPdf', () => {
  it('emits bytes that start with the PDF magic header', async () => {
    const buf = await generateVisitPdf(mkVisit());
    expect(buf.length).toBeGreaterThan(1000);
    expect(buf.subarray(0, 4).toString('ascii')).toBe('%PDF');
  });

  it('tolerates an empty SOAP without crashing', async () => {
    const buf = await generateVisitPdf(mkVisit({ soapText: '' }));
    expect(buf.subarray(0, 4).toString('ascii')).toBe('%PDF');
  });

  it('emits a larger buffer when more sections are populated', async () => {
    const small = await generateVisitPdf(
      mkVisit({
        icdCodes: [],
        procedures: [],
        prescriptions: [],
        referrals: [],
        patientSummary: null,
      })
    );
    const big = await generateVisitPdf(mkVisit());
    expect(big.length).toBeGreaterThan(small.length);
  });
});

describe('generateVisitDocx', () => {
  it('emits a DOCX (zip) payload starting with PK magic header', async () => {
    const buf = await generateVisitDocx(mkVisit());
    expect(buf.length).toBeGreaterThan(1000);
    // DOCX is a zip archive — first two bytes are "PK".
    expect(buf.subarray(0, 2).toString('ascii')).toBe('PK');
  });

  it('handles a visit with only a SOAP and no automation outputs', async () => {
    const buf = await generateVisitDocx(
      mkVisit({
        icdCodes: [],
        em: null,
        procedures: [],
        prescriptions: [],
        referrals: [],
        patientSummary: null,
      })
    );
    expect(buf.subarray(0, 2).toString('ascii')).toBe('PK');
  });
});

// ---------------------------------------------------------------------------
// Structure-aware notes — GitHub-style markdown tables + task lists inside
// section bodies. These smoke-test that the DOCX Table path and the PDF
// vector-checkbox / grid path don't crash and produce well-formed output.
// ---------------------------------------------------------------------------

const STRUCTURED_SOAP = [
  '## Objective',
  '',
  '| Vital | Value |',
  '| --- | --- |',
  '| BP | 148/92 |',
  '| HR | 78 |',
  '',
  '## Plan',
  '- [x] Chaperone offered',
  '- [ ] Interpreter used',
].join('\n');

describe('generateVisitDocx — structure-aware notes', () => {
  it('emits a valid DOCX with a real Word table for markdown tables', async () => {
    const buf = await generateVisitDocx(mkVisit({ soapText: STRUCTURED_SOAP }));
    expect(buf.subarray(0, 2).toString('ascii')).toBe('PK');
    const zip = await JSZip.loadAsync(buf);
    const docXml = await zip.file('word/document.xml')!.async('text');
    // Real Word table markup — <w:tbl> — must be present.
    expect(docXml).toContain('<w:tbl>');
    // Table header + body cell text survives (no literal pipe rows).
    expect(docXml).toContain('148/92');
    expect(docXml).not.toContain('| BP |');
    // Task glyphs are emitted (Word substitutes the font at read time).
    expect(docXml).toContain('☒');
    expect(docXml).toContain('☐');
  });
});

describe('generateVisitPdf — structure-aware notes', () => {
  it('renders tables + task lines without crashing', async () => {
    const buf = await generateVisitPdf(mkVisit({ soapText: STRUCTURED_SOAP }));
    expect(buf.subarray(0, 4).toString('ascii')).toBe('%PDF');
    expect(buf.length).toBeGreaterThan(1000);
  });

  it('paginates a long table across a page break without crashing', async () => {
    const rows = ['| Item | Result |', '| --- | --- |'];
    for (let i = 0; i < 80; i++) rows.push(`| Finding ${i} | Value ${i} |`);
    const buf = await generateVisitPdf(
      mkVisit({ soapText: `## Findings\n\n${rows.join('\n')}` })
    );
    expect(buf.subarray(0, 4).toString('ascii')).toBe('%PDF');
  });
});

// ---------------------------------------------------------------------------
// Metadata-PHI guards. The PDF /Info dictionary and the DOCX
// docProps/core.xml entries persist in OS file-preview surfaces
// (Spotlight, Explorer) and survive forwarding the file. Anything
// that lands here leaks the moment a doctor shares the export.
// These tests pin Title to the opaque visitId and Author/Creator to
// the brand name — and fail loudly if patient or clinician names
// ever sneak back in.
// ---------------------------------------------------------------------------

const PHI_PATIENT = 'METADATA TEST PATIENT';
const PHI_CLINICIAN = 'METADATA TEST CLINICIAN';
const PHI_VISIT_ID = 'vmeta-test-001';

function extractPdfInfoDict(buf: Buffer): Record<string, string> {
  // pdfkit serializes each /Info entry as an indirect object reference
  // (e.g. `/Title 13 0 R`) and stores the actual literal-string body
  // in object 13 under `13 0 obj\n(Visit vmeta-test-001)\nendobj`.
  // Two-step: collect refs from the /Info dict, then resolve each.
  // lastIndexOf-on-')' tolerates inner parens (e.g. the Producer
  // string "QuillMD PDF Generator (pdfkit)").
  const text = buf.toString('latin1');
  const refs: Array<[string, number]> = [];
  const refRe = /\/(Title|Author|Creator|Producer)\s+(\d+)\s+0\s+R/g;
  let m: RegExpExecArray | null;
  while ((m = refRe.exec(text)) !== null) {
    refs.push([m[1], Number(m[2])]);
  }
  const out: Record<string, string> = {};
  for (const [key, objNum] of refs) {
    const startMarker = `${objNum} 0 obj`;
    const objStart = text.indexOf(startMarker);
    if (objStart < 0) continue;
    const objEnd = text.indexOf('endobj', objStart);
    if (objEnd < 0) continue;
    const body = text.slice(objStart + startMarker.length, objEnd);
    const open = body.indexOf('(');
    const close = body.lastIndexOf(')');
    if (open >= 0 && close > open) {
      out[key] = body.slice(open + 1, close);
    }
  }
  return out;
}

describe('generateVisitPdf — metadata PHI guard', () => {
  it('puts only visitId in /Title and brand in /Author', async () => {
    const buf = await generateVisitPdf(
      mkVisit({
        visitId: PHI_VISIT_ID,
        patientName: PHI_PATIENT,
        clinicianName: PHI_CLINICIAN,
      })
    );
    const info = extractPdfInfoDict(buf);
    expect(info.Title).toBe(`Visit ${PHI_VISIT_ID}`);
    expect(info.Author).toBe('QuillMD');
    expect(info.Creator).toBe('QuillMD');
    expect(info.Producer).toMatch(/QuillMD/);
  });

  it('never embeds the patient name in any /Info field', async () => {
    const buf = await generateVisitPdf(
      mkVisit({
        visitId: PHI_VISIT_ID,
        patientName: PHI_PATIENT,
        clinicianName: PHI_CLINICIAN,
      })
    );
    const info = extractPdfInfoDict(buf);
    for (const value of Object.values(info)) {
      expect(value).not.toContain(PHI_PATIENT);
    }
  });

  it('never embeds the clinician name in any /Info field', async () => {
    const buf = await generateVisitPdf(
      mkVisit({
        visitId: PHI_VISIT_ID,
        patientName: PHI_PATIENT,
        clinicianName: PHI_CLINICIAN,
      })
    );
    const info = extractPdfInfoDict(buf);
    for (const value of Object.values(info)) {
      expect(value).not.toContain(PHI_CLINICIAN);
    }
  });
});

async function readDocxCoreXml(buf: Buffer): Promise<string> {
  const zip = await JSZip.loadAsync(buf);
  const entry = zip.file('docProps/core.xml');
  if (!entry) throw new Error('docProps/core.xml not found in DOCX');
  return entry.async('text');
}

describe('generateVisitDocx — metadata PHI guard', () => {
  it('puts only visitId in <dc:title> and brand in <dc:creator>', async () => {
    const buf = await generateVisitDocx(
      mkVisit({
        visitId: PHI_VISIT_ID,
        patientName: PHI_PATIENT,
        clinicianName: PHI_CLINICIAN,
      })
    );
    const xml = await readDocxCoreXml(buf);
    expect(xml).toContain(`<dc:title>Visit ${PHI_VISIT_ID}</dc:title>`);
    expect(xml).toContain('<dc:creator>QuillMD</dc:creator>');
  });

  it('never embeds the patient name in docProps/core.xml', async () => {
    const buf = await generateVisitDocx(
      mkVisit({
        visitId: PHI_VISIT_ID,
        patientName: PHI_PATIENT,
        clinicianName: PHI_CLINICIAN,
      })
    );
    const xml = await readDocxCoreXml(buf);
    expect(xml).not.toContain(PHI_PATIENT);
  });

  it('never embeds the clinician name in docProps/core.xml', async () => {
    const buf = await generateVisitDocx(
      mkVisit({
        visitId: PHI_VISIT_ID,
        patientName: PHI_PATIENT,
        clinicianName: PHI_CLINICIAN,
      })
    );
    const xml = await readDocxCoreXml(buf);
    expect(xml).not.toContain(PHI_CLINICIAN);
  });
});

// ---------------------------------------------------------------------------
// Header fields + form-only export (feat/template-header-fields). A parsed
// operative-note form's labeled header renders at the top of the styled export
// in place of the generic patient bar; a form-only template suppresses the
// appended coding/summary blocks.
// ---------------------------------------------------------------------------
describe('generateVisitDocx — header fields (form templates)', () => {
  const HEADER_FIELDS = [
    { label: 'PATIENT NAME', value: 'KUK' },
    { label: 'PATIENT DOB', value: '' },
    { label: 'DATE OF SURGERY', value: '2026-07-23' },
    { label: 'SURGEON', value: 'Dr. Shabatian' },
  ];

  async function docXml(buf: Buffer): Promise<string> {
    const zip = await JSZip.loadAsync(buf);
    return zip.file('word/document.xml')!.async('text');
  }

  it('renders labeled header fields (values + honest blank) in place of the patient bar', async () => {
    const xml = await docXml(await generateVisitDocx(mkVisit({ headerFields: HEADER_FIELDS })));
    expect(xml).toContain('PATIENT NAME');
    expect(xml).toContain('KUK');
    expect(xml).toContain('DATE OF SURGERY');
    expect(xml).toContain('2026-07-23');
    expect(xml).toContain('SURGEON');
    expect(xml).toContain('Dr. Shabatian');
    expect(xml).toContain('—'); // blank PATIENT DOB → honest em-dash
    // The generic patient bar's "Jane Doe" is replaced by the doctor's form.
    expect(xml).not.toContain('Jane Doe');
  });

  it('form-only export suppresses appended Diagnoses/Summary but keeps the form + body', async () => {
    const withXml = await docXml(
      await generateVisitDocx(mkVisit({ headerFields: HEADER_FIELDS, formOnly: false }))
    );
    const formXml = await docXml(
      await generateVisitDocx(mkVisit({ headerFields: HEADER_FIELDS, formOnly: true }))
    );
    expect(withXml).toContain('DIAGNOSES'); // section headings are uppercased
    expect(formXml).not.toContain('DIAGNOSES');
    expect(formXml).not.toContain('PATIENT SUMMARY');
    expect(formXml).toContain('PATIENT NAME'); // form header survives
    expect(formXml).toContain('lisinopril'); // note body survives
  });
});

describe('generateVisitPdf — header fields', () => {
  it('renders header fields + form-only without crashing', async () => {
    const buf = await generateVisitPdf(
      mkVisit({ headerFields: [{ label: 'SURGEON', value: 'Dr. Shabatian' }], formOnly: true })
    );
    expect(buf.subarray(0, 4).toString('ascii')).toBe('%PDF');
    expect(buf.length).toBeGreaterThan(1000);
  });
});
