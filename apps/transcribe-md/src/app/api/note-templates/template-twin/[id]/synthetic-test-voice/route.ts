import { NextResponse } from 'next/server';
import { transcribe } from '@meddoc/ai';
import prisma from '@meddoc/db';

import { AuthError, requireDoctorSession } from '@/lib/auth';
import {
  magicBytesMatchClaimedMime,
  sniffAudioMagicBytes,
  SNIFF_MIN_BYTES,
} from '@/lib/audio-sniff';
import { RATE_LIMITS, rateLimitOr429 } from '@/lib/rate-limit';
import { isSameOriginTemplateTwinMutation } from '@/lib/template-twin/request-security';
import {
  runTemplateTwinSyntheticTest,
  TemplateTwinSyntheticTestError,
} from '@/lib/template-twin/synthetic-test';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';
export const maxDuration = 120;

const MAX_SYNTHETIC_AUDIO_BYTES = 10 * 1024 * 1024;
const SHA256 = /^[a-f0-9]{64}$/;

function response(body: unknown, status: number) {
  return NextResponse.json(body, {
    status,
    headers: { 'Cache-Control': 'no-store, private' },
  });
}

export async function POST(
  request: Request,
  context: { params: Promise<{ id: string }> },
) {
  if (!isSameOriginTemplateTwinMutation(request)) {
    return response({ ok: false, error: 'The voice-test request was not same-origin.' }, 403);
  }
  try {
    const session = await requireDoctorSession();
    const blocked = rateLimitOr429(RATE_LIMITS.UPLOAD, session.user.id);
    if (blocked) return blocked;
    const contentLength = Number(request.headers.get('content-length') ?? '0');
    if (
      Number.isFinite(contentLength) &&
      contentLength > MAX_SYNTHETIC_AUDIO_BYTES + 256 * 1024
    ) {
      return response({ ok: false, error: 'Synthetic recordings must be 10 MB or smaller.' }, 413);
    }
    const { id } = await context.params;
    const form = await request.formData();
    const file = form.get('audio');
    const expectedMappingsSha256 = form.get('expectedMappingsSha256');
    if (!(file instanceof File) || typeof expectedMappingsSha256 !== 'string') {
      return response({ ok: false, error: 'Record synthetic audio before running the test.' }, 400);
    }
    if (!SHA256.test(expectedMappingsSha256)) {
      return response({ ok: false, error: 'The mapping version changed. Reload before testing.' }, 409);
    }
    const ownedTemplate = await prisma.noteTemplate.findFirst({
      where: {
        id,
        doctorId: session.user.id,
        templateKind: 'template_twin_docx',
      },
      select: {
        templateTwinCompiledVersion: {
          select: {
            certificationStatus: true,
            sourceArtifact: { select: { practiceId: true } },
          },
        },
      },
    });
    if (
      !ownedTemplate?.templateTwinCompiledVersion ||
      ownedTemplate.templateTwinCompiledVersion.sourceArtifact.practiceId !==
        session.user.practiceId
    ) {
      return response({ ok: false, error: 'Template Twin version not found.' }, 404);
    }
    if (
      ownedTemplate.templateTwinCompiledVersion.certificationStatus ===
      'CERTIFIED'
    ) {
      return response({ ok: false, error: 'This template version is already certified.' }, 409);
    }
    if (file.size < SNIFF_MIN_BYTES || file.size > MAX_SYNTHETIC_AUDIO_BYTES) {
      return response({ ok: false, error: 'Synthetic recordings must be non-empty and 10 MB or smaller.' }, 413);
    }
    const audio = Buffer.from(await file.arrayBuffer());
    const claimedMime = file.type.split(';')[0]?.trim().toLowerCase() || 'audio/webm';
    const sniff = sniffAudioMagicBytes(
      audio.subarray(0, Math.max(SNIFF_MIN_BYTES, 32)),
    );
    if (!magicBytesMatchClaimedMime(sniff.detected, claimedMime)) {
      return response(
        { ok: false, error: 'The synthetic recording format is invalid or unsupported.' },
        415,
      );
    }

    // The certification recorder is explicitly synthetic-only and ephemeral:
    // bytes go through the existing transcription orchestrator and are never
    // written to object storage or application logs. Cross-provider Whisper
    // fallback remains disabled at this boundary.
    const transcription = await transcribe({
      practiceId: session.user.practiceId,
      userId: session.user.id,
      visitId: null,
      purpose: 'tm_transcribe',
      audio,
      mimeType: sniff.detected!,
      allowCrossProviderFallback: false,
      deepgram: { options: { diarize: false, utterances: false } },
    });
    if (transcription.transcript.trim().length < 10) {
      return response(
        { ok: false, error: 'The synthetic recording was too short to test safely.' },
        422,
      );
    }
    const workspace = await runTemplateTwinSyntheticTest({
      noteTemplateId: id,
      actor: {
        userId: session.user.id,
        userEmail: session.user.email,
        practiceId: session.user.practiceId,
      },
      expectedMappingsSha256,
      encounterText: transcription.transcript,
      encounterMode: 'dictation',
    });
    return response({ ok: true, workspace }, 200);
  } catch (error) {
    if (error instanceof AuthError) {
      return response(
        {
          ok: false,
          error:
            error.code === 'FORBIDDEN'
              ? error.message
              : 'Sign in again before testing.',
        },
        error.code === 'FORBIDDEN' ? 403 : 401,
      );
    }
    if (error instanceof TemplateTwinSyntheticTestError) {
      const status =
        error.code === 'NOT_FOUND'
          ? 404
          : error.code === 'VALIDATION_FAILED' ||
              error.code === 'MAPPINGS_NOT_READY' ||
              error.code === 'SYNTHETIC_EVIDENCE_REJECTED' ||
              error.code === 'SOURCE_PROVENANCE_INVALID'
            ? 422
            : 409;
      return response({ ok: false, error: error.message }, status);
    }
    return response(
      { ok: false, error: 'The synthetic voice test did not pass transcription and document verification.' },
      503,
    );
  }
}
