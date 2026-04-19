import { describe, expect, it } from 'vitest';
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
