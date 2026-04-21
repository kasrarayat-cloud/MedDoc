// ============================================================================
// T-M20.1: end-to-end PDF overlap regression script
// ----------------------------------------------------------------------------
// One-off verifier for the `renderInlineWithBold` fix in pdf-generator.ts.
// Feeds the generator a SOAP note that reproduces the overlap scenario —
// bold labels followed by "[not documented]" placeholders — and writes
// the resulting PDF to the path passed as argv[2] (default: /tmp/out/test.pdf).
//
// Usage (inside the db-migrate container, which has source + deps):
//   npx tsx apps/transcribe-md/scripts/gen-test-pdf.ts /tmp/out/test.pdf
//
// Verify with `pdftotext -layout <file> -` and confirm each bold label
// ("PMH:", "Medications:", "Social History:", "ROS:") appears on its
// own line, with "[not documented]" after it. Pre-fix, multiple labels
// collapsed onto a single line → visual overlap in the rendered PDF.
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

const mockData: VisitExportData = {
  visitId: 'test-t-m20-1',
  patientName: 'Jane Doe',
  specialty: 'Internal Medicine',
  chiefComplaint: 'Annual physical',
  status: 'SIGNED' as VisitExportData['status'],
  createdAt: new Date('2026-04-22T14:00:00Z'),
  signedAt: new Date('2026-04-22T14:30:00Z'),

  clinicianName: 'Dr. Test Clinician',
  clinicianEmail: 'test@quillmd.com',

  soapText: OVERLAP_SOAP,

  icdCodes: [],
  em: null,
  procedures: [],
  modifiers: [],
  prescriptions: [],
  rxWarnings: [],
  referrals: [],
  patientSummary: null,
};

async function main(): Promise<void> {
  const outPath = process.argv[2] ?? '/tmp/out/test.pdf';
  await mkdir(dirname(outPath), { recursive: true });
  const pdf = await generateVisitPdf(mockData);
  await writeFile(outPath, pdf);
  console.log(`wrote ${pdf.length} bytes → ${outPath}`);
}

void main().catch((err) => {
  console.error(err);
  process.exit(1);
});
