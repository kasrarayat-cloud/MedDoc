// ============================================================================
// POST /api/visits/[id]/em-score (Phase 5.2)
// ----------------------------------------------------------------------------
// Body: { soapText: string }
// Response: { ok: true, score: UiEmScore }
//
// Loads the visit, validates ownership, runs the hybrid scoring engine
// (deterministic counts + LLM-judged MDM with Redis cache + fallback).
// Read-only on SOAP data — never writes back to soapNote/soapFinal.
// Coding feedback is COACHING ONLY: the engine returns scores; the
// rail decides display. The Sign action proceeds regardless.
//
// Wire shape: { ok: true, score: <UI-shape> }. The CodingRail consumes
// the UI shape from `lib/em-coding-ui/types` (suggestedCode, groups,
// bump.{...}, timeBand, override, …) — not the raw engine shape from
// `lib/em-coding/types` (code, satisfied, bumpableTo, …). Pre-fix the
// route returned the engine shape directly; the rail's `RescoreResult`
// reader checks `result.ok && result.score`, both of which were
// undefined on the wire, so every doctor edit silently fell through to
// the "Coding feedback temporarily unavailable" branch — including the
// rescore that runs immediately after a successful Bump apply, which
// made the bump look like it had not persisted.
// ============================================================================

import { NextResponse } from "next/server";
import { z } from "zod";
import type { Prisma } from "@prisma/client";

import prisma from "@meddoc/db";
import { auth } from "@/lib/nextauth";
import { apiError, withApiHandler } from "@/lib/api-error";
import { isOwnedTemplateTwinStagingQaVisit } from "@/lib/template-twin/staging-qa-access";
import { isSameOriginTemplateTwinMutation } from "@/lib/template-twin/request-security";
import {
  requireTemplateTwinVisitReadAuthority,
  TemplateTwinVisitReadAuthorityError,
} from "@/lib/template-twin/read-authority";
import { computeEmScore } from "@/lib/em-coding/score";
import { engineToUiScore } from "@/lib/em-coding/to-ui-score";
import {
  hasTemplateTwinProvenance,
  runProviderBackedEmForOrdinaryVisit,
} from "@/lib/em-coding/template-twin-boundary";
import {
  lockAndAssertOrdinaryClinicalMutation,
  TemplateTwinClinicalMutationAuthorizationError,
} from "@/lib/template-twin/visit-mutation-authority";
import { TEMPLATE_TWIN_DURABLE_VISIT_EXCLUSION_WHERE } from "@/lib/template-twin/durable-visit-exclusion";
import { currentClinicalVisitActorWhere } from "@/lib/clinical-visit-authority";
import {
  extractIcdRows,
  extractRxRows,
  extractEmOverride,
} from "@/lib/em-coding/displayed-level";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const maxDuration = 30;

const BodySchema = z.object({
  soapText: z.string().min(1).max(50_000),
});

export const POST = withApiHandler<{ id: string }>(
  "api:visits:em-score",
  async (req, { params }) => {
    const { id: visitId } = await params;

    const session = await auth();
    const userId = session?.user?.id;
    const practiceId = session?.user?.practiceId;
    if (!userId || !practiceId) return apiError("unauthorized", 401);
    if (!isSameOriginTemplateTwinMutation(req)) {
      return apiError("The E/M score request was not same-origin.", 403, {
        code: "CROSS_SITE_MUTATION",
      });
    }
    // The staging flow is provider-isolated. A direct request must not turn a
    // synthetic visit into a live E/M-judge call when its cache is cold.
    if (await isOwnedTemplateTwinStagingQaVisit({ visitId, userId })) {
      return apiError("not found", 404);
    }

    let body: unknown;
    try {
      body = await req.json();
    } catch {
      return apiError("invalid JSON body", 400);
    }
    const parsed = BodySchema.safeParse(body);
    if (!parsed.success) return apiError("invalid soapText payload", 400);

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
    // No synthetic decision may reach the clinical projection below. This
    // includes a full QA run as well as admission-only, pre-certification,
    // provider-ledger, and reserved-patient orphan lineage.
    if (
      preReadAuthority.isSyntheticTemplateTwin ||
      (preReadAuthority.isTemplateTwin && !preReadAuthority.practiceId)
    ) {
      return apiError("not found", 404);
    }

    // Clinical columns are projected only after the identifier-only durable
    // provenance/current-physician admission above.
    const visit = await prisma.transcribeVisit.findUnique({
      where: {
        id: visitId,
        ...currentClinicalVisitActorWhere(userId),
        ...(!preReadAuthority.isTemplateTwin
          ? TEMPLATE_TWIN_DURABLE_VISIT_EXCLUSION_WHERE
          : {}),
      },
      select: {
        id: true,
        userId: true,
        patientId: true,
        noteTemplateId: true,
        updatedAt: true,
        deletedAt: true,
        archivedAt: true,
        patient: { select: { externalId: true } },
        // Pull these for the deterministic fallback's structured signals.
        icdCodes: true,
        rxDrafts: true,
        // Time-band derivation in the UI score.
        inputMode: true,
        audioDurationSec: true,
        dictationDurationSec: true,
        // Existing doctor override hydration so the rail keeps showing
        // the doctor-set code after a re-score (matching page.tsx's
        // initial render path).
        cptCodes: true,
        noteTemplate: {
          select: {
            templateKind: true,
            templateTwinCompiledVersion: { select: { id: true } },
          },
        },
        templateTwinFill: { select: { id: true } },
        templateTwinSyntheticQaRun: { select: { id: true } },
        templateTwinSyntheticQaAdmission: { select: { id: true } },
        templateTwinProviderExecutions: {
          select: { id: true },
          take: 1,
        },
      },
    });
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
    if (visit.deletedAt !== null || visit.archivedAt !== null) {
      return apiError("Visit is no longer active.", 400, {
        code: "VISIT_NOT_ACTIVE",
      });
    }
    const isTemplateTwinVisit = hasTemplateTwinProvenance(visit);
    if (readAuthority.isTemplateTwin !== isTemplateTwinVisit) {
      return apiError("not found", 404);
    }
    if (isTemplateTwinVisit) {
      return apiError(
        "Provider-backed E/M scoring is unavailable for Template Twin visits.",
        409,
        {
          code: "TEMPLATE_TWIN_PROVIDER_BACKED_EM_UNAVAILABLE",
          retry: false,
        },
      );
    }

    // Extract structured signals from the visit row. The Prisma JSON
    // typing is loose; we narrow at the boundary so the engine sees a
    // well-shaped array regardless of older drafts.
    const icdCodes = extractIcdRows(visit.icdCodes);
    const rxDrafts = extractRxRows(visit.rxDrafts);

    const ordinaryProvenanceFence = () =>
      prisma.$transaction((tx: Prisma.TransactionClient) =>
        lockAndAssertOrdinaryClinicalMutation({
          tx,
          visitId,
          actorUserId: userId,
          admittedVisitUpdatedAt: visit.updatedAt,
          admittedPatientId: visit.patientId,
          admittedNoteTemplateId: visit.noteTemplateId,
        }),
      );
    let engineScore;
    try {
      engineScore = await runProviderBackedEmForOrdinaryVisit(
        isTemplateTwinVisit,
        ordinaryProvenanceFence,
        () =>
          computeEmScore(parsed.data.soapText, {
            practiceId,
            visitId,
            userId,
            icdCodes,
            rxDrafts,
          }),
      );
    } catch (error) {
      if (error instanceof TemplateTwinClinicalMutationAuthorizationError) {
        return apiError(
          "The visit changed before E/M scoring. Refresh and try again.",
          409,
          { code: "TEMPLATE_TWIN_MUTATION_CONFLICT", retry: true },
        );
      }
      throw error;
    }
    if (!engineScore) {
      return apiError(
        "Provider-backed E/M scoring is unavailable for Template Twin visits.",
        409,
        {
          code: "TEMPLATE_TWIN_PROVIDER_BACKED_EM_UNAVAILABLE",
          retry: false,
        },
      );
    }

    // Project engine → UI shape (matches page.tsx initial render +
    // override route + apply-additions route). Same three inputs as
    // page.tsx so the rescore wire shape is consistent.
    const durationSec =
      visit.inputMode === "voice_dictation"
        ? (visit.dictationDurationSec ?? 0)
        : (visit.audioDurationSec ?? 0);
    const existingOverride = extractEmOverride(visit.cptCodes);
    const uiScore = engineToUiScore(engineScore, durationSec, existingOverride);

    return NextResponse.json({ ok: true, score: uiScore }, { status: 200 });
  },
);
// E/M signal extractors now live in @/lib/em-coding/displayed-level (the
// single source shared with the sign gate — 2026-06-13 trigger-parity fix).
