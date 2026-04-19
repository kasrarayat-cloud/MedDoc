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

  const soapText =
    visit.status === 'SIGNED'
      ? visit.signedSoap ?? visit.soapFinal ?? ''
      : visit.soapFinal ?? '';

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

  return {
    visitId: visit.id,
    patientName: visit.patientName,
    specialty: visit.specialty,
    chiefComplaint: visit.chiefComplaint,
    status: visit.status as TranscribeVisitStatus,
    createdAt: visit.createdAt,
    signedAt: visit.signedAt,
    clinicianName: visit.user.name ?? null,
    clinicianEmail: visit.user.email,
    soapText,
    icdCodes: icdBlob?.codes ?? [],
    em: cptBlob?.em ?? null,
    procedures: cptBlob?.procedures ?? [],
    modifiers: cptBlob?.modifiers ?? [],
    prescriptions: rxBlob?.prescriptions ?? [],
    rxWarnings: rxBlob?.warnings ?? [],
    referrals: refBlob?.referrals ?? [],
    patientSummary: visit.patientSummary,
  };
}
