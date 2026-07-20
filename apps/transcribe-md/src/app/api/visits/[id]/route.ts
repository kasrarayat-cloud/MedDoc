// ============================================================================
// GET   /api/visits/[id]  — full visit shape (smoke F-B-003 fix)
// PATCH /api/visits/[id]  (T-M17.3 Phase 3 Commit 5)
// ----------------------------------------------------------------------------
// GET returns the same prisma row that /visits/[id]/page.tsx loads
// server-side, so API consumers (Playwright harnesses, future
// integrations) can read a visit without screen-scraping. Slim
// status-only data still lives at /api/visits/[id]/status; this
// route is the full object.
//
// PATCH edits a draft QUEUED visit — the small window between "I
// clicked a capture-mode tile by mistake" and "the pipeline is
// actually running". Once any input lands (audioKey,
// dictationAudioKey, or rawTextInput), the visit becomes immutable
// via this route and the doctor's corrective action is
// Delete-and-retry instead.
//
// Editable fields: patientId, specialty, chiefComplaint, inputMode.
// All optional in the body (undefined = leave unchanged, null clears
// only chiefComplaint — the other three are NOT NULL on the model).
//
// Error shape matches the T-M16.4 classification (code + retry):
//   VISIT_NOT_DRAFT   — status != QUEUED, or any input field has
//                       content. Retry after clearing inputs, or use
//                       Delete instead.
//   VISIT_DELETED     — deletedAt IS NOT NULL (not technically
//                       "deleted" yet but in the 15-day trash window).
//   VISIT_ARCHIVED    — archivedAt IS NOT NULL (impossible today —
//                       only SIGNED visits archive and SIGNED ≠
//                       QUEUED — but the gate is defensive against
//                       future archive-expansion).
//   INVALID_PATIENT   — patientId doesn't exist, belongs to a
//                       different practice, or is soft-deleted.
// ============================================================================

import { z } from "zod";
import { NextResponse } from "next/server";

import prisma from "@meddoc/db";
import { Prisma, TranscribeVisitStatus } from "@prisma/client";
import { SPECIALTY_IDS } from "@meddoc/shared/specialties";

import { apiError, withApiHandler } from "@/lib/api-error";
import { auth } from "@/lib/nextauth";
import { RATE_LIMITS, rateLimitOr429 } from "@/lib/rate-limit";
import { log } from "@/lib/log";
import { logAudit, logRequiredAudit } from "@/lib/audit";
import { isTemplateTwinStagingQaRequested } from "@/lib/template-twin/staging-qa-gate";
import { isOwnedTemplateTwinStagingQaVisit } from "@/lib/template-twin/staging-qa-access";
import { TEMPLATE_TWIN_STAGING_QA_RUN_GUARD_SELECT } from "@/lib/template-twin/staging-qa-visit-guard";
import {
  requireTemplateTwinVisitReadAuthority,
  TemplateTwinVisitReadAuthorityError,
} from "@/lib/template-twin/read-authority";
import {
  requireTemplateTwinSyntheticReadAdmission,
  type TemplateTwinSyntheticReadAdmission,
  TemplateTwinSyntheticReadAdmissionError,
} from "@/lib/template-twin/synthetic-read-admission";
import { TEMPLATE_TWIN_DURABLE_VISIT_EXCLUSION_WHERE } from "@/lib/template-twin/durable-visit-exclusion";
import { currentClinicalVisitActorWhere } from "@/lib/clinical-visit-authority";
import { lockCurrentClinicalPatientAfterActor } from "@/lib/clinical-patient-authority";
import { isSameOriginTemplateTwinMutation } from "@/lib/template-twin/request-security";
import {
  enqueueTemplateTwinClinicalMutationAudit,
  hasDurableTemplateTwinClinicalMutationProvenance,
  loadTemplateTwinClinicalMutationAdmissionTarget,
  lockAndAssertOrdinaryClinicalMutation,
  lockAndAssertTemplateTwinClinicalMutation,
  pinTemplateTwinClinicalMutation,
  TEMPLATE_TWIN_CLINICAL_MUTATION_PROVENANCE_SELECT,
  TemplateTwinClinicalMutationAuthorizationError,
  type TemplateTwinClinicalMutationClaim,
} from "@/lib/template-twin/visit-mutation-authority";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const INPUT_MODES = ["audio_upload", "voice_dictation", "text_notes"] as const;

class InvalidPatientSelectionError extends Error {
  constructor() {
    super("Selected patient is not available.");
    this.name = "InvalidPatientSelectionError";
  }
}

const BodySchema = z.object({
  patientId: z.string().trim().min(1).optional(),
  specialty: z.enum(SPECIALTY_IDS, { message: "Pick a specialty" }).optional(),
  chiefComplaint: z
    .union([z.string().trim().max(500), z.null()])
    .optional()
    .transform((v) => {
      if (v === undefined) return undefined;
      if (v === null) return null;
      return v.length === 0 ? null : v;
    }),
  inputMode: z.enum(INPUT_MODES).optional(),
});

export const GET = withApiHandler<{ id: string }>(
  "api:visits:get",
  async (_req, { params }) => {
    const { id: visitId } = await params;

    const session = await auth();
    const userId = session?.user?.id;
    if (!userId) return apiError("unauthorized", 401);

    let preReadAuthority;
    try {
      preReadAuthority = await requireTemplateTwinVisitReadAuthority({
        db: prisma,
        visitId,
        actorUserId: userId,
      });
    } catch (error) {
      if (error instanceof TemplateTwinVisitReadAuthorityError) {
        return apiError("not found", 404);
      }
      throw error;
    }
    if (preReadAuthority.isTemplateTwin && !preReadAuthority.practiceId) {
      return apiError("not found", 404);
    }
    if (
      isTemplateTwinStagingQaRequested() &&
      !preReadAuthority.isSyntheticTemplateTwin
    ) {
      return apiError("not found", 404);
    }
    let syntheticReadAdmission: TemplateTwinSyntheticReadAdmission | null;
    try {
      syntheticReadAdmission = await requireTemplateTwinSyntheticReadAdmission({
        visitId,
        actorUserId: userId,
        readDecision: preReadAuthority,
      });
    } catch (error) {
      if (error instanceof TemplateTwinSyntheticReadAdmissionError) {
        return apiError("not found", 404);
      }
      throw error;
    }

    const visit = await prisma.transcribeVisit.findFirst({
      where: {
        id: visitId,
        ...currentClinicalVisitActorWhere(userId),
        ...(preReadAuthority.isTemplateTwin
          ? {}
          : TEMPLATE_TWIN_DURABLE_VISIT_EXCLUSION_WHERE),
      },
      select: {
        id: true,
        userId: true,
        patientId: true,
        patientName: true,
        specialty: true,
        chiefComplaint: true,
        inputMode: true,
        status: true,
        signedAt: true,
        deletedAt: true,
        archivedAt: true,
        patient: {
          select: {
            id: true,
            name: true,
            dateOfBirth: true,
            externalId: true,
            mrn: true,
            insurance: true,
            problemList: true,
          },
        },
        createdAt: true,
        updatedAt: true,
        audioKey: true,
        audioMimeType: true,
        audioSizeBytes: true,
        audioDurationSec: true,
        audioUploadedAt: true,
        dictationAudioKey: true,
        dictationDurationSec: true,
        rawTextInput: true,
        transcriptRaw: true,
        transcriptText: true,
        speakerMap: true,
        entities: true,
        soapDraft: true,
        critique: true,
        soapFinal: true,
        signedSoap: true,
        needsReview: true,
        reviewReason: true,
        failureCategory: true,
        manualRetryCount: true,
        processingStartedAt: true,
        processingFinishedAt: true,
        processingCostCents: true,
        icdCodes: true,
        cptCodes: true,
        rxDrafts: true,
        referrals: true,
        patientSummary: true,
        confidenceScores: true,
        templateTwinSyntheticQaRun: {
          select: TEMPLATE_TWIN_STAGING_QA_RUN_GUARD_SELECT,
        },
      },
    });
    // 404 on both "not found" AND "not yours" prevents ID enumeration.
    if (!visit || visit.userId !== userId) return apiError("not found", 404);
    let readAuthority;
    try {
      readAuthority = await requireTemplateTwinVisitReadAuthority({
        db: prisma,
        visitId,
        actorUserId: userId,
        ...(preReadAuthority.isTemplateTwin
          ? {
              expectedPracticeId: preReadAuthority.practiceId!,
              requireTemplateTwin: true,
            }
          : {}),
      });
    } catch (error) {
      if (error instanceof TemplateTwinVisitReadAuthorityError) {
        return apiError("not found", 404);
      }
      throw error;
    }
    let syntheticQaAuditPracticeId = syntheticReadAdmission?.practiceId ?? null;
    if (syntheticReadAdmission) {
      try {
        if (
          visit.templateTwinSyntheticQaRun?.id !==
            syntheticReadAdmission.runId ||
          visit.templateTwinSyntheticQaRun.attempt !==
            syntheticReadAdmission.attempt
        ) {
          return apiError("not found", 404);
        }
        syntheticReadAdmission =
          await requireTemplateTwinSyntheticReadAdmission({
            visitId,
            actorUserId: userId,
            readDecision: readAuthority,
            expected: syntheticReadAdmission,
          });
        if (!syntheticReadAdmission) return apiError("not found", 404);
        syntheticQaAuditPracticeId = syntheticReadAdmission.practiceId;
      } catch (error) {
        if (error instanceof TemplateTwinSyntheticReadAdmissionError) {
          return apiError("not found", 404);
        }
        throw error;
      }
    }

    // Synthetic QA reads are fail-closed and awaited: lifecycle cleanup or
    // another concurrent claim cannot race an unaudited page/API response.
    // Ordinary visits retain the pre-existing best-effort read-audit policy.
    const viewAudit = {
      action: "VIEWED_VISIT",
      targetId: visit.id,
      targetType: "TranscribeVisit",
      metadata: { source: "api:GET /api/visits/[id]" },
    } as const;
    if (readAuthority.isTemplateTwin) {
      const currentPracticeId =
        syntheticQaAuditPracticeId ?? readAuthority.practiceId;
      if (!currentPracticeId) return apiError("not found", 404);
      try {
        await logRequiredAudit({
          ...viewAudit,
          userId,
          practiceId: currentPracticeId,
          templateTwinReadAuthority: {
            expectedPracticeId: currentPracticeId,
          },
        });
      } catch (error) {
        if (error instanceof TemplateTwinVisitReadAuthorityError) {
          return apiError("not found", 404);
        }
        throw error;
      }
    } else {
      void logAudit(viewAudit);
    }

    if (syntheticReadAdmission) {
      try {
        const finalReadAuthority = await requireTemplateTwinVisitReadAuthority({
          db: prisma,
          visitId,
          actorUserId: userId,
          expectedPracticeId: syntheticReadAdmission.practiceId,
          requireTemplateTwin: true,
        });
        const finalAdmission = await requireTemplateTwinSyntheticReadAdmission({
          visitId,
          actorUserId: userId,
          readDecision: finalReadAuthority,
          expected: syntheticReadAdmission,
        });
        if (!finalAdmission) return apiError("not found", 404);
      } catch (error) {
        if (
          error instanceof TemplateTwinVisitReadAuthorityError ||
          error instanceof TemplateTwinSyntheticReadAdmissionError
        ) {
          return apiError("not found", 404);
        }
        throw error;
      }
    }

    const visitDto = { ...visit, templateTwinSyntheticQaRun: undefined };
    return NextResponse.json({ visit: visitDto }, { status: 200 });
  },
);

export const PATCH = withApiHandler<{ id: string }>(
  "api:visits:edit",
  async (req, { params }) => {
    const { id: visitId } = await params;

    const session = await auth();
    const userId = session?.user?.id;
    if (!userId) return apiError("unauthorized", 401);
    if (await isOwnedTemplateTwinStagingQaVisit({ visitId, userId })) {
      return apiError("not found", 404);
    }

    const blocked = rateLimitOr429(RATE_LIMITS.VISIT_OPS, userId);
    if (blocked) return blocked;

    // Classify from identifiers, reserved synthetic identity, and immutable
    // Twin lineage before consuming any requested clinical metadata. Live
    // Twin edits require a current physician/rollout admission and same-origin
    // request; damaged/synthetic lineage remains unavailable here.
    const authorityTarget =
      await loadTemplateTwinClinicalMutationAdmissionTarget({
        visitId,
        actorUserId: userId,
      });
    if (!authorityTarget || authorityTarget.userId !== userId) {
      return apiError("not found", 404);
    }
    let templateTwinMutationClaim: TemplateTwinClinicalMutationClaim | null =
      null;
    if (hasDurableTemplateTwinClinicalMutationProvenance(authorityTarget)) {
      if (!isSameOriginTemplateTwinMutation(req)) {
        return apiError("not found", 404);
      }
      try {
        templateTwinMutationClaim = await pinTemplateTwinClinicalMutation({
          visitId,
          actorUserId: userId,
          admittedVisitUpdatedAt: authorityTarget.updatedAt,
          provenance: authorityTarget,
        });
      } catch (error) {
        if (error instanceof TemplateTwinClinicalMutationAuthorizationError) {
          return apiError("not found", 404);
        }
        throw error;
      }
    }

    let body: unknown;
    try {
      body = await req.json();
    } catch {
      return apiError("invalid JSON body", 400);
    }
    const parsed = BodySchema.safeParse(body);
    if (!parsed.success) {
      const first = parsed.error.issues[0];
      const field = first?.path.join(".") || "_form";
      return NextResponse.json(
        { error: first?.message || "invalid payload", field },
        { status: 400 },
      );
    }

    const visit = await prisma.transcribeVisit.findUnique({
      where: {
        id: visitId,
        ...currentClinicalVisitActorWhere(userId),
        updatedAt: authorityTarget.updatedAt,
        ...(templateTwinMutationClaim
          ? {}
          : TEMPLATE_TWIN_DURABLE_VISIT_EXCLUSION_WHERE),
      },
      select: {
        id: true,
        userId: true,
        updatedAt: true,
        status: true,
        signedAt: true,
        audioKey: true,
        dictationAudioKey: true,
        rawTextInput: true,
        deletedAt: true,
        archivedAt: true,
        specialty: true,
        chiefComplaint: true,
        inputMode: true,
        ...TEMPLATE_TWIN_CLINICAL_MUTATION_PROVENANCE_SELECT,
      },
    });
    if (!visit || visit.userId !== userId) return apiError("not found", 404);
    if (
      Boolean(templateTwinMutationClaim) !==
      hasDurableTemplateTwinClinicalMutationProvenance(visit)
    ) {
      return apiError("The visit changed. Reload and retry.", 409, {
        code: "TEMPLATE_TWIN_MUTATION_CONFLICT",
      });
    }

    if (visit.deletedAt !== null) {
      return NextResponse.json(
        {
          error: "Visit is in trash. Restore it before editing.",
          code: "VISIT_DELETED",
        },
        { status: 400 },
      );
    }
    // archivedAt is impossible here (only SIGNED visits can be archived,
    // and SIGNED ≠ QUEUED), but check defensively for future changes.
    if (visit.archivedAt !== null) {
      return NextResponse.json(
        {
          error: "Archived visits cannot be edited.",
          code: "VISIT_ARCHIVED",
        },
        { status: 400 },
      );
    }

    const noInput =
      visit.audioKey === null &&
      visit.dictationAudioKey === null &&
      (visit.rawTextInput === null || visit.rawTextInput.length === 0);

    if (
      visit.status !== TranscribeVisitStatus.QUEUED ||
      visit.signedAt !== null ||
      !noInput
    ) {
      return NextResponse.json(
        {
          error:
            "Only draft visits (queued with no input uploaded) can be edited. Delete it instead.",
          code: "VISIT_NOT_DRAFT",
        },
        { status: 400 },
      );
    }

    const data: {
      patientId?: string;
      patientName?: string;
      specialty?: string;
      chiefComplaint?: string | null;
      inputMode?: (typeof INPUT_MODES)[number];
    } = {};
    if (
      parsed.data.patientId !== undefined &&
      parsed.data.patientId !== visit.patientId
    ) {
      data.patientId = parsed.data.patientId;
    }
    if (parsed.data.specialty !== undefined) {
      data.specialty = parsed.data.specialty;
    }
    if (parsed.data.chiefComplaint !== undefined) {
      data.chiefComplaint = parsed.data.chiefComplaint;
    }
    if (parsed.data.inputMode !== undefined) {
      data.inputMode = parsed.data.inputMode;
    }

    if (Object.keys(data).length === 0) {
      return NextResponse.json(
        { error: "No fields to update.", field: "_form" },
        { status: 400 },
      );
    }

    let updated: {
      id: string;
      patientId: string;
      specialty: string;
      chiefComplaint: string | null;
      inputMode: string;
      updatedAt: Date;
    } | null = null;
    try {
      updated = await prisma.$transaction(
        async (tx: Prisma.TransactionClient) => {
          if (templateTwinMutationClaim) {
            const locked = await lockAndAssertTemplateTwinClinicalMutation({
              tx,
              claim: templateTwinMutationClaim,
            });
            if (
              locked.status !== TranscribeVisitStatus.QUEUED ||
              locked.signedAt !== null ||
              locked.deletedAt !== null ||
              locked.archivedAt !== null ||
              locked.updatedAt.getTime() !== visit.updatedAt.getTime() ||
              locked.audioKey !== visit.audioKey ||
              locked.dictationAudioKey !== visit.dictationAudioKey ||
              locked.rawTextInput !== visit.rawTextInput ||
              locked.patientId !== visit.patientId ||
              locked.specialty !== visit.specialty ||
              locked.chiefComplaint !== visit.chiefComplaint ||
              locked.inputMode !== visit.inputMode
            ) {
              return null;
            }
          } else {
            await lockAndAssertOrdinaryClinicalMutation({
              tx,
              visitId,
              actorUserId: userId,
              admittedVisitUpdatedAt: authorityTarget.updatedAt,
              admittedPatientId: authorityTarget.patientId,
              admittedNoteTemplateId: authorityTarget.noteTemplateId,
            });
          }

          const writeData = { ...data };
          if (data.patientId && data.patientId !== visit.patientId) {
            const expectedPracticeId =
              templateTwinMutationClaim?.practiceId ?? session.user.practiceId;
            const targetPatient = await lockCurrentClinicalPatientAfterActor({
              tx,
              actor: { userId, practiceId: expectedPracticeId },
              patientId: data.patientId,
            });
            if (!targetPatient) throw new InvalidPatientSelectionError();
            // Denormalised legacy column remains consistent with the exact
            // target patient row held under the same transaction lock.
            writeData.patientName = targetPatient.name;
          }

          const saved = await tx.transcribeVisit.update({
            where: {
              id: visit.id,
              userId,
              updatedAt: visit.updatedAt,
              status: TranscribeVisitStatus.QUEUED,
            },
            data: writeData,
            select: {
              id: true,
              patientId: true,
              specialty: true,
              chiefComplaint: true,
              inputMode: true,
              updatedAt: true,
            },
          });
          if (templateTwinMutationClaim) {
            await enqueueTemplateTwinClinicalMutationAudit({
              tx,
              claim: templateTwinMutationClaim,
              operation: "generic_patch",
              action: "EDITED_NOTE",
              metadata: { changedKeys: Object.keys(data).sort() },
            });
          }
          return saved;
        },
      );
    } catch (error) {
      if (error instanceof InvalidPatientSelectionError) {
        return NextResponse.json(
          {
            error: error.message,
            code: "INVALID_PATIENT",
          },
          { status: 400 },
        );
      }
      if (error instanceof TemplateTwinClinicalMutationAuthorizationError) {
        return apiError(
          templateTwinMutationClaim
            ? "Template Twin authorization changed. Reload and retry."
            : "The visit changed. Reload and retry.",
          409,
          {
            code: templateTwinMutationClaim
              ? "TEMPLATE_TWIN_AUTHORIZATION_CHANGED"
              : "TEMPLATE_TWIN_MUTATION_CONFLICT",
          },
        );
      }
      throw error;
    }
    if (!updated) {
      return apiError("The visit changed. Reload and retry.", 409, {
        code: "TEMPLATE_TWIN_MUTATION_CONFLICT",
      });
    }

    log.info("api:visits:edit", "draft edited", {
      userId,
      visitId,
      changedKeys: Object.keys(data),
    });

    return NextResponse.json({ visit: updated });
  },
);
