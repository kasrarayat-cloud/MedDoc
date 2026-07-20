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

import prisma from "@meddoc/db";
import type { TranscribeVisitStatus } from "@prisma/client";
import { findSpecialty } from "@meddoc/shared/specialties";
import { projectEmForDisplay } from "./visit-export";
import type {
  CptEm,
  CptModifier,
  CptProcedure,
  IcdCode,
  Prescription,
  Referral,
  RxWarning,
  VisitExportData,
} from "./visit-export";
import { assessVisitAutomationProof } from "@/worker/automation-finalization";
import { VISIT_AUTOMATION_MANIFEST_SELECT } from "@/worker/automation-manifest";
import { authorizeVisitDeliveryFinalClaim } from "@/lib/template-twin/delivery-authorization";
import { TEMPLATE_TWIN_DURABLE_VISIT_EXCLUSION_WHERE } from "@/lib/template-twin/durable-visit-exclusion";
import { currentClinicalVisitActorWhere } from "@/lib/clinical-visit-authority";

export interface VisitExportObjectManifest {
  id: string;
  audioKey: string | null;
  dictationAudioKey: string | null;
  audioMimeType: string | null;
  status: TranscribeVisitStatus;
  createdAt: Date;
}

/**
 * Object keys are PHI-linked storage locators. Load them only between two
 * exact delivery claims so archive jobs never inventory Twin storage before
 * current authorization and never retain a locator across a revoked claim.
 */
export async function loadVisitExportObjectManifest(
  visitId: string,
  userId: string,
): Promise<VisitExportObjectManifest | null> {
  const initialDeliveryClaim = await authorizeVisitDeliveryFinalClaim({
    visitId,
    actorUserId: userId,
  });
  const manifest = await prisma.transcribeVisit.findFirst({
    where: {
      id: visitId,
      ...currentClinicalVisitActorWhere(userId),
      ...(initialDeliveryClaim.templateTwin
        ? {}
        : TEMPLATE_TWIN_DURABLE_VISIT_EXCLUSION_WHERE),
    },
    select: {
      id: true,
      userId: true,
      audioKey: true,
      dictationAudioKey: true,
      audioMimeType: true,
      status: true,
      createdAt: true,
    },
  });
  if (!manifest || manifest.userId !== userId) return null;
  const finalDeliveryClaim = await authorizeVisitDeliveryFinalClaim({
    visitId,
    actorUserId: userId,
  });
  if (finalDeliveryClaim.templateTwin !== initialDeliveryClaim.templateTwin) {
    throw new Error("Visit delivery authority changed.");
  }
  return {
    id: manifest.id,
    audioKey: manifest.audioKey,
    dictationAudioKey: manifest.dictationAudioKey,
    audioMimeType: manifest.audioMimeType,
    status: manifest.status,
    createdAt: manifest.createdAt,
  };
}

/**
 * Auth + load. Returns null for "not found / not yours" so the route
 * can return 404 without distinguishing the two (prevents ID
 * enumeration).
 */
export async function loadVisitExportData(
  visitId: string,
  userId: string,
  options: { allowSyntheticOriginalTemplate?: boolean } = {},
): Promise<VisitExportData | null> {
  // The shared authorizer begins with the identifier/provenance-only read
  // boundary. Run it before selecting SOAP/codes/Rx so a stale Twin session
  // cannot project clinical payload into application memory. It is a no-op
  // beyond ownership for ordinary visits and retains the stricter signed,
  // reviewed, provider-owned final claim for Twin delivery.
  const initialDeliveryClaim = await authorizeVisitDeliveryFinalClaim({
    visitId,
    actorUserId: userId,
    allowSyntheticOriginalTemplate:
      options.allowSyntheticOriginalTemplate === true,
  });
  const visit = await prisma.transcribeVisit.findFirst({
    where: {
      id: visitId,
      ...currentClinicalVisitActorWhere(userId),
      ...(initialDeliveryClaim.templateTwin
        ? {}
        : TEMPLATE_TWIN_DURABLE_VISIT_EXCLUSION_WHERE),
    },
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
      soapVersion: true,
      automationManifest: { select: VISIT_AUTOMATION_MANIFEST_SELECT },
      templateTwinSyntheticQaRun: {
        select: {
          id: true,
          admissionId: true,
          pinnedGlobalRolloutGeneration: true,
          pinnedPracticeRolloutGeneration: true,
        },
      },
      user: { select: { name: true, email: true, practiceId: true } },
    },
  });
  if (!visit || visit.userId !== userId) return null;
  const automation = assessVisitAutomationProof({
    visitId: visit.id,
    practiceId: visit.user.practiceId,
    soapVersion: visit.soapVersion,
    soapFinal: visit.soapFinal,
    manifest: visit.automationManifest,
    staging: visit.templateTwinSyntheticQaRun
      ? {
          admissionId: visit.templateTwinSyntheticQaRun.admissionId ?? "",
          runId: visit.templateTwinSyntheticQaRun.id,
          globalGeneration:
            visit.templateTwinSyntheticQaRun.pinnedGlobalRolloutGeneration,
          practiceGeneration:
            visit.templateTwinSyntheticQaRun.pinnedPracticeRolloutGeneration,
        }
      : null,
  });
  if (!automation.ready) return null;

  const soapText =
    visit.status === "SIGNED"
      ? (visit.signedSoap ?? visit.soapFinal ?? "")
      : (visit.soapFinal ?? "");

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
  const emForExport = projectEmForDisplay(
    cptBlob?.em ?? null,
    visit.status === "SIGNED",
  );

  const exportData: VisitExportData = {
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
  // The first delivery claim authorized the clinical projection. Repeat the
  // locked final claim immediately before returning it to a response/render
  // caller so a revocation during load/formatting cannot escape as bytes.
  const finalDeliveryClaim = await authorizeVisitDeliveryFinalClaim({
    visitId,
    actorUserId: userId,
    allowSyntheticOriginalTemplate:
      options.allowSyntheticOriginalTemplate === true,
  });
  if (finalDeliveryClaim.templateTwin !== initialDeliveryClaim.templateTwin) {
    throw new Error("Visit delivery authority changed.");
  }
  return exportData;
}
