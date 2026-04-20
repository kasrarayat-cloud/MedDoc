// ============================================================================
// POST /api/visits/[id]/dictation/upload (T-M5)
// ----------------------------------------------------------------------------
// Browser sends a raw audio body (MediaRecorder → webm/opus) with
// Content-Type audio/webm. Unlike the bulk audio-upload route, this is
// capped at 50 MB / ~10 minutes — dictation is a short summary, not a
// full visit recording.
//
// On success: object stored in the same MinIO bucket as uploaded audio
// (but under a distinct prefix), `dictationAudioKey` set on the visit,
// status flipped back to QUEUED, and a process_visit job enqueued for
// the worker.
// ============================================================================

import { NextResponse } from 'next/server';
import { Readable } from 'node:stream';

import { auth } from '@/lib/nextauth';
import prisma from '@meddoc/db';
import { TranscribeVisitStatus } from '@prisma/client';
import { putAudioStream } from '@/lib/minio';
import {
  getTranscribeMdQueue,
  JOB_PROCESS_VISIT,
} from '@/lib/queue';

import { apiError, withApiHandler } from '@/lib/api-error';
import { RATE_LIMITS, rateLimitOr429 } from '@/lib/rate-limit';

export const runtime = 'nodejs';
export const maxDuration = 120;
export const dynamic = 'force-dynamic';

/** Dictation is short-form — 50 MB is generous for 10 min of webm/opus
 *  at the default ~32 kbps MediaRecorder bitrate (~2.4 MB). The cap is
 *  really a safety valve against runaway uploads, not a typical size. */
const MAX_BYTES = 50 * 1024 * 1024;

const ALLOWED_MIME = new Set([
  'audio/webm',
  'audio/ogg',
  'audio/wav',
  'audio/x-wav',
  'audio/mp4',
  'audio/mpeg',
  'audio/mp3',
]);

export const POST = withApiHandler<{ id: string }>(
  'api:visits:dictation:upload',
  async (req, { params }) => {
    const { id: visitId } = await params;

    const session = await auth();
    const userId = session?.user?.id;
    if (!userId) return apiError('unauthorized', 401);

    const blocked = rateLimitOr429(RATE_LIMITS.UPLOAD, userId);
    if (blocked) return blocked;

    const visit = await prisma.transcribeVisit.findUnique({
      where: { id: visitId },
      select: {
        id: true,
        userId: true,
        inputMode: true,
        status: true,
        dictationAudioKey: true,
      },
    });
    if (!visit || visit.userId !== userId) return apiError('not found', 404);
    if (visit.inputMode !== 'voice_dictation') {
      return apiError('this visit is not a voice-dictation visit', 400);
    }
    if (visit.dictationAudioKey) {
      return apiError(
        'a dictation has already been recorded for this visit',
        409
      );
    }
    if (visit.status !== TranscribeVisitStatus.QUEUED) {
      return apiError('visit is already processing or finalized', 409);
    }

    const contentLengthHeader = req.headers.get('content-length');
    const contentLength = contentLengthHeader
      ? Number.parseInt(contentLengthHeader, 10)
      : NaN;
    if (!Number.isFinite(contentLength) || contentLength <= 0) {
      return apiError('content-length header missing or invalid', 400);
    }
    if (contentLength > MAX_BYTES) {
      return apiError(
        `dictation too large: ${contentLength} bytes exceeds ${MAX_BYTES / 1024 / 1024} MB limit`,
        413
      );
    }

    const mimeHeader = req.headers.get('content-type')?.trim() ?? '';
    const mimeType = mimeHeader.split(';')[0]!.trim();
    if (!ALLOWED_MIME.has(mimeType)) {
      return apiError(
        `unsupported content-type: ${mimeHeader || '(missing)'}`,
        415
      );
    }

    if (!req.body) return apiError('empty body', 400);

    // Object-key prefix distinguishes dictation from the bulk audio the
    // other route uses — simplifies bucket policy + debugging later.
    const objectKey = `${userId}/${visitId}/dictation-${Date.now()}.webm`;

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const nodeReadable = Readable.fromWeb(req.body as any);

    try {
      await putAudioStream(objectKey, nodeReadable, contentLength, mimeType);
    } catch (err) {
      console.error('[api:visits:dictation:upload] MinIO put failed:', err);
      return apiError('storage write failed', 502);
    }

    await prisma.transcribeVisit.update({
      where: { id: visitId },
      data: {
        dictationAudioKey: objectKey,
        audioMimeType: mimeType,
        audioUploadedAt: new Date(),
        status: TranscribeVisitStatus.QUEUED,
        needsReview: false,
        reviewReason: null,
        processingStartedAt: null,
        processingFinishedAt: null,
        processingCostCents: null,
      },
    });

    try {
      await getTranscribeMdQueue().add(
        JOB_PROCESS_VISIT,
        { visitId, userId },
        { jobId: `visit-${visitId}-${Date.now()}` }
      );
    } catch (err) {
      console.error('[api:visits:dictation:upload] queue enqueue failed:', err);
      return apiError(
        'dictation stored but worker enqueue failed; please refresh and try again',
        502
      );
    }

    return NextResponse.json({ visitId, status: 'QUEUED' }, { status: 202 });
  }
);
