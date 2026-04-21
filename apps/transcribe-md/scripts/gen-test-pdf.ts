// ============================================================================
// T-M20.1 + T-M21: end-to-end PDF generation regression script
// ----------------------------------------------------------------------------
// Generates two test PDFs side by side:
//   /tmp/out/test-empty.pdf     — every SOAP sub-section is "[not documented]"
//                                  (the original T-M20.1 overlap repro)
//   /tmp/out/test-realistic.pdf — full HPI / multi-line PMH / multi-bullet
//                                  meds / Z00.00 + ICD codes / signed
//                                  electronically. T-M21 added this case
//                                  so we can eyeball wrap behavior, label
//                                  drift on long content, and font fidelity
//                                  (Charter + Inter Tight) against a more
//                                  representative visit.
//
// Usage (inside the db-migrate container, which has source + deps):
//   npx tsx apps/transcribe-md/scripts/gen-test-pdf.ts [outDir]
//   default outDir = /tmp/out
//
// Verify with `pdftotext -layout <file> -` and confirm each bold label
// appears on its own line. Use `pdffonts <file>` (poppler-utils) to
// confirm Charter + InterTight are embedded, not the previous
// Times-Roman / Helvetica defaults.
// ============================================================================

import { writeFile, mkdir } from 'node:fs/promises';
import { dirname } from 'node:path';

import { generateVisitPdf } from '../src/lib/pdf-generator';
import type { VisitExportData } from '../src/lib/visit-export';

// SOAP note mirrors the exact pattern the T-M18.x Layer-4 prompt emits:
// bold label + ":" + either content or the literal "[not documented]"
// placeholder. Every empty section is a potential overlap trigger.
const OVERLAP_SOAP = `## Subjective

**CC:** Routine annual physical
**HPI:** 45-year-old female presenting for annual check-up. No acute concerns.
**PMH:** [not documented]
**Medications:** [not documented]
**Allergies:** NKDA
**Social History:** [not documented]
**Family History:** Unremarkable
**ROS:** [not documented]

## Objective

**Vitals:** BP 118/76, HR 72, Temp 98.6F
**Physical Exam:** [not documented]

## Assessment

- Z00.00 Encounter for general adult medical examination without abnormal findings

## Plan

- Return in 1 year for next annual visit
- Routine labs ordered
`;

// Realistic SOAP: long HPI prose, multi-bullet PMH/meds, mixed
// label-content + plain bullets. Catches label-drift on wrapping
// long content and exercises Charter at small body sizes.
const REALISTIC_SOAP = `## Subjective

**CC:** Worsening shortness of breath on exertion over the past three weeks.

**HPI:** 62-year-old male with a history of hypertension and type-2 diabetes presents with progressive dyspnea on exertion over the past three weeks. He reports being able to walk only one block before stopping to catch his breath, down from his usual two miles. Denies chest pain, palpitations, orthopnea, paroxysmal nocturnal dyspnea, or lower-extremity swelling. No recent travel, no known sick contacts. Has been compliant with his current medications.

**PMH:**
- Hypertension, diagnosed 2018, well controlled on lisinopril
- Type 2 diabetes mellitus, diagnosed 2020, A1c 6.8 last check
- Hyperlipidemia, on atorvastatin
- Former smoker, 20 pack-years, quit 2015

**Medications:**
- Lisinopril 20 mg PO daily
- Metformin 1000 mg PO twice daily
- Atorvastatin 40 mg PO at bedtime
- Aspirin 81 mg PO daily

**Allergies:** Penicillin (rash); no other known drug allergies.

**Social History:** Married, lives with wife. Retired electrician. Quit smoking 11 years ago. Drinks 2-3 beers on weekends only. No illicit drug use.

**Family History:** Father died at 71 of MI. Mother alive at 86 with osteoporosis. One brother with type 2 diabetes.

**ROS:** Otherwise negative on 12-system review.

## Objective

**Vitals:** BP 142/88, HR 84 regular, RR 18, SpO2 96% on room air, Temp 98.4 F, Weight 198 lb (BMI 30.1).

**Physical Exam:** Alert, mildly diaphoretic. Cardiac: regular rate and rhythm, no murmurs/rubs/gallops. Lungs: bilateral basal crackles, no wheezing.

**Musculoskeletal:**
- Visible swelling of right knee
- Tenderness on palpation, medial joint line
- Limited ROM on flexion
- *Ability to fully bear weight was not assessed at this visit.*

**ROS:**
*Musculoskeletal:* Positive for right knee pain, worsening with weight-bearing.
*Cardiovascular:* denies chest pain, palpitations.
*Respiratory:* as documented in HPI.

*The following HPI elements were not assessed at this visit: onset modifiers, alleviating factors, prior imaging history.*

## Assessment

- I50.9 Heart failure, unspecified — new diagnosis, likely systolic given exertional dyspnea + bibasilar crackles + edema
- I10 Essential hypertension — uncontrolled at today's visit
- E11.9 Type 2 diabetes mellitus without complications — stable

## Plan

1. Diagnostics: echocardiogram, BNP, basic metabolic panel, CBC.
2. Medications: start furosemide 20 mg PO daily; increase lisinopril to 40 mg PO daily.
3. Referrals: cardiology for HFrEF workup if EF <50%.
4. Counseling: low-sodium diet, daily weight log.
5. Follow-up in 2 weeks with labs reviewed.
`;

function buildMock(
  visitId: string,
  patientName: string,
  soap: string,
  icds: VisitExportData['icdCodes'] = []
): VisitExportData {
  return {
    visitId,
    patientName,
    specialty: 'Internal Medicine',
    chiefComplaint: 'Annual physical',
    status: 'SIGNED' as VisitExportData['status'],
    createdAt: new Date('2026-04-22T14:00:00Z'),
    signedAt: new Date('2026-04-22T14:30:00Z'),
    clinicianName: 'Dr. Test Clinician',
    clinicianEmail: 'test@quillmd.com',
    soapText: soap,
    icdCodes: icds,
    em: null,
    procedures: [],
    modifiers: [],
    prescriptions: [],
    rxWarnings: [],
    referrals: [],
    patientSummary: null,
  };
}

async function writePdf(data: VisitExportData, outPath: string): Promise<void> {
  await mkdir(dirname(outPath), { recursive: true });
  const pdf = await generateVisitPdf(data);
  await writeFile(outPath, pdf);
  console.log(`wrote ${pdf.length} bytes → ${outPath}`);
}

async function main(): Promise<void> {
  const outDir = process.argv[2] ?? '/tmp/out';

  await writePdf(
    buildMock('test-t-m20-1-empty', 'Jane Doe', OVERLAP_SOAP),
    `${outDir}/test-empty.pdf`
  );

  const realistic = buildMock(
    'test-t-m21-realistic',
    'Robert Smith',
    REALISTIC_SOAP,
    [
      {
        code: 'I50.9',
        description: 'Heart failure, unspecified',
        evidence_quote: 'bibasilar crackles + edema',
        confidence: 0.85,
      },
      {
        code: 'I10',
        description: 'Essential hypertension',
        evidence_quote: 'BP 142/88',
        confidence: 0.95,
      },
    ]
  );
  realistic.prescriptions = [
    { drug: 'Furosemide', strength: '20 mg', form: 'tablet', sig: 'one tablet by mouth daily',
      quantity: '30', refills: '3', action: 'new', evidence_quote: 'instruct patient on weight monitoring' },
    { drug: 'Naproxen', strength: '500 mg', form: 'tablet', sig: 'one tablet by mouth twice daily with food',
      quantity: '30', refills: '1', action: 'new', evidence_quote: 'for knee pain' },
  ];
  realistic.rxWarnings = [
    { severity: 'critical', rx_drug: 'Furosemide',
      message: 'Potassium depletion risk — check K+ within 1 week and monitor',
      evidence_quote: 'new diuretic on ACE-I' },
    { severity: 'major', rx_drug: 'Naproxen',
      message: 'NSAID + HF relative contraindication; consider acetaminophen instead',
      evidence_quote: 'new HF dx' },
    { severity: 'minor', rx_drug: 'Naproxen',
      message: 'Take with food to reduce GI upset',
      evidence_quote: 'standard counseling' },
  ];
  await writePdf(realistic, `${outDir}/test-realistic.pdf`);
}

void main().catch((err) => {
  console.error(err);
  process.exit(1);
});
