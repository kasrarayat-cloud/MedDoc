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
  flattenTables,
  flattenTasks,
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
    headerFields: [],
    formOnly: false,
    formTitle: null,
    formSignature: null,
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
  it('does NOT surface Rx warnings in the export — review chrome stays on-screen + in the audit', () => {
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
    // The "Rx safety warnings — review before sending" banner + [SEVERITY]
    // blocks are internal review machinery — never in an exported document.
    expect(out).not.toContain('--- Rx warnings');
    expect(out).not.toContain('review before sending');
    expect(out).not.toContain('[CRITICAL]');
    expect(out).not.toContain('Prior ACE-inhibitor cough');
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

// ---------------------------------------------------------------------------
// Structure-aware notes (T: GitHub tables + task lists in section bodies).
// The clipboard formatters must degrade tables/tasks to ASCII so an EHR
// text field never receives raw pipes/brackets — and PROSE-ONLY notes must
// stay byte-identical through the flatteners (regression canary).
// ---------------------------------------------------------------------------

describe('flattenTables', () => {
  it('collapses a 2-column table to `cell1: cell2` lines', () => {
    const src = [
      '| Vital | Value |',
      '|-------|-------|',
      '| BP | 148/92 |',
      '| HR | 78 |',
    ].join('\n');
    const out = flattenTables(src);
    expect(out).toBe('BP: 148/92\nHR: 78');
    expect(out).not.toContain('|');
    expect(out).not.toContain('---');
  });

  it('zips a 3+ column table header with each body row via ` · `', () => {
    const src = [
      '| Med | Dose | Route |',
      '| --- | --- | --- |',
      '| Lisinopril | 20 mg | PO |',
    ].join('\n');
    const out = flattenTables(src);
    expect(out).toBe('Med: Lisinopril · Dose: 20 mg · Route: PO');
    expect(out).not.toContain('|');
  });

  it('drops separator rows and preserves surrounding prose', () => {
    const src = [
      'Findings:',
      '| Site | Result |',
      '| --- | --- |',
      '| Right | Normal |',
      '',
      'Impression: stable.',
    ].join('\n');
    const out = flattenTables(src);
    expect(out).toBe(
      ['Findings:', 'Right: Normal', '', 'Impression: stable.'].join('\n')
    );
  });

  it('degrades a header-only table to a single dotted line (nothing lost)', () => {
    const src = ['| A | B |', '| --- | --- |'].join('\n');
    expect(flattenTables(src)).toBe('A · B');
  });

  it('leaves prose without pipe rows byte-identical', () => {
    const prose =
      '## Subjective\n**Chief Complaint:** Chest tightness.\n\n- BP 148/92\n- HR 78';
    expect(flattenTables(prose)).toBe(prose);
  });
});

describe('flattenTasks', () => {
  it('rewrites `- [x]` / `- [ ]` to ASCII `[x]` / `[ ]`', () => {
    const src = [
      '- [x] Chaperone offered',
      '- [ ] Interpreter used',
      '* [X] Consent obtained',
    ].join('\n');
    expect(flattenTasks(src)).toBe(
      '[x] Chaperone offered\n[ ] Interpreter used\n[x] Consent obtained'
    );
  });

  it('keeps unchecked options VISIBLE (clinical meaning is not noise)', () => {
    const out = flattenTasks('- [ ] Chaperone offered');
    expect(out).toContain('[ ] Chaperone offered');
  });

  it('preserves leading indentation', () => {
    expect(flattenTasks('  - [x] Nested')).toBe('  [x] Nested');
  });

  it('leaves prose without task lines byte-identical', () => {
    const prose = '## Plan\n- Increase lisinopril\n1. Follow up in 2 weeks';
    expect(flattenTasks(prose)).toBe(prose);
  });
});

describe('clipboard degradation — structure-aware notes', () => {
  const structuredSoap = [
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

  it('Epic never emits raw pipes or `- [ ]` brackets', () => {
    const out = formatForEpic(mkVisit({ soapText: structuredSoap }));
    expect(out).not.toContain('|');
    expect(out).not.toContain('- [');
    expect(out).toContain('BP: 148/92');
    expect(out).toContain('[x] Chaperone offered');
    expect(out).toContain('[ ] Interpreter used');
  });

  it('Cerner degrades tables/tasks identically to Epic', () => {
    const out = formatForCerner(mkVisit({ soapText: structuredSoap }));
    // Cerner's own header uses a `name | date` divider, so assert on the
    // note body specifically: no raw markdown table rows survive.
    expect(out).not.toContain('| BP |');
    expect(out).not.toContain('| Value |');
    expect(out).not.toContain('- [ ]');
    expect(out).toContain('BP: 148/92');
    expect(out).toContain('[ ] Interpreter used');
  });

  it('sectionSoap (Copy-this-section) degrades tables/tasks', () => {
    const out = sectionSoap(mkVisit({ soapText: structuredSoap }));
    expect(out).not.toContain('|');
    expect(out).toContain('BP: 148/92');
    expect(out).toContain('[x] Chaperone offered');
  });

  it('prose-only SOAP is byte-identical vs the pre-structure behavior', () => {
    // Manually reproduce the OLD stripMarkdown (no flatten chain) to prove
    // notes without pipes/tasks are unaffected by the new branches.
    const proseSoap =
      '## Subjective\n**Chief Complaint:** Chest tightness.\n\n## Plan\n1. Increase lisinopril to 20 mg.';
    const oldStrip = (s: string) =>
      s
        .replace(/^#{1,6}\s+/gm, '')
        .replace(/\*\*(.+?)\*\*/g, '$1')
        .replace(/(?<!\*)\*(?!\*)(.+?)\*(?!\*)/g, '$1');
    const visit = mkVisit({ soapText: proseSoap });
    expect(sectionSoap(visit)).toBe(oldStrip(proseSoap).trim());
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
