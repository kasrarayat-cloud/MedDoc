// ============================================================================
// POST /api/visits/[id]/text (T-M5)
// ----------------------------------------------------------------------------
// Accepts a JSON body { text: string } and kicks off the text-mode
// pipeline (L3 text variant → L4 → L5 → L6; no transcription).
//
// One-shot: the route 409s if rawTextInput is already populated so a
// click-thrash can't re-submit and duplicate the pipeline run.
// ============================================================================

import { NextResponse } from "next/server";
import { z } from "zod";

import { auth } from "@/lib/nextauth";
import prisma from "@meddoc/db";
import { Prisma, TranscribeVisitStatus } from "@prisma/client";
import { enqueueProcessVisit } from "@/lib/queue";

import { apiError, withApiHandler } from "@/lib/api-error";
import { RATE_LIMITS, rateLimitOr429 } from "@/lib/rate-limit";
import { redactPhi } from "@meddoc/ai";
import { logAudit } from "@/lib/audit";
import { currentClinicalVisitActorWhere } from "@/lib/clinical-visit-authority";
import { isOwnedTemplateTwinStagingQaVisit } from "@/lib/template-twin/staging-qa-access";
import { isSameOriginTemplateTwinMutation } from "@/lib/template-twin/request-security";
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

const MIN_CHARS = 30;
// Round 3 PR-J — A07-P1 server-side ceiling. 5000 chars covers a
// dense paragraph of typed shorthand; anything past that is either
// pasted PHI (probably accidental) or an attack surface.
const MAX_CHARS = 5000;

const BodySchema = z.object({
  text: z.string().min(MIN_CHARS).max(MAX_CHARS),
});

export const POST = withApiHandler<{ id: string }>(
  "api:visits:text",
  async (req, { params }) => {
    const { id: visitId } = await params;

    const session = await auth();
    const userId = session?.user?.id;
    if (!userId) return apiError("unauthorized", 401);
    if (await isOwnedTemplateTwinStagingQaVisit({ visitId, userId })) {
      return apiError("not found", 404);
    }

    const blocked = rateLimitOr429(RATE_LIMITS.UPLOAD, userId);
    if (blocked) return blocked;

    // Inspect only PHI-free provenance before reading the caller's clinical
    // text. Live Twin mutations require same-origin and a fresh physician /
    // rollout admission; synthetic, pre-certification, and damaged lineage
    // never consume the body through this generic route.
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
    if (
      authorityTarget?.userId === userId &&
      hasDurableTemplateTwinClinicalMutationProvenance(authorityTarget)
    ) {
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
      // Round 3 PR-J — audit the rejection so a flood of oversize
      // attempts surfaces in the audit log even when no DB write
      // occurs. Length-only metadata; never log the rejected
      // content (could be partial PHI).
      const rawLen =
        typeof (body as { text?: unknown })?.text === "string"
          ? (body as { text: string }).text.length
          : null;
      const tooLong = typeof rawLen === "number" && rawLen > MAX_CHARS;
      if (tooLong) {
        void logAudit({
          action: "TEXT_INPUT_REJECTED_TOO_LARGE",
          targetType: "transcribe_visit",
          targetId: visitId,
          success: false,
          errorCode: "TEXT_TOO_LONG",
          metadata: { length: rawLen, maxChars: MAX_CHARS },
        });
      }
      return apiError(`text must be ${MIN_CHARS}-${MAX_CHARS} characters`, 400);
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
        inputMode: true,
        status: true,
        rawTextInput: true,
        deletedAt: true,
        archivedAt: true,
        ...TEMPLATE_TWIN_CLINICAL_MUTATION_PROVENANCE_SELECT,
      },
    });
    if (!visit || visit.userId !== userId) return apiError("not found", 404);
    if (visit.deletedAt !== null || visit.archivedAt !== null) {
      return apiError("Visit is no longer active. Restore it first.", 400, {
        code: "VISIT_NOT_ACTIVE",
      });
    }
    if (visit.inputMode !== "text_notes") {
      return apiError("this visit is not a text-to-SOAP visit", 400);
    }
    if (visit.rawTextInput?.trim()) {
      return apiError("text has already been submitted for this visit", 409);
    }
    if (visit.status !== TranscribeVisitStatus.QUEUED) {
      return apiError("visit is already processing or finalized", 409);
    }
    if (
      !templateTwinMutationClaim &&
      hasDurableTemplateTwinClinicalMutationProvenance(visit)
    ) {
      return apiError("The visit changed. Reload and retry.", 409, {
        code: "TEMPLATE_TWIN_MUTATION_CONFLICT",
      });
    }

    const updateData = {
      rawTextInput: parsed.data.text,
      status: TranscribeVisitStatus.QUEUED,
      needsReview: false,
      reviewReason: null,
      processingStartedAt: null,
      processingFinishedAt: null,
      processingCostCents: null,
    } as const;
    if (templateTwinMutationClaim) {
      try {
        const applied = await prisma.$transaction(
          async (tx: Prisma.TransactionClient) => {
            const locked = await lockAndAssertTemplateTwinClinicalMutation({
              tx,
              claim: templateTwinMutationClaim,
            });
            if (
              locked.status !== TranscribeVisitStatus.QUEUED ||
              locked.updatedAt.getTime() !== visit.updatedAt.getTime() ||
              locked.inputMode !== "text_notes" ||
              Boolean(locked.rawTextInput?.trim()) ||
              locked.deletedAt !== null ||
              locked.archivedAt !== null ||
              locked.signedAt !== null
            ) {
              return false;
            }
            await tx.transcribeVisit.update({
              where: { id: visitId },
              data: updateData,
            });
            await enqueueTemplateTwinClinicalMutationAudit({
              tx,
              claim: templateTwinMutationClaim,
              operation: "text_submit",
              action: "EDITED_NOTE",
              metadata: { inputMode: "text_notes" },
            });
            return true;
          },
        );
        if (!applied) {
          return apiError("The visit changed. Reload and retry.", 409, {
            code: "TEMPLATE_TWIN_MUTATION_CONFLICT",
          });
        }
      } catch (error) {
        if (error instanceof TemplateTwinClinicalMutationAuthorizationError) {
          return apiError("Template Twin authorization changed.", 409, {
            code: "TEMPLATE_TWIN_AUTHORIZATION_CHANGED",
          });
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
            data: updateData,
          });
        });
      } catch (error) {
        if (error instanceof TemplateTwinClinicalMutationAuthorizationError) {
          return apiError("The visit changed. Reload and retry.", 409, {
            code: "TEMPLATE_TWIN_MUTATION_CONFLICT",
          });
        }
        throw error;
      }
    }

    try {
      await enqueueProcessVisit(visitId, userId);
    } catch (err) {
      console.error(
        "[api:visits:text] queue enqueue failed:",
        redactPhi(err instanceof Error ? err.message : err),
      );
      return apiError(
        "text stored but worker enqueue failed; please refresh and try again",
        502,
      );
    }

    return NextResponse.json({ visitId, status: "QUEUED" }, { status: 202 });
  },
);
