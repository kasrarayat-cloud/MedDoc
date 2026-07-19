// ============================================================================
// POST /api/visits/[id]/retry (T-M16.4)
// ----------------------------------------------------------------------------
// Last-ditch "something got stuck" button surfaced by the processing UI
// after 30 min elapsed with no pipeline progress. Re-enqueues the visit
// for the worker with a per-minute idempotent jobId so double-clicks
// collapse into a single retry.
//
// Eligibility:
//   - Session required (owner only — 404 anti-enumeration on mismatch).
//   - visit.status === SIGNED → 409 (nothing to retry, it's terminal).
//   - visit.updatedAt > now - 10 min AND status is an "in-flight"
//     state → 409 + { code: "STILL_PROCESSING" }. A live worker
//     writes to the visit row (status transitions, processingStartedAt,
//     etc.) as each layer runs; a stale updatedAt indicates the worker
//     is probably dead/wedged, safe to re-enqueue. Fresh updatedAt
//     means the worker is likely making progress we don't want to
//     duplicate.
//
// On success: reset visit status to QUEUED, clear reviewReason + the
// processing-finished timestamp, enqueue the retry job. Worker's
// T-M13 resume logic skips whatever layers already completed.
// ============================================================================

import { NextResponse } from "next/server";

import prisma from "@meddoc/db";
import { TranscribeVisitStatus } from "@prisma/client";

import { apiError, withApiHandler } from "@/lib/api-error";
import { AuthError, requireFreshDoctorIdentity } from "@/lib/auth";
import { auth } from "@/lib/nextauth";
import { enqueueProcessVisit } from "@/lib/queue";
import { RATE_LIMITS, rateLimitOr429 } from "@/lib/rate-limit";
import { redactPhi } from "@meddoc/ai";
import { log } from "@/lib/log";
import { logAudit } from "@/lib/audit";
import { isSameOriginTemplateTwinMutation } from "@/lib/template-twin/request-security";
import { TemplateTwinStagingQaDisabledError } from "@/lib/template-twin/staging-qa-gate";
import {
  retryTemplateTwinStagingQaRun,
  TemplateTwinStagingQaError,
  TemplateTwinStagingQaRetryRequestSchema,
} from "@/lib/template-twin/staging-qa-service";
import {
  readBoundedTemplateTwinStagingQaJson,
  TemplateTwinStagingQaRequestError,
} from "@/lib/template-twin/staging-qa-request";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/** How "fresh" updatedAt has to be for the retry to be rejected as
 *  STILL_PROCESSING. A working worker writes the row at every layer
 *  transition (~10s between writes); 10 min covers the longest
 *  single-layer span (a big Deepgram batch + a slow Anthropic polish).
 *  See docs/T-M15-AUDIT-REPORT.md finding H13. */
const STILL_PROCESSING_WINDOW_MS = 10 * 60 * 1000;

/** Statuses that mean "the worker might be running this right now".
 *  Any other status (FAILED, QUEUED) doesn't need the staleness check
 *  — FAILED is an explicit failure, QUEUED means nothing is running. */
/** Hard cap on how many manual /retry POSTs the doctor can issue
 *  against a single visit before the route refuses with 429. Each
 *  retry burns Anthropic + (when relevant) Deepgram tokens; without
 *  a budget a stuck-button loop turns into a serious cost incident.
 *  5 is generous — the BullMQ auto-retry already covered the
 *  transient case 3x before the visit ever hit FAILED, so a doctor
 *  legitimately clicking Try again should usually succeed inside
 *  this budget. */
const MANUAL_RETRY_BUDGET = 5;
const MAX_TEMPLATE_TWIN_RETRY_REQUEST_BYTES = 1024;

const IN_FLIGHT_STATUSES: TranscribeVisitStatus[] = [
  TranscribeVisitStatus.TRANSCRIBING,
  TranscribeVisitStatus.EXTRACTING,
  TranscribeVisitStatus.DRAFTING,
  TranscribeVisitStatus.CRITIQUING,
  TranscribeVisitStatus.POLISHING,
  TranscribeVisitStatus.AUTOMATING,
];

export const POST = withApiHandler<{ id: string }>(
  "api:visits:retry",
  async (_req, { params }) => {
    const { id: visitId } = await params;

    const session = await auth();
    const userId = session?.user?.id;
    if (!userId) return apiError("unauthorized", 401);

    // T-M18.3 A26: retry is a visit-management op (same cadence as
    // delete / archive / restore), not an upload. Aligning the bucket
    // prevents a user cleaning up stale visits from tripping the
    // UPLOAD cost-shield bucket prematurely.
    const blocked = rateLimitOr429(RATE_LIMITS.VISIT_OPS, userId);
    if (blocked) return blocked;

    const visit = await prisma.transcribeVisit.findUnique({
      where: { id: visitId },
      select: {
        id: true,
        userId: true,
        status: true,
        updatedAt: true,
        deletedAt: true,
        archivedAt: true,
        manualRetryCount: true,
        templateTwinSyntheticQaRun: { select: { id: true } },
      },
    });
    if (!visit || visit.userId !== userId) return apiError("not found", 404);

    // A synthetic QA visit must never fall through to the normal retry queue:
    // doing so would drop its exact run/attempt admission and could select a
    // live provider. Route it through the durable staging run ledger instead.
    if (visit.templateTwinSyntheticQaRun) {
      if (!isSameOriginTemplateTwinMutation(_req)) {
        return apiError("not found", 404);
      }
      try {
        const raw = await readBoundedTemplateTwinStagingQaJson(
          _req,
          MAX_TEMPLATE_TWIN_RETRY_REQUEST_BYTES,
        );
        const retryRequest =
          TemplateTwinStagingQaRetryRequestSchema.safeParse(raw);
        if (!retryRequest.success) {
          return apiError(
            "Refresh this synthetic QA run before retrying.",
            400,
          );
        }
        const doctor = await requireFreshDoctorIdentity(userId);
        const email = session?.user?.email;
        if (!email) return apiError("not found", 404);
        const run = await retryTemplateTwinStagingQaRun({
          actor: {
            userId,
            userEmail: email,
            practiceId: doctor.practiceId,
            rolloutToken: doctor.rolloutToken,
          },
          visitId,
          expectedAttempt: retryRequest.data.expectedAttempt,
        });
        return NextResponse.json(
          { ok: true, run },
          {
            status: 202,
            headers: { "Cache-Control": "no-store, private" },
          },
        );
      } catch (error) {
        if (
          error instanceof AuthError ||
          error instanceof TemplateTwinStagingQaDisabledError ||
          (error instanceof TemplateTwinStagingQaError &&
            error.code === "NOT_FOUND")
        ) {
          return apiError("not found", 404);
        }
        if (error instanceof TemplateTwinStagingQaRequestError) {
          return apiError(
            error.message,
            error.code === "REQUEST_TOO_LARGE" ? 413 : 400,
            { code: error.code },
          );
        }
        if (error instanceof TemplateTwinStagingQaError) {
          return apiError(error.message, 409, {
            code: error.code,
            retry: error.code === "QUEUE_UNAVAILABLE",
          });
        }
        throw error;
      }
    }

    if (visit.manualRetryCount >= MANUAL_RETRY_BUDGET) {
      log.warn("api:visits:retry", "budget exhausted", {
        userId,
        visitId,
        count: visit.manualRetryCount,
      });
      void logAudit({
        action: "VISIT_RETRY_BUDGET_EXHAUSTED",
        targetType: "TranscribeVisit",
        targetId: visitId,
        success: false,
        errorCode: "RETRY_BUDGET_EXHAUSTED",
        metadata: { count: visit.manualRetryCount },
      });
      return NextResponse.json(
        {
          error:
            "This visit has been retried multiple times. Please contact support if the issue persists.",
          code: "RETRY_BUDGET_EXHAUSTED",
        },
        { status: 429 },
      );
    }

    if (visit.deletedAt !== null || visit.archivedAt !== null) {
      return NextResponse.json(
        {
          error: "Visit is no longer active. Restore it first.",
          code: "VISIT_NOT_ACTIVE",
        },
        { status: 400 },
      );
    }

    if (visit.status === TranscribeVisitStatus.SIGNED) {
      return NextResponse.json(
        {
          error: "Signed visits cannot be retried.",
          code: "ALREADY_SIGNED",
        },
        { status: 409 },
      );
    }

    const isInFlight = IN_FLIGHT_STATUSES.includes(visit.status);
    const freshlyUpdated =
      Date.now() - visit.updatedAt.getTime() < STILL_PROCESSING_WINDOW_MS;
    if (isInFlight && freshlyUpdated) {
      return NextResponse.json(
        {
          error: "Visit is still processing, please wait.",
          code: "STILL_PROCESSING",
        },
        { status: 409 },
      );
    }

    // Reset + re-enqueue. Resume logic (T-M13) inside processVisit
    // checks column presence; layers that already wrote their output
    // stay skipped, so this isn't a full re-run.
    try {
      await prisma.transcribeVisit.update({
        where: { id: visit.id },
        data: {
          status: TranscribeVisitStatus.QUEUED,
          needsReview: false,
          reviewReason: null,
          failureCategory: null,
          processingFinishedAt: null,
          manualRetryCount: { increment: 1 },
        },
      });
      await enqueueProcessVisit(visitId, userId, { retry: true });
      void logAudit({
        action: "VISIT_RETRY",
        targetType: "TranscribeVisit",
        targetId: visitId,
        metadata: { prevStatus: visit.status },
      });
      log.info("api:visits:retry", "re-enqueued", {
        userId,
        visitId,
        prevStatus: visit.status,
      });
    } catch (err) {
      console.error(
        "[api:visits:retry] enqueue failed:",
        redactPhi(err instanceof Error ? err.message : err),
      );
      return apiError("Could not re-enqueue the visit. Try again.", 502);
    }

    return NextResponse.json({ ok: true }, { status: 200 });
  },
);
