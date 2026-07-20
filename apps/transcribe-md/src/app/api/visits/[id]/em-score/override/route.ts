// ============================================================================
// POST /api/visits/[id]/em-score/override  (Phase 5.2 orphan-completion)
// ----------------------------------------------------------------------------
// Body:    { overrideToCode: EmCode, reason?: string }
// Response: { ok: true, newScore: UiEmScore }
//
// Persists the doctor's E&M override into transcribe_visits.cptCodes
// (under the `em.override` sub-blob), writes an EM_OVERRIDE_APPLIED
// audit row, and returns a freshly-projected UI score so the rail
// re-renders with the doctor-set code on the same network round-trip.
//
// Pre-2026-05-05 the override dropdown dispatched a `qm:em-override`
// CustomEvent that no listener consumed (Bug F-01 in the QA agent's
// 20260505T230801Z report — silent clinical data loss with a lying
// "recorded in audit trail" toast). This route is its server-side
// landing zone; the rail now calls onApplyOverride(code, reason?)
// instead of dispatching.
//
// Refuses signed/locked visits. Refuses archived/deleted visits.
// Returns 404 on ownership mismatch (consistent with rest of /api/visits).
// ============================================================================

import { NextResponse } from "next/server";
import { z } from "zod";

import prisma from "@meddoc/db";
import { Prisma, TranscribeVisitStatus } from "@prisma/client";
import { auth } from "@/lib/nextauth";
import { apiError, withApiHandler } from "@/lib/api-error";
import { computeEmScore } from "@/lib/em-coding/score";
import { engineToUiScore } from "@/lib/em-coding/to-ui-score";
import { extractIcdRows, extractRxRows } from "@/lib/em-coding/displayed-level";
import { currentClinicalVisitActorWhere } from "@/lib/clinical-visit-authority";
import { logAudit } from "@/lib/audit";
import { isSameOriginTemplateTwinMutation } from "@/lib/template-twin/request-security";
import { canonicalSha256 } from "@/lib/template-twin/canonical";
import { TEMPLATE_TWIN_DURABLE_VISIT_EXCLUSION_WHERE } from "@/lib/template-twin/durable-visit-exclusion";
import {
  hasDurableTemplateTwinClinicalMutationProvenance,
  enqueueTemplateTwinClinicalMutationAudit,
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
export const maxDuration = 30;

// AMA 2021 Office E&M code surface (mirrors the rail's union literal).
const EM_CODES = [
  "99202",
  "99203",
  "99204",
  "99205",
  "99211",
  "99212",
  "99213",
  "99214",
  "99215",
] as const;

// Reason is optional + length-capped so a fat-fingered payload can't
// bloat audit metadata.
const MAX_REASON_LENGTH = 240;

const BodySchema = z.object({
  overrideToCode: z.enum(EM_CODES),
  reason: z.string().max(MAX_REASON_LENGTH).optional(),
});

export const POST = withApiHandler<{ id: string }>(
  "api:visits:em-score:override",
  async (req, { params }) => {
    const { id: visitId } = await params;

    const session = await auth();
    const userId = session?.user?.id;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const practiceId = (session?.user as any)?.practiceId as string | undefined;
    if (!userId || !practiceId) return apiError("unauthorized", 401);
    if (!isSameOriginTemplateTwinMutation(req)) {
      return apiError("The override request was not same-origin.", 403, {
        code: "CROSS_SITE_MUTATION",
      });
    }

    // Resolve only ownership and immutable lineage before the request body or
    // any SOAP / coding state is consumed.  Synthetic and pre-certification
    // visits remain on their dedicated immutable evidence paths.
    const authorityTarget =
      await loadTemplateTwinClinicalMutationAdmissionTarget({
        visitId,
        actorUserId: userId,
      });
    if (!authorityTarget || authorityTarget.userId !== userId) {
      return apiError("not found", 404);
    }
    if (
      authorityTarget.templateTwinSyntheticQaRun ||
      authorityTarget.templateTwinSyntheticQaAdmission
    ) {
      return apiError("not found", 404, {
        code: "TEMPLATE_TWIN_STAGING_QA_MUTATION_UNAVAILABLE",
      });
    }
    let templateTwinMutationClaim: TemplateTwinClinicalMutationClaim | null =
      null;
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

    let body: unknown;
    try {
      body = await req.json();
    } catch {
      return apiError("invalid JSON body", 400);
    }
    const parsed = BodySchema.safeParse(body);
    if (!parsed.success) {
      return apiError("invalid override payload", 400, {
        code: "INVALID_REQUEST",
      });
    }

    // Ownership + status gates. 404 on mismatch — never leak existence.
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
        status: true,
        deletedAt: true,
        archivedAt: true,
        signedAt: true,
        updatedAt: true,
        soapDraft: true,
        soapFinal: true,
        audioDurationSec: true,
        dictationDurationSec: true,
        inputMode: true,
        icdCodes: true,
        cptCodes: true,
        rxDrafts: true,
        soapVersion: true,
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
    if (visit.deletedAt !== null || visit.archivedAt !== null) {
      return apiError("Visit is no longer active.", 400, {
        code: "VISIT_NOT_ACTIVE",
      });
    }
    if (
      visit.signedAt !== null ||
      visit.status === TranscribeVisitStatus.SIGNED
    ) {
      return apiError(
        "Visit is signed and locked — override can no longer be set.",
        409,
        { code: "VISIT_LOCKED" },
      );
    }
    // Only allow on visits that have actually completed the pipeline —
    // earlier statuses mean the AI's suggestedCode isn't stable yet, so
    // the override semantics are undefined.
    if (visit.status !== TranscribeVisitStatus.READY) {
      return apiError(
        `Visit is in status ${visit.status}; override requires a READY visit.`,
        409,
        { code: "VISIT_NOT_READY" },
      );
    }

    const currentSoap = visit.soapFinal ?? visit.soapDraft ?? "";
    if (!currentSoap.trim()) {
      return apiError("Visit has no SOAP draft to score.", 400, {
        code: "NO_SOAP_DRAFT",
      });
    }

    // Re-score against the current SOAP so the rail receives a fresh
    // groups/bump payload with the override applied. This route is the one
    // intentionally permitted Twin E/M surface because null forces the
    // deterministic fallback and cannot invoke a provider/cache judge.
    const icdCodes = extractIcdRows(visit.icdCodes);
    const rxDrafts = extractRxRows(visit.rxDrafts);
    const engineScore = await computeEmScore(currentSoap, {
      mdmCachedJudgement: null,
      icdCodes,
      rxDrafts,
    });

    const durationSec =
      visit.inputMode === "voice_dictation"
        ? (visit.dictationDurationSec ?? 0)
        : (visit.audioDurationSec ?? 0);

    const overrideRecord = {
      code: parsed.data.overrideToCode,
      reason: parsed.data.reason,
      overriddenAt: new Date().toISOString(),
    };

    const newUiScore = engineToUiScore(
      engineScore,
      durationSec,
      overrideRecord,
    );

    // cptCodes is a Json column. Merge `em.override` into whatever
    // existing top-level shape lives there (the doctor may have
    // overridden once before; this overwrites). Other top-level keys
    // are preserved.
    const existing = isPlainObject(visit.cptCodes) ? { ...visit.cptCodes } : {};
    const existingEm = isPlainObject(existing.em) ? { ...existing.em } : {};
    const nextCpt = {
      ...existing,
      em: { ...existingEm, override: overrideRecord },
    };

    if (templateTwinMutationClaim) {
      try {
        const applied = await prisma.$transaction(
          async (tx: Prisma.TransactionClient) => {
            const locked = await lockAndAssertTemplateTwinClinicalMutation({
              tx,
              claim: templateTwinMutationClaim,
            });
            if (
              locked.status !== TranscribeVisitStatus.READY ||
              locked.deletedAt !== null ||
              locked.archivedAt !== null ||
              locked.signedAt !== null ||
              emOverrideTargetSha256(locked) !== emOverrideTargetSha256(visit)
            ) {
              return false;
            }
            await tx.transcribeVisit.update({
              where: { id: visitId },
              data: { cptCodes: nextCpt },
            });
            await enqueueTemplateTwinClinicalMutationAudit({
              tx,
              claim: templateTwinMutationClaim,
              operation: "em_override",
              action: "EM_OVERRIDE_APPLIED",
              discriminator: parsed.data.overrideToCode,
              metadata: { overrideCode: parsed.data.overrideToCode },
            });
            return true;
          },
        );
        if (!applied) {
          return apiError(
            "The visit changed before the override was saved. Reload and retry.",
            409,
            { code: "TEMPLATE_TWIN_MUTATION_CONFLICT" },
          );
        }
      } catch (error) {
        if (error instanceof TemplateTwinClinicalMutationAuthorizationError) {
          return apiError(
            "Template Twin authorization changed. Reload and retry.",
            409,
            { code: "TEMPLATE_TWIN_AUTHORIZATION_CHANGED" },
          );
        }
        throw error;
      }
    } else {
      try {
        await prisma.$transaction(async (tx: Prisma.TransactionClient) => {
          await lockAndAssertOrdinaryClinicalMutation({
            tx,
            visitId,
            actorUserId: userId,
            admittedVisitUpdatedAt: authorityTarget.updatedAt,
            admittedPatientId: authorityTarget.patientId,
            admittedNoteTemplateId: authorityTarget.noteTemplateId,
          });
          await tx.transcribeVisit.update({
            where: { id: visitId },
            data: { cptCodes: nextCpt },
          });
        });
      } catch (error) {
        if (error instanceof TemplateTwinClinicalMutationAuthorizationError) {
          return apiError(
            "The visit changed before the override was saved. Reload and retry.",
            409,
            { code: "TEMPLATE_TWIN_MUTATION_CONFLICT" },
          );
        }
        throw error;
      }
    }

    void logAudit({
      action: "EM_OVERRIDE_APPLIED",
      targetType: "transcribe_visit",
      targetId: visitId,
      metadata: {
        fromCode: engineScore.code,
        toCode: parsed.data.overrideToCode,
        reason: parsed.data.reason ?? null,
      },
    });

    return NextResponse.json(
      { ok: true, newScore: newUiScore },
      { status: 200 },
    );
  },
);

// ──────────────────────────────────────────────────────────────────────
// Helpers
// ──────────────────────────────────────────────────────────────────────

function isPlainObject(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

function emOverrideTargetSha256(visit: {
  status: TranscribeVisitStatus;
  deletedAt: Date | null;
  archivedAt: Date | null;
  signedAt: Date | null;
  updatedAt: Date;
  soapDraft: string | null;
  soapFinal: string | null;
  soapVersion: number;
  inputMode: string;
  audioDurationSec: number | null;
  dictationDurationSec: number | null;
  icdCodes: unknown;
  cptCodes: unknown;
  rxDrafts: unknown;
}): string {
  return canonicalSha256({
    status: visit.status,
    deletedAt: visit.deletedAt?.toISOString() ?? null,
    archivedAt: visit.archivedAt?.toISOString() ?? null,
    signedAt: visit.signedAt?.toISOString() ?? null,
    updatedAt: visit.updatedAt.toISOString(),
    soapDraft: visit.soapDraft,
    soapFinal: visit.soapFinal,
    soapVersion: visit.soapVersion,
    inputMode: visit.inputMode,
    audioDurationSec: visit.audioDurationSec,
    dictationDurationSec: visit.dictationDurationSec,
    icdCodes: visit.icdCodes ?? null,
    cptCodes: visit.cptCodes ?? null,
    rxDrafts: visit.rxDrafts ?? null,
  });
}

// E/M signal extractors now come from @/lib/em-coding/displayed-level
// (the single source shared with the rail + sign gate — 2026-06-13).
