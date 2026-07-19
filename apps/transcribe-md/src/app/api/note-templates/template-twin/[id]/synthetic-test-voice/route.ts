import { NextResponse } from "next/server";
import { transcribe } from "@meddoc/ai";
import prisma from "@meddoc/db";

import { AuthError, requireDoctorSession } from "@/lib/auth";
import {
  magicBytesMatchClaimedMime,
  sniffAudioMagicBytes,
  SNIFF_MIN_BYTES,
} from "@/lib/audio-sniff";
import { RATE_LIMITS, rateLimitOr429 } from "@/lib/rate-limit";
import {
  boundedMultipartFormData,
  isMultipartFile,
  isSameOriginTemplateTwinMutation,
  TemplateTwinMultipartError,
} from "@/lib/template-twin/request-security";
import {
  runTemplateTwinSyntheticTest,
  TemplateTwinSyntheticTestError,
} from "@/lib/template-twin/synthetic-test";
import { runWithTemplateTwinStagingQaCertificationProvider } from "@/lib/template-twin/staging-qa-certification-provider";
import { TEMPLATE_TWIN_STAGING_QA_VOICE_TRANSCRIPT } from "@/lib/template-twin/staging-qa-fixtures";
import {
  TemplateTwinStagingQaLifecycleGuardError,
  runWithTemplateTwinStagingQaLifecycleGuard,
} from "@/lib/template-twin/staging-qa-lifecycle-guard";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const maxDuration = 120;

const MAX_SYNTHETIC_AUDIO_BYTES = 10 * 1024 * 1024;
const MAX_SYNTHETIC_AUDIO_MULTIPART_BYTES =
  MAX_SYNTHETIC_AUDIO_BYTES + 256 * 1024;
const SHA256 = /^[a-f0-9]{64}$/;

function response(body: unknown, status: number) {
  return NextResponse.json(body, {
    status,
    headers: { "Cache-Control": "no-store, private" },
  });
}

export async function POST(
  request: Request,
  context: { params: Promise<{ id: string }> },
) {
  if (!isSameOriginTemplateTwinMutation(request)) {
    return response(
      { ok: false, error: "The voice-test request was not same-origin." },
      403,
    );
  }
  try {
    const session = await requireDoctorSession();
    const blocked = rateLimitOr429(RATE_LIMITS.UPLOAD, session.user.id);
    if (blocked) return blocked;
    const contentLength = Number(request.headers.get("content-length") ?? "0");
    if (
      Number.isFinite(contentLength) &&
      contentLength > MAX_SYNTHETIC_AUDIO_BYTES + 256 * 1024
    ) {
      return response(
        { ok: false, error: "Synthetic recordings must be 10 MB or smaller." },
        413,
      );
    }
    const { id } = await context.params;
    const form = await boundedMultipartFormData(
      request,
      MAX_SYNTHETIC_AUDIO_MULTIPART_BYTES,
    );
    const file = form.get("audio");
    const expectedMappingsSha256 = form.get("expectedMappingsSha256");
    const expectedFieldIntentsSha256 = form.get("expectedFieldIntentsSha256");
    if (
      !isMultipartFile(file) ||
      typeof expectedMappingsSha256 !== "string" ||
      (expectedFieldIntentsSha256 !== null &&
        typeof expectedFieldIntentsSha256 !== "string")
    ) {
      return response(
        { ok: false, error: "Record synthetic audio before running the test." },
        400,
      );
    }
    if (
      !SHA256.test(expectedMappingsSha256) ||
      (typeof expectedFieldIntentsSha256 === "string" &&
        !SHA256.test(expectedFieldIntentsSha256))
    ) {
      return response(
        {
          ok: false,
          error: "The mapping version changed. Reload before testing.",
        },
        409,
      );
    }
    const ownedTemplate = await prisma.noteTemplate.findFirst({
      where: {
        id,
        doctorId: session.user.id,
        templateKind: "template_twin_docx",
      },
      select: {
        templateTwinCompiledVersion: {
          select: {
            certificationStatus: true,
            sourceArtifact: {
              select: {
                practiceId: true,
                sha256: true,
                sizeBytes: true,
              },
            },
          },
        },
      },
    });
    if (
      !ownedTemplate?.templateTwinCompiledVersion ||
      ownedTemplate.templateTwinCompiledVersion.sourceArtifact.practiceId !==
        session.user.practiceId
    ) {
      return response(
        {
          ok: false,
          error: "This Template Twin version is stale or unavailable.",
        },
        404,
      );
    }
    if (
      ownedTemplate.templateTwinCompiledVersion.certificationStatus ===
      "CERTIFIED"
    ) {
      return response(
        { ok: false, error: "This template version is already certified." },
        409,
      );
    }
    if (file.size < SNIFF_MIN_BYTES || file.size > MAX_SYNTHETIC_AUDIO_BYTES) {
      return response(
        {
          ok: false,
          error: "Synthetic recordings must be non-empty and 10 MB or smaller.",
        },
        413,
      );
    }
    const audio = Buffer.from(await file.arrayBuffer());
    const claimedMime =
      file.type.split(";")[0]?.trim().toLowerCase() || "audio/webm";
    const sniff = sniffAudioMagicBytes(
      audio.subarray(0, Math.max(SNIFF_MIN_BYTES, 32)),
    );
    if (!magicBytesMatchClaimedMime(sniff.detected, claimedMime)) {
      return response(
        {
          ok: false,
          error: "The synthetic recording format is invalid or unsupported.",
        },
        415,
      );
    }

    // The certification recorder is explicitly synthetic-only and ephemeral:
    // bytes go through the existing transcription orchestrator and are never
    // written to object storage or application logs. Cross-provider Whisper
    // fallback remains disabled at this boundary.
    const actor = {
      userId: session.user.id,
      userEmail: session.user.email,
      practiceId: session.user.practiceId,
      rolloutToken: session.templateTwinRolloutToken,
    };
    const workspace = await runWithTemplateTwinStagingQaLifecycleGuard({
      noteTemplateId: id,
      actor,
      purpose: "synthetic-test-voice",
      evidenceText: TEMPLATE_TWIN_STAGING_QA_VOICE_TRANSCRIPT,
      requireConfirmedMappings: true,
      expectedMappingConfirmation: {
        mappingsSha256: expectedMappingsSha256,
        ...(typeof expectedFieldIntentsSha256 === "string"
          ? { fieldIntentsSha256: expectedFieldIntentsSha256 }
          : {}),
      },
      isExpectedBusinessError: (error) =>
        error instanceof TemplateTwinSyntheticTestError,
      operation: async () => {
        const transcription =
          await runWithTemplateTwinStagingQaCertificationProvider({
            source: {
              sha256:
                ownedTemplate.templateTwinCompiledVersion.sourceArtifact.sha256,
              sizeBytes:
                ownedTemplate.templateTwinCompiledVersion.sourceArtifact
                  .sizeBytes,
            },
            noteTemplateId: id,
            doctorId: session.user.id,
            practiceId: session.user.practiceId,
            rolloutToken: session.templateTwinRolloutToken,
            encounterMode: "dictation",
            expectedMappingConfirmation: {
              mappingsSha256: expectedMappingsSha256,
              ...(typeof expectedFieldIntentsSha256 === "string"
                ? { fieldIntentsSha256: expectedFieldIntentsSha256 }
                : {}),
            },
            evidenceText: TEMPLATE_TWIN_STAGING_QA_VOICE_TRANSCRIPT,
            operation: (providerVisitId) =>
              transcribe({
                practiceId: session.user.practiceId,
                userId: session.user.id,
                visitId: providerVisitId,
                purpose: "tm_transcribe",
                audio,
                mimeType: sniff.detected!,
                allowCrossProviderFallback: false,
                deepgram: { options: { diarize: false, utterances: false } },
              }),
          });
        if (transcription.transcript.trim().length < 10) {
          throw new TemplateTwinSyntheticTestError(
            "VALIDATION_FAILED",
            "The synthetic recording was too short to test safely.",
          );
        }
        return runTemplateTwinSyntheticTest({
          noteTemplateId: id,
          actor,
          expectedMappingsSha256,
          expectedFieldIntentsSha256:
            typeof expectedFieldIntentsSha256 === "string"
              ? expectedFieldIntentsSha256
              : undefined,
          encounterText: transcription.transcript,
          encounterMode: "dictation",
        });
      },
    });
    return response({ ok: true, workspace }, 200);
  } catch (error) {
    if (error instanceof AuthError) {
      return response(
        {
          ok: false,
          error:
            error.code === "FORBIDDEN"
              ? error.message
              : "Sign in again before testing.",
        },
        error.code === "FORBIDDEN" ? 403 : 401,
      );
    }
    if (error instanceof TemplateTwinSyntheticTestError) {
      const status =
        error.code === "NOT_FOUND"
          ? 404
          : error.code === "VALIDATION_FAILED" ||
              error.code === "MAPPINGS_NOT_READY" ||
              error.code === "SYNTHETIC_EVIDENCE_REJECTED" ||
              error.code === "SOURCE_PROVENANCE_INVALID"
            ? 422
            : 409;
      return response({ ok: false, error: error.message }, status);
    }
    if (error instanceof TemplateTwinStagingQaLifecycleGuardError) {
      return response(
        {
          ok: false,
          code: "VERSION_STALE",
          recoverable: true,
          error:
            "This Template Twin version is stale or unavailable. Refresh the certification workspace to continue.",
        },
        409,
      );
    }
    if (error instanceof TemplateTwinMultipartError) {
      return response(
        { ok: false, error: "Synthetic recordings must be 10 MB or smaller." },
        error.code === "MULTIPART_TOO_LARGE" ? 413 : 400,
      );
    }
    return response(
      {
        ok: false,
        error:
          "The synthetic voice test did not pass transcription and document verification.",
      },
      503,
    );
  }
}
