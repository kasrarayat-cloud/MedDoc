// ============================================================================
// POST /api/visits/[id]/upload (T-M4)
// ----------------------------------------------------------------------------
// The browser sends the raw audio bytes as the request body, with
// Content-Type carrying the mime type (audio/mpeg, audio/wav, …) and
// X-TM-Filename carrying the original filename. Rejects early on
// Content-Length > 500 MB so the 500 MB never touches MinIO if it's
// over-limit.
//
// On success: the object lands in MinIO, the visit flips to QUEUED
// (already the default, but set explicitly to reset a previously-
// FAILED visit), and a BullMQ job is enqueued for the worker.
// ============================================================================

import { NextResponse } from 'next/server';
import { Readable } from 'node:stream';

import { auth } from '@/lib/nextauth';
import prisma from '@meddoc/db';
import { TranscribeVisitStatus } from '@prisma/client';
import { buildAudioObjectKey, putAudioStream } from '@/lib/minio';
import { enqueueProcessVisit } from '@/lib/queue';

import { apiError, withApiHandler } from '@/lib/api-error';
import { RATE_LIMITS, rateLimitOr429 } from '@/lib/rate-limit';
import { redactPhi } from '@meddoc/ai';

export const runtime = 'nodejs';
// Next's default body-size limit on route handlers is 1 MB — we need
// to opt out to accept up to 500 MB.
export const maxDuration = 300;
export const dynamic = 'force-dynamic';

const MAX_BYTES = 500 * 1024 * 1024; // 500 MB

const ALLOWED_MIME = new Set([
  'audio/mpeg',
  'audio/mp3',
  'audio/mp4',
  'audio/m4a',
  'audio/x-m4a',
  'audio/wav',
  'audio/x-wav',
  'audio/ogg',
  'audio/webm',
  'audio/flac',
]);

export const POST = withApiHandler<{ id: string }>(
  'api:visits:upload',
  async (req, { params }) => {
    const { id: visitId } = await params;

    const session = await auth();
    const userId = session?.user?.id;
    if (!userId) return apiError('unauthorized', 401);

    // UPLOAD bucket — each upload burns real Deepgram/Anthropic cost.
    const blocked = rateLimitOr429(RATE_LIMITS.UPLOAD, userId);
    if (blocked) return blocked;

    const visit = await prisma.transcribeVisit.findUnique({
      where: { id: visitId },
      select: { id: true, userId: true, inputMode: true, status: true },
    });
    if (!visit || visit.userId !== userId) return apiError('not found', 404);
    if (visit.inputMode !== 'audio_upload') {
      return apiError('this visit does not accept audio uploads', 400);
    }
    if (
      visit.status === TranscribeVisitStatus.SIGNED ||
      visit.status === TranscribeVisitStatus.READY ||
      visit.status === TranscribeVisitStatus.TRANSCRIBING ||
      visit.status === TranscribeVisitStatus.EXTRACTING ||
      visit.status === TranscribeVisitStatus.DRAFTING ||
      visit.status === TranscribeVisitStatus.CRITIQUING ||
      visit.status === TranscribeVisitStatus.POLISHING
    ) {
      return apiError('visit is already processing or finalized', 409);
    }

    // Early content-length check. A client that lies about size will hit
    // the putObject-level limit; we also pass sizeBytes to putObject
    // below so MinIO will reject an over-claim.
    const contentLengthHeader = req.headers.get('content-length');
    const contentLength = contentLengthHeader
      ? Number.parseInt(contentLengthHeader, 10)
      : NaN;
    if (!Number.isFinite(contentLength) || contentLength <= 0) {
      return apiError(
        'Content-length header missing or invalid.',
        400,
        { code: 'INVALID_REQUEST', retry: false }
      );
    }
    if (contentLength > MAX_BYTES) {
      return apiError(
        `File too large: ${contentLength} bytes exceeds the ${Math.round(MAX_BYTES / 1024 / 1024)} MB limit.`,
        413,
        { code: 'FILE_TOO_LARGE', retry: false }
      );
    }

    const mimeType = req.headers.get('content-type')?.trim() ?? '';
    if (!mimeType || !ALLOWED_MIME.has(mimeType.split(';')[0]!.trim())) {
      return apiError(
        `Unsupported file format: ${mimeType || '(missing)'}. Try MP3, M4A, WAV, or WebM.`,
        415,
        { code: 'UNSUPPORTED_FORMAT', retry: false }
      );
    }

    const filename =
      req.headers.get('x-tm-filename')?.trim() || 'audio-upload';

    const objectKey = buildAudioObjectKey(userId, visitId, filename);

    if (!req.body) return apiError('empty body', 400);

    // Adapt Web ReadableStream → Node Readable for the MinIO SDK.
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const nodeReadable = Readable.fromWeb(req.body as any);

    try {
      await putAudioStream(objectKey, nodeReadable, contentLength, mimeType);
    } catch (err) {
      // MinIO classification: 5xx → transient (retry worth it);
      // 4xx with an error message mentioning the bucket → permanent
      // (bucket missing or credentials bad). We err on the side of
      // retry:true except for obviously-permanent auth failures.
      const msg = err instanceof Error ? err.message.toLowerCase() : '';
      const permanent =
        /access denied|invalid accesskey|invalid signature|not found.*bucket/.test(
          msg
        );
      console.error(
        '[api:visits:upload] MinIO put failed:',
        redactPhi(err instanceof Error ? err.message : err)
      );
      return apiError(
        permanent
          ? 'Storage is misconfigured; please contact support.'
          : 'Storage write failed. Please try again in a moment.',
        502,
        {
          code: permanent ? 'STORAGE_PERMANENT' : 'STORAGE_TEMPORARY',
          retry: !permanent,
        }
      );
    }

    // Persist upload metadata + flip back to QUEUED (covers the "retry
    // after FAILED" path) before enqueuing the worker job.
    await prisma.transcribeVisit.update({
      where: { id: visitId },
      data: {
        audioKey: objectKey,
        audioMimeType: mimeType.split(';')[0]!.trim(),
        audioSizeBytes: contentLength,
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
      await enqueueProcessVisit(visitId, userId);
    } catch (err) {
      console.error(
        '[api:visits:upload] queue enqueue failed:',
        redactPhi(err instanceof Error ? err.message : err)
      );
      // The audio is in MinIO and the visit is QUEUED; the user can retry
      // upload or an ops tool can re-enqueue. Don't lose the upload.
      return apiError(
        'Upload stored, but the worker queue is unreachable. Please refresh and try again.',
        502,
        { code: 'QUEUE_TEMPORARY', retry: true }
      );
    }

    return NextResponse.json({ visitId, status: 'QUEUED' }, { status: 202 });
  }
);
