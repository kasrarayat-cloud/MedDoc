// ============================================================================
// GET /api/visits/[id]/dictation/audio (T-M5)
// ----------------------------------------------------------------------------
// Streams the dictation audio back to the browser so the Transcript tab
// can render a small <audio> player. Authed and scoped to the visit's
// owner — we never hand out a presigned URL to avoid exposing raw MinIO
// access; the bytes go through the Node runtime with session validation.
// ============================================================================

import { NextResponse } from "next/server";

import { auth } from "@/lib/nextauth";
import prisma from "@meddoc/db";
import { downloadAudio } from "@/lib/minio";

import { apiError, withApiHandler } from "@/lib/api-error";
import { redactPhi } from "@meddoc/ai";
import { logAudit, logRequiredAudit } from "@/lib/audit";
import { isOwnedTemplateTwinStagingQaVisit } from "@/lib/template-twin/staging-qa-access";
import {
  requireTemplateTwinVisitReadAuthority,
  TemplateTwinVisitReadAuthorityError,
} from "@/lib/template-twin/read-authority";
import { TEMPLATE_TWIN_DURABLE_VISIT_EXCLUSION_WHERE } from "@/lib/template-twin/durable-visit-exclusion";
import { currentClinicalVisitActorWhere } from "@/lib/clinical-visit-authority";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export const GET = withApiHandler<{ id: string }>(
  "api:visits:dictation:audio",
  async (_req, { params }) => {
    const { id: visitId } = await params;

    const session = await auth();
    const userId = session?.user?.id;
    if (!userId) return apiError("unauthorized", 401);
    if (await isOwnedTemplateTwinStagingQaVisit({ visitId, userId })) {
      return apiError("not found", 404);
    }

    // Classify before resolving an object key or touching storage. Full
    // synthetic QA is already denied above; this durable check also catches
    // pre-certification voice admissions (which intentionally have no run)
    // and malformed synthetic execution provenance.
    let preReadAuthority;
    try {
      preReadAuthority = await requireTemplateTwinVisitReadAuthority({
        db: prisma,
        visitId,
        actorUserId: userId,
      });
      if (preReadAuthority.isSyntheticTemplateTwin) {
        return apiError("not found", 404);
      }
    } catch (error) {
      if (error instanceof TemplateTwinVisitReadAuthorityError) {
        return apiError("not found", 404);
      }
      throw error;
    }
    if (preReadAuthority.isTemplateTwin && !preReadAuthority.practiceId) {
      return apiError("not found", 404);
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
        userId: true,
        dictationAudioKey: true,
        audioMimeType: true,
      },
    });
    if (!visit || visit.userId !== userId) return apiError("not found", 404);
    if (!visit.dictationAudioKey) {
      return apiError("no dictation recorded", 404);
    }

    let buf: Buffer;
    try {
      buf = await downloadAudio(visit.dictationAudioKey);
    } catch (err) {
      console.error(
        "[api:visits:dictation:audio] download failed:",
        redactPhi(err instanceof Error ? err.message : err),
      );
      return apiError("storage read failed", 502);
    }

    // Reclassify and authorize after the storage read, immediately before
    // bytes can leave the server. A stale session may therefore never race a
    // suspension, role/product change, practice transfer, or newly discovered
    // durable Twin marker into an audio response.
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

    // Round 3 PR-C — §164.312(b) PHI-read audit (A05-P0-004). Audio
    // download is the highest-risk PHI-read surface: full patient voice
    // exits the server. Audited even though the session+ownership gate
    // already protects it.
    const audioAudit = {
      action: "VIEWED_VISIT_AUDIO",
      targetId: visitId,
      targetType: "TranscribeVisit",
      metadata: {
        source: "api:GET /api/visits/[id]/dictation/audio",
        bytes: buf.byteLength,
        mimeType: visit.audioMimeType ?? "audio/webm",
      },
    } as const;
    if (readAuthority.isTemplateTwin) {
      if (!readAuthority.practiceId) return apiError("not found", 404);
      try {
        await logRequiredAudit({
          ...audioAudit,
          userId,
          practiceId: readAuthority.practiceId,
          templateTwinReadAuthority: {
            expectedPracticeId: readAuthority.practiceId,
          },
        });
      } catch (error) {
        if (error instanceof TemplateTwinVisitReadAuthorityError) {
          return apiError("not found", 404);
        }
        throw error;
      }
    } else {
      void logAudit(audioAudit);
    }

    // For 10-min webm clips we return the whole buffer — cheaper to
    // render in one shot than to stream for the browser's audio element.
    // If dictations ever grow beyond a few MB a streaming variant is the
    // obvious follow-up.
    return new NextResponse(buf as unknown as BodyInit, {
      status: 200,
      headers: {
        "Content-Type": visit.audioMimeType ?? "audio/webm",
        "Content-Length": String(buf.byteLength),
        // Disable caching — the bytes are PHI and the session gate is the
        // only thing keeping them private.
        "Cache-Control": "no-store, private",
      },
    });
  },
);
