import { describe, expect, it } from 'vitest';
import JSZip from 'jszip';
import type { VisitExportData } from '@/lib/visit-export';
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
    formTitle: null,
    formSignature: null,
    ...overrides,
  };
}

// ⚠️ `describe('generateVisitPdf')` STOOD HERE AND ITS ARMS WERE NOT DELETED —
// they MOVED into the DOCX block below (ruling #113 retired the second builder;
// #116 required the coverage to move rather than go with the import).
//
// Two of its three arms had exact DOCX twins already ("magic header" ↔ "PK
// magic header"). The other two did not, and are now DOCX arms: the empty-SOAP
// tolerance and the grows-with-content check.

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

  // ↓ MOVED from `describe('generateVisitPdf')` when ruling #113 retired the
  //   second builder. Neither arm had a DOCX twin, so neither could be dropped
  //   as duplicate coverage — an empty SOAP and a "does it grow with content"
  //   check are properties of whatever builds the document, and that is now
  //   this one.
  it('tolerates an empty SOAP without crashing', async () => {
    const buf = await generateVisitDocx(mkVisit({ soapText: '' }));
    expect(buf.subarray(0, 2).toString('ascii')).toBe('PK');
  });

  it('emits a larger buffer when more sections are populated', async () => {
    const small = await generateVisitDocx(
      mkVisit({
        icdCodes: [],
        procedures: [],
        prescriptions: [],
        referrals: [],
        patientSummary: null,
      })
    );
    const big = await generateVisitDocx(mkVisit());
    expect(big.length).toBeGreaterThan(small.length);
  });
});

// ---------------------------------------------------------------------------
// Structure-aware notes — GitHub-style markdown tables + task lists inside
// section bodies. These smoke-test that the DOCX Table path doesn't crash and
// produces well-formed output. (It used to say "and the PDF vector-checkbox /
// grid path" too; that builder retired under ruling #113.)
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

  // ↓ MOVED from the retired PDF block, with its meaning restated. It used to
  //   assert "paginates a long table across a page break without crashing".
  //   The DOCX declares no page breaks — LibreOffice paginates now — so what
  //   survives is the half that was always ours: an 80-row table must build,
  //   and build as a REAL Word table rather than degrading to literal markdown
  //   pipes, which is the failure mode a long table actually has.
  it('builds an 80-row table as a real Word table, not literal markdown', async () => {
    const rows = ['| Item | Result |', '| --- | --- |'];
    for (let i = 0; i < 80; i++) rows.push(`| Finding ${i} | Value ${i} |`);
    const buf = await generateVisitDocx(
      mkVisit({ soapText: `## Findings\n\n${rows.join('\n')}` })
    );
    expect(buf.subarray(0, 2).toString('ascii')).toBe('PK');
    const zip = await JSZip.loadAsync(buf);
    const docXml = await zip.file('word/document.xml')!.async('text');
    expect(docXml).toContain('<w:tbl>');
    expect(docXml).toContain('Finding 79');
    expect(docXml).not.toContain('| Finding 79 |');
  });
});

// The PDF structure-aware block moved into the DOCX one above for the same
// reason. Its long-table arm is the one worth keeping and it changed MEANING in
// the move: pagination is no longer ours to get wrong — LibreOffice breaks the
// page now — so what the DOCX can still be held to is that an 80-row table
// BUILDS, and builds as a real Word table rather than as markdown left as text.

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


// ⚠️ THE PDF METADATA-PHI BLOCK IS GONE AND ITS GUARANTEE IS NOT.
//
// It asserted three things about pdfkit's /Info dictionary: only visitId in
// /Title, brand in /Author, and neither the patient's nor the clinician's name
// anywhere in it. All three have exact DOCX twins in the block below, and the
// PDF is now LibreOffice's render of that DOCX — LibreOffice maps docProps into
// /Info, so a docProps proven PHI-free is what makes the /Info PHI-free.
//
// ⚠️ THAT IS AN ARGUMENT, NOT A MEASUREMENT, AND IT IS WRITTEN DOWN AS ONE.
// The conversion step is not exercised by any unit test — see
// `gate-f3-one-pdf-builder.test.ts`, which records the untested leg by name
// rather than leaving the gap to be rediscovered.

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

// The PDF header-fields smoke test retired with the builder. Its two DOCX
// twins directly above assert strictly more than it did — it only checked the
// bytes did not crash; they check the rendered XML.
