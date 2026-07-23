// ============================================================================
// Server-only visit-export loader (T-M7)
// ----------------------------------------------------------------------------
// Split from visit-export.ts because that module is imported (transitively)
// from client components via ehr-formatters.ts → visit-ready-view.tsx.
// Any `import prisma from '@meddoc/db'` reaches into @prisma/adapter-pg,
// which pulls Node built-ins (fs/net/tls/dns) and breaks the client bundle.
//
// Keeping the Prisma-touching function here means the pure helpers and
// types can stay in visit-export.ts and be safely client-imported.
// ============================================================================

import prisma from '@meddoc/db';
import type { TranscribeVisitStatus } from '@prisma/client';
import { findSpecialty } from '@meddoc/shared/specialties';
import { projectEmForDisplay, sanitizeExportedSoap } from './visit-export';
import type {
  CptEm,
  CptModifier,
  CptProcedure,
  IcdCode,
  Prescription,
  Referral,
  RxWarning,
  VisitExportData,
} from './visit-export';

/**
 * Auth + load. Returns null for "not found / not yours" so the route
 * can return 404 without distinguishing the two (prevents ID
 * enumeration).
 */
export async function loadVisitExportData(
  visitId: string,
  userId: string
): Promise<VisitExportData | null> {
  const visit = await prisma.transcribeVisit.findUnique({
    where: { id: visitId },
    select: {
      id: true,
      userId: true,
      patientName: true,
      specialty: true,
      chiefComplaint: true,
      status: true,
      createdAt: true,
      signedAt: true,
      soapFinal: true,
      signedSoap: true,
      icdCodes: true,
      cptCodes: true,
      rxDrafts: true,
      referrals: true,
      patientSummary: true,
      user: { select: { name: true, email: true } },
    },
  });
  if (!visit || visit.userId !== userId) return null;

  const rawSoap =
    visit.status === 'SIGNED'
      ? visit.signedSoap ?? visit.soapFinal ?? ''
      : visit.soapFinal ?? '';
  // DEDUPE (prod bug): the note body may carry a "## PATIENT SUMMARY" section
  // (from the template — often partial), and the visit ALSO has a dedicated,
  // complete `patientSummary` field the exporters render as their own "Patient
  // Summary" block. Rendering both yields a partial-above-complete duplicate.
  // When the complete field is present, strip the note's section so exactly one
  // (complete) summary is rendered; when it is absent, the note's section stays.
  // Presentation-only export cleanup (Stage 1): set-aside/empty prose sections
  // → "Not documented.", "[not documented]" table cells → "—", review-lane
  // placeholder dropped. Applied ONLY to the exported copy — stored columns and
  // the on-screen review lane are untouched. Runs after the patient-summary
  // strip so the dedupe still sees the note's own heading.
  const soapText = sanitizeExportedSoap(
    visit.patientSummary && visit.patientSummary.trim()
      ? stripNotePatientSummarySection(rawSoap)
      : rawSoap
  );

  // All four of these are Json? columns — treat each as its own shape
  // with a tolerant cast + safe-default. Downstream code can rely on
  // arrays being arrays.
  const icdBlob = (visit.icdCodes as { codes?: IcdCode[] } | null) ?? null;
  const cptBlob =
    (visit.cptCodes as {
      em?: CptEm | null;
      procedures?: CptProcedure[];
      modifiers?: CptModifier[];
    } | null) ?? null;
  const rxBlob =
    (visit.rxDrafts as {
      prescriptions?: Prescription[];
      warnings?: RxWarning[];
    } | null) ?? null;
  const refBlob =
    (visit.referrals as { referrals?: Referral[] } | null) ?? null;

  // E/M PARITY (#315 obs#2): project the AUTHORITATIVE displayed level onto
  // em.code so every artifact (PDF, DOCX, all EHR clipboard formats) prints
  // what the doctor reviewed — never the raw L7b suggestion. The SAME helper
  // the client Codes tab + "Copy codes" use, so all surfaces agree.
  const emForExport = projectEmForDisplay(cptBlob?.em ?? null, visit.status === 'SIGNED');

  return {
    visitId: visit.id,
    patientName: visit.patientName,
    // PDF/DOCX/EHR formatters render `data.specialty` directly into
    // document headers — we want the human label ("Cardiology"), not
    // the canonical id ("cardiology"). findSpecialty also resolves
    // legacy display-name rows so old visits export with the right
    // label instead of "Unspecified".
    specialty: findSpecialty(visit.specialty).label,
    chiefComplaint: visit.chiefComplaint,
    status: visit.status as TranscribeVisitStatus,
    createdAt: visit.createdAt,
    signedAt: visit.signedAt,
    clinicianName: visit.user.name ?? null,
    clinicianEmail: visit.user.email,
    soapText,
    icdCodes: icdBlob?.codes ?? [],
    em: emForExport,
    procedures: cptBlob?.procedures ?? [],
    modifiers: cptBlob?.modifiers ?? [],
    prescriptions: rxBlob?.prescriptions ?? [],
    rxWarnings: rxBlob?.warnings ?? [],
    referrals: refBlob?.referrals ?? [],
    patientSummary: visit.patientSummary,
  };
}

/**
 * Remove a note body's "## PATIENT SUMMARY" section (heading + body up to the
 * next "## " heading or end of note) so it is not rendered alongside the visit's
 * dedicated complete `patientSummary` field. Pure; case-insensitive on the
 * heading text only. When the note carries no such section the SECTION is left
 * intact; trailing whitespace is still normalised (trimEnd + collapse blank-line
 * runs), which is inert for the export renderer.
 */
export function stripNotePatientSummarySection(soap: string): string {
  return soap
    .replace(/(^|\n)[ \t]*##[ \t]+patient summary\b[\s\S]*?(?=\n[ \t]*##[ \t]|$)/i, '$1')
    .replace(/\n{3,}/g, '\n\n')
    .trimEnd();
}
