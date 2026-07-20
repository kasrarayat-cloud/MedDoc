// ============================================================================
// POST /api/visits/[id]/em-score/apply-additions  (Phase 5.2 stub completion)
// ----------------------------------------------------------------------------
// Body: { additions: Array<{ criterionId: string; text: string }> }
// Response: { ok: true, newScore: UiEmScore, applied: number, skipped: number }
//
// Persists doctor-edited bump-modal additions into the visit's
// soapDraft, re-runs the L7b CPT scorer against the new SOAP, writes
// an EM_BUMP_APPLIED audit row, and returns the new UI-shaped EmScore
// so the rail can re-render with the bumped code (e.g. 99213 → 99214)
// without a full page reload.
//
// Refuses signed/locked visits (status=SIGNED or signedAt set). Refuses
// archived/deleted visits. Returns 404 on ownership mismatch consistent
// with the rest of the visits API.
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
import { mergeAdditions } from "@/lib/em-coding/merge-additions";
import { currentClinicalVisitActorWhere } from "@/lib/clinical-visit-authority";
import { hasDurableTemplateTwinVisitProvenance } from "@/lib/template-twin/durable-visit-provenance";
import { TEMPLATE_TWIN_DURABLE_VISIT_EXCLUSION_WHERE } from "@/lib/template-twin/durable-visit-exclusion";
import { logAudit } from "@/lib/audit";
import { invalidateTemplateTwinAfterSoapEdit } from "@/lib/template-twin/soap-binding";
import { isSameOriginTemplateTwinMutation } from "@/lib/template-twin/request-security";
import {
  hasDurableTemplateTwinClinicalMutationProvenance,
  loadTemplateTwinClinicalMutationAdmissionTarget,
  lockAndAssertOrdinaryClinicalMutation,
  TemplateTwinClinicalMutationAuthorizationError,
} from "@/lib/template-twin/visit-mutation-authority";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const maxDuration = 30;

// Conservative caps so a malicious or fat-fingered payload can't bloat
// the soapDraft or burn through the request.
const MAX_ADDITIONS = 20;
const MAX_TEXT_LENGTH = 4000;

const AdditionSchema = z.object({
  criterionId: z.string().min(1).max(120),
  text: z.string().max(MAX_TEXT_LENGTH),
});

const BodySchema = z.object({
  additions: z.array(AdditionSchema).min(1).max(MAX_ADDITIONS),
});

export const POST = withApiHandler<{ id: string }>(
  "api:visits:em-score:apply-additions",
  async (req, { params }) => {
    const { id: visitId } = await params;

    const session = await auth();
    const userId = session?.user?.id;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const practiceId = (session?.user as any)?.practiceId as string | undefined;
    if (!userId || !practiceId) return apiError("unauthorized", 401);
    if (!isSameOriginTemplateTwinMutation(req)) {
      return apiError("The additions request was not same-origin.", 403, {
        code: "CROSS_SITE_MUTATION",
      });
    }

    // Provider-backed additions are intentionally unsupported for every
    // durable Twin state. Classify from PHI-minimal immutable lineage before
    // reading the additions body or selecting SOAP/coding state.
    const authorityTarget =
      await loadTemplateTwinClinicalMutationAdmissionTarget({
        visitId,
        actorUserId: userId,
      });
    if (!authorityTarget || authorityTarget.userId !== userId) {
      return apiError("not found", 404);
    }
    if (authorityTarget.templateTwinSyntheticQaRun) {
      return apiError("not found", 404, {
        code: "TEMPLATE_TWIN_STAGING_QA_MUTATION_UNAVAILABLE",
      });
    }
    if (hasDurableTemplateTwinClinicalMutationProvenance(authorityTarget)) {
      return apiError(
        "Provider-backed E/M additions are unavailable for Template Twin visits.",
        409,
        {
          code: "TEMPLATE_TWIN_PROVIDER_BACKED_EM_UNAVAILABLE",
          retry: false,
        },
      );
    }

    let body: unknown;
    try {
      body = await req.json();
    } catch {
      return apiError("invalid JSON body", 400);
    }
    const parsed = BodySchema.safeParse(body);
    if (!parsed.success) {
      return apiError("invalid additions payload", 400, {
        code: "INVALID_REQUEST",
      });
    }

    // Ownership + status gates. 404 on mismatch — never leak existence.
    const visit = await prisma.transcribeVisit.findUnique({
      where: {
        id: visitId,
        ...currentClinicalVisitActorWhere(userId),
        updatedAt: authorityTarget.updatedAt,
        ...TEMPLATE_TWIN_DURABLE_VISIT_EXCLUSION_WHERE,
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
        soapVersion: true,
        audioDurationSec: true,
        dictationDurationSec: true,
        inputMode: true,
        icdCodes: true,
        rxDrafts: true,
        patient: { select: { externalId: true } },
        templateTwinSyntheticQaRun: { select: { id: true } },
        noteTemplate: {
          select: {
            templateKind: true,
            templateTwinCompiledVersion: { select: { id: true } },
          },
        },
        templateTwinFill: { select: { id: true } },
        templateTwinSyntheticQaAdmission: { select: { id: true } },
        templateTwinProviderExecutions: { select: { id: true }, take: 1 },
      },
    });
    if (!visit || visit.userId !== userId) return apiError("not found", 404);
    if (hasDurableTemplateTwinVisitProvenance(visit)) {
      return apiError(
        "Provider-backed E/M additions are unavailable for Template Twin visits.",
        409,
        {
          code: "TEMPLATE_TWIN_PROVIDER_BACKED_EM_UNAVAILABLE",
          retry: false,
        },
      );
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
        "Visit is signed and locked — additions can no longer be applied.",
        409,
        { code: "VISIT_LOCKED" },
      );
    }
    // Only allow on visits that have actually completed the pipeline.
    // Earlier statuses mean the SOAP isn't stable yet.
    if (visit.status !== TranscribeVisitStatus.READY) {
      return apiError(
        `Visit is in status ${visit.status}; bump additions require a READY visit.`,
        409,
        { code: "VISIT_NOT_READY" },
      );
    }

    const currentSoap = visit.soapFinal ?? visit.soapDraft ?? "";
    if (!currentSoap.trim()) {
      return apiError("Visit has no SOAP draft to apply additions to.", 400, {
        code: "NO_SOAP_DRAFT",
      });
    }

    // Merge the additions into the SOAP. Pure function — testable
    // without the DB.
    const merge = mergeAdditions(currentSoap, parsed.data.additions);

    // Re-establish the ordinary-only decision in a short linearizable claim
    // immediately before model/cache egress. The admission projection alone
    // cannot prevent a durable relation from appearing after its read.
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
      });
    } catch (error) {
      if (error instanceof TemplateTwinClinicalMutationAuthorizationError) {
        return apiError(
          "The visit changed. Reload before applying additions.",
          409,
          {
            code: "TEMPLATE_TWIN_MUTATION_CONFLICT",
          },
        );
      }
      throw error;
    }

    // Re-score against the new SOAP using the LLM MDM judge path.
    //
    // Pre-2026-05-11 the route passed `mdmCachedJudgement: null` to
    // force the deterministic fallback "for synchronous + deterministic
    // behaviour." That broke the bump UX: the deterministic counter
    // reads structured ICD codes + Rx warnings from the SOAP, not the
    // free-text additions the BumpModal writes into Assessment. So the
    // MDM tier never moved on a successful bump and the rail kept
    // showing the pre-bump code (e.g. 99212 stays 99212 even when the
    // doctor's addition was the exact gap-filler the rubric prompted
    // for). Every EM_BUMP_APPLIED audit row from the 22-day production
    // window had `toCode === fromCode`.
    //
    // The LLM judge path (`judgeMdm` — purpose=`judge`) reads the SOAP
    // prose and re-evaluates MDM tier. p95 latency 11s in production —
    // well inside the route's maxDuration=30 — so the synchronous
    // concern was over-cautious. `priorSoap: currentSoap` lets the
    // cache's drift bypass fire when the additions move the SOAP
    // enough (>20% drift) so we don't return a stale cached judgement
    // built on the pre-bump body.
    const icdCodes = extractIcdRows(visit.icdCodes);
    const rxDrafts = extractRxRows(visit.rxDrafts);
    const engineScore = await computeEmScore(merge.newSoap, {
      practiceId,
      visitId,
      userId,
      icdCodes,
      rxDrafts,
      priorSoap: currentSoap,
    });

    // The provider result is usable only while the same ordinary-visit claim
    // still holds. Re-check on return, then repeat once more inside the final
    // write transaction to close both concurrency windows.
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
      });
    } catch (error) {
      if (error instanceof TemplateTwinClinicalMutationAuthorizationError) {
        return apiError(
          "The visit changed. Reload before applying additions.",
          409,
          {
            code: "TEMPLATE_TWIN_MUTATION_CONFLICT",
          },
        );
      }
      throw error;
    }

    const durationSec =
      visit.inputMode === "voice_dictation"
        ? (visit.dictationDurationSec ?? 0)
        : (visit.audioDurationSec ?? 0);
    const newUiScore = engineToUiScore(engineScore, durationSec);

    // Persist. Both columns updated so:
    //   soapDraft  → the rail's source of truth for re-score POSTs
    //   soapFinal  → what the renderer + sign action read
    // The pre-merge soapFinal is preserved as soapL6Original (set by
    // L6 polish; not touched here so the original-AI-output snapshot
    // remains immutable for the doctor-edit-pattern capture path).
    let updated: { count: number };
    try {
      updated = await prisma.$transaction(
        async (tx: Prisma.TransactionClient) => {
          await lockAndAssertOrdinaryClinicalMutation({
            tx,
            visitId,
            actorUserId: userId,
            admittedVisitUpdatedAt: authorityTarget.updatedAt,
            admittedPatientId: authorityTarget.patientId,
            admittedNoteTemplateId: authorityTarget.noteTemplateId,
          });
          const saved = await tx.transcribeVisit.updateMany({
            where: {
              id: visitId,
              userId,
              status: TranscribeVisitStatus.READY,
              deletedAt: null,
              archivedAt: null,
              signedAt: null,
              updatedAt: visit.updatedAt,
              soapDraft: visit.soapDraft,
              soapFinal: visit.soapFinal,
              soapVersion: visit.soapVersion,
              ...TEMPLATE_TWIN_DURABLE_VISIT_EXCLUSION_WHERE,
            },
            data: {
              soapDraft: merge.newSoap,
              soapFinal: merge.newSoap,
              soapVersion: { increment: 1 },
            },
          });
          if (saved.count === 1) {
            await invalidateTemplateTwinAfterSoapEdit(tx, visitId);
          }
          return saved;
        },
      );
    } catch (error) {
      if (error instanceof TemplateTwinClinicalMutationAuthorizationError) {
        return apiError(
          "The visit changed. Reload before applying additions.",
          409,
          {
            code: "TEMPLATE_TWIN_MUTATION_CONFLICT",
          },
        );
      }
      throw error;
    }
    if (updated.count !== 1) {
      return apiError(
        "The note changed in another tab. Reload before applying additions.",
        409,
        { code: "SOAP_VERSION_CONFLICT" },
      );
    }

    // Audit row. Metadata carries the from→to code pair + per-criterion
    // counts; never the addition text itself (PHI).
    void logAudit({
      action: "EM_BUMP_APPLIED",
      targetType: "transcribe_visit",
      targetId: visitId,
      metadata: {
        fromCode: engineScore.code,
        // toCode comes from the engine's bumpableTo — may be null if
        // the additions resolved the gap and the new score IS the
        // target tier. In that case the rail's `score.suggestedCode`
        // moved (e.g. 99213 → 99214); we record it explicitly so
        // forensics can see the transition.
        toCode: newUiScore.suggestedCode,
        appliedCount: merge.applied.length,
        skippedCount: merge.skipped.length,
        criterionIds: merge.applied.map((a) => a.criterionId),
      },
    });

    return NextResponse.json(
      {
        ok: true,
        newScore: newUiScore,
        applied: merge.applied.length,
        skipped: merge.skipped.length,
      },
      { status: 200 },
    );
  },
);

// ──────────────────────────────────────────────────────────────────────
// JSON column normalisers — copied from /api/visits/[id]/em-score/route.ts
// to keep the two routes' wire-shape handling consistent. If a third
// route ever needs them, lift to a shared util.
// ──────────────────────────────────────────────────────────────────────

// E/M signal extractors now come from @/lib/em-coding/displayed-level
// (the single source shared with the rail + sign gate — 2026-06-13).
