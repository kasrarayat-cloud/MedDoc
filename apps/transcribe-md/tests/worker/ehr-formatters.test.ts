import { describe, expect, it } from 'vitest';
import type { VisitExportData } from '@/lib/visit-export';
import {
  formatForEpic,
  formatForAthena,
  formatForCerner,
  formatForEclinicalworks,
  formatGeneric,
  sectionSoap,
  sectionCodes,
  sectionRx,
  sectionExtras,
} from '@/lib/ehr-formatters';

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
      '## Subjective\n**Chief Complaint:** Chest tightness.\n\n## Objective\nBP 148/92.\n\n## Assessment\nHTN not at goal.\n\n## Plan\n1. Increase lisinopril to 20 mg.',
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

describe('formatForEpic', () => {
  it('uses ALL-CAPS section headers followed by colon', () => {
    const out = formatForEpic(mkVisit());
    expect(out).toMatch(/^PATIENT: Jane Doe/);
    expect(out).toContain('DIAGNOSES:');
    expect(out).toContain('MEDICATIONS:');
    expect(out).toContain('PROCEDURES / E&M:');
  });
  it('strips markdown from the SOAP body', () => {
    const out = formatForEpic(mkVisit());
    expect(out).not.toContain('##');
    expect(out).not.toContain('**Chief Complaint:**');
    expect(out).toContain('Chief Complaint: Chest tightness.');
  });
  it('separates sections with blank lines (paste-friendly)', () => {
    const out = formatForEpic(mkVisit());
    expect(out).toMatch(/\n\nDIAGNOSES:/);
    expect(out).toMatch(/\n\nMEDICATIONS:/);
  });
});

describe('formatForAthena', () => {
  it('preserves markdown bold + bulleted diagnoses', () => {
    const out = formatForAthena(mkVisit());
    expect(out).toContain('**Patient:** Jane Doe');
    expect(out).toContain('**Diagnoses**');
    expect(out).toContain('- `I10`');
  });
});

describe('formatForCerner', () => {
  it('uses dashed dividers instead of markdown', () => {
    const out = formatForCerner(mkVisit());
    expect(out).toMatch(/-{10,}/);
    expect(out).toContain('DIAGNOSES');
    expect(out).not.toContain('**');
    expect(out).not.toContain('##');
  });
});

describe('formatForEclinicalworks', () => {
  it('relabels SOAP headings to S:/O:/A:/P:', () => {
    const out = formatForEclinicalworks(mkVisit());
    expect(out).toContain('\nS:\n');
    expect(out).toContain('\nO:\n');
    expect(out).toContain('\nA:\n');
    expect(out).toContain('\nP:\n');
    expect(out).not.toContain('## Subjective');
  });
  it('uses DX / CPT / RX short labels', () => {
    const out = formatForEclinicalworks(mkVisit());
    expect(out).toContain('DX:');
    expect(out).toContain('CPT:');
    expect(out).toContain('RX:');
  });
});

describe('formatGeneric', () => {
  it('keeps SOAP markdown untouched', () => {
    const out = formatGeneric(mkVisit());
    expect(out).toContain('## Subjective');
    expect(out).toContain('**Chief Complaint:**');
  });
});

describe('Rx warnings', () => {
  it('surfaces warnings under the Medications section', () => {
    const visit = mkVisit({
      rxWarnings: [
        {
          severity: 'critical',
          rx_drug: 'Lisinopril',
          message: 'Prior ACE-inhibitor cough — verify tolerance',
        },
      ],
    });
    const out = formatForEpic(visit);
    expect(out).toContain('--- Rx warnings');
    expect(out).toContain('[CRITICAL] Lisinopril');
  });
});

describe('section helpers', () => {
  it('sectionSoap returns plaintext SOAP only', () => {
    const out = sectionSoap(mkVisit());
    expect(out).not.toContain('PATIENT:');
    expect(out).not.toContain('DIAGNOSES:');
    expect(out).toContain('Chief Complaint: Chest tightness.');
  });
  it('sectionCodes returns DX + CPT blocks only', () => {
    const out = sectionCodes(mkVisit());
    expect(out).toContain('DIAGNOSES:');
    expect(out).toContain('PROCEDURES / E&M:');
    expect(out).not.toContain('MEDICATIONS');
  });
  it('sectionRx returns MEDICATIONS block only', () => {
    const out = sectionRx(mkVisit());
    expect(out).toContain('MEDICATIONS:');
    expect(out).toContain('Lisinopril 20 mg tablet');
  });
  it('sectionExtras returns patient-summary + referrals', () => {
    const out = sectionExtras(mkVisit());
    expect(out).toContain('PATIENT SUMMARY:');
    expect(out).toContain('your blood pressure');
  });
});

describe('signed-by footer', () => {
  it('includes signed date + clinician name on signed visits', () => {
    const out = formatForEpic(mkVisit());
    expect(out).toContain('Signed electronically by Ayesha Khan');
    expect(out).toContain('Apr 19, 2026');
  });
  it('drops the footer when includeFooter=false', () => {
    const out = formatForEpic(mkVisit(), { includeFooter: false });
    expect(out).not.toContain('Signed electronically');
    expect(out).not.toContain('TranscribeMD. Clinician reviewed');
  });
});
