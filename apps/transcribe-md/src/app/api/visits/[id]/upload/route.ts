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

import { getSession } from '@/lib/auth';
import prisma from '@meddoc/db';
import { TranscribeVisitStatus } from '@prisma/client';
import {
  buildAudioObjectKey,
  deleteAudioObject,
  putAudioStream,
} from '@/lib/minio';
import { enqueueProcessVisit } from '@/lib/queue';

import { apiError, withApiHandler } from '@/lib/api-error';
import { visitByIdScope } from '@/lib/practice-scope';
import { RATE_LIMITS, rateLimitOr429 } from '@/lib/rate-limit';
import { redactPhi } from '@meddoc/ai';
import { logAudit } from '@/lib/audit';
import {
  sniffAudioMagicBytes,
  magicBytesMatchClaimedMime,
  SNIFF_MIN_BYTES,
} from '@/lib/audio-sniff';

export const runtime = 'nodejs';
// Next's default body-size limit on route handlers is 1 MB — we need
// to opt out to accept up to 100 MB.
export const maxDuration = 300;
export const dynamic = 'force-dynamic';

// Round 3 PR-J — A07-P0 server-side cap. Lowered from the historical
// 500 MB to 100 MB: a 100 MB ceiling covers a 90-minute high-quality
// recording with comfortable headroom and removes the high-end abuse
// surface (bandwidth-flooding the worker, OOM via runaway streams).
const MAX_BYTES = 100 * 1024 * 1024;

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

    const session = await getSession();
    const userId = session?.user.id;
    if (!userId) return apiError('unauthorized', 401);

    // UPLOAD bucket — each upload burns real Deepgram/Anthropic cost.
    const blocked = rateLimitOr429(RATE_LIMITS.UPLOAD, userId);
    if (blocked) return blocked;

    const visit = await prisma.transcribeVisit.findFirst({
      where: visitByIdScope(visitId, session.user.practiceId),
      select: {
        id: true,
        userId: true,
        inputMode: true,
        status: true,
        deletedAt: true,
        archivedAt: true,
        // T-M18.2 A9: pulled so we can sweep a stale MinIO object
        // left by a previous failed-then-reuploaded attempt.
        audioKey: true,
      },
    });
    // T6 §4.1c — the author conjunct is GONE; practice membership is the gate.
    // The read above is practice-scoped (T5), so reaching this line means the
    // visit is in the caller's practice. SIGNING is the only role-gated action
    // (SPEC §1.2); tech-creates/doctor-signs requires every member to be able to
    // prepare work.
    if (!visit) return apiError('not found', 404);
    if (visit.deletedAt !== null || visit.archivedAt !== null) {
      return apiError(
        'Visit is no longer active. Restore it first.',
        400,
        { code: 'VISIT_NOT_ACTIVE' }
      );
    }
    if (visit.inputMode !== 'audio_upload') {
      return apiError('this visit does not accept audio uploads', 400);
    }
    // T-M18.1 A4: switched from a deny-list of 7 in-flight statuses to
    // an allowlist of 2. The deny-list was missing AUTOMATING — a
    // re-upload during the L7 fan-out would have flipped the visit
    // back to QUEUED and enqueued a duplicate pipeline run, wasting
    // Deepgram + Anthropic tokens. Allowlist pattern matches
    // /dictation/upload and /text routes and closes the class.
    if (
      visit.status !== TranscribeVisitStatus.QUEUED &&
      visit.status !== TranscribeVisitStatus.FAILED
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
      // Round 3 PR-J — audit the rejection so a flood of oversize
      // attempts shows up in the audit log even when the bytes never
      // reach MinIO.
      void logAudit({
        action: 'AUDIO_REJECTED_FILE_TOO_LARGE',
        targetType: 'transcribe_visit',
        targetId: visitId,
        success: false,
        errorCode: 'FILE_TOO_LARGE',
        metadata: {
          claimedSizeBytes: contentLength,
          maxBytes: MAX_BYTES,
        },
      });
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

    // ── Round 3 PR-J — A07-P0 magic-byte sniff ──
    // The Content-Type header is client-supplied and trivially spoofable;
    // the MIME allowlist above is courtesy, not a boundary. Buffer the
    // entire request body, sniff the leading bytes, and reject if the
    // claimed MIME doesn't match the binary header. We buffer in
    // memory because a 100 MB cap fits in the worker's mem_limit; if
    // that ceiling rises in the future this becomes a streaming PassThrough
    // pattern (peek 16 bytes, then forward to MinIO).
    const bodyBuffer = Buffer.from(await req.arrayBuffer());
    if (bodyBuffer.byteLength === 0) return apiError('empty body', 400);
    if (bodyBuffer.byteLength > MAX_BYTES) {
      // Defensive — content-length lied about size. Audit + reject.
      void logAudit({
        action: 'AUDIO_REJECTED_FILE_TOO_LARGE',
        targetType: 'transcribe_visit',
        targetId: visitId,
        success: false,
        errorCode: 'FILE_TOO_LARGE_BODY',
        metadata: {
          claimedSizeBytes: contentLength,
          actualSizeBytes: bodyBuffer.byteLength,
          maxBytes: MAX_BYTES,
        },
      });
      return apiError(
        `File too large: actual body size exceeds the ${Math.round(MAX_BYTES / 1024 / 1024)} MB limit.`,
        413,
        { code: 'FILE_TOO_LARGE', retry: false }
      );
    }

    const claimedMime = mimeType.split(';')[0]!.trim();
    const sniff = sniffAudioMagicBytes(
      bodyBuffer.subarray(0, Math.max(SNIFF_MIN_BYTES, 32))
    );
    if (!magicBytesMatchClaimedMime(sniff.detected, claimedMime)) {
      void logAudit({
        action: 'AUDIO_REJECTED_INVALID_MAGIC_BYTES',
        targetType: 'transcribe_visit',
        targetId: visitId,
        success: false,
        errorCode: 'INVALID_MAGIC_BYTES',
        metadata: {
          claimedMime,
          detectedMime: sniff.detected,
          detectedFormat: sniff.format,
          sizeBytes: bodyBuffer.byteLength,
        },
      });
      return apiError(
        sniff.detected
          ? `File contents (${sniff.format}) don't match the declared format (${claimedMime}). Re-upload with the correct file or extension.`
          : `Unrecognised audio format. Try MP3, M4A, WAV, OGG, WebM, or FLAC.`,
        415,
        { code: 'INVALID_MAGIC_BYTES', retry: false }
      );
    }

    // Adapt Buffer → Node Readable for the MinIO SDK. The buffer
    // is in-memory (capped at 100 MB by the gate above).
    const nodeReadable = Readable.from(bodyBuffer);

    try {
      await putAudioStream(
        objectKey,
        nodeReadable,
        bodyBuffer.byteLength,
        mimeType
      );
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
        // Round 3 PR-J — record the actual byte count, not the
        // client's content-length header. They match for honest
        // clients; for a lying client we already rejected above.
        audioSizeBytes: bodyBuffer.byteLength,
        audioUploadedAt: new Date(),
        status: TranscribeVisitStatus.QUEUED,
        needsReview: false,
        reviewReason: null,
        processingStartedAt: null,
        processingFinishedAt: null,
        processingCostCents: null,
      },
    });

    // T-M18.2 A9: if this was a re-upload (FAILED → new upload), the
    // old audioKey is now orphaned in MinIO. Best-effort delete so
    // the T-M12 orphan sweep doesn't have to catch it later. Fire
    // AFTER the DB update succeeds — if the delete races ahead and
    // the DB update fails, the user loses BOTH the old and new
    // audio.
    if (visit.audioKey && visit.audioKey !== objectKey) {
      void deleteAudioObject(visit.audioKey).catch((err: unknown) => {
        console.warn(
          `[api:visits:upload] orphan cleanup failed key=${visit.audioKey}:`,
          redactPhi(err instanceof Error ? err.message : err)
        );
      });
    }

    void logAudit({
      action: 'AUDIO_UPLOADED',
      targetType: 'transcribe_visit',
      targetId: visitId,
      metadata: {
        sizeBytes: bodyBuffer.byteLength,
        mimeType: mimeType.split(';')[0]!.trim(),
        // Round 3 PR-J — surface the sniffed format alongside the
        // claimed MIME for forensics. They should match for accepted
        // uploads (we reject mismatches above).
        detectedFormat: sniff.format,
        inputMode: 'audio_upload',
        reupload: visit.audioKey !== null && visit.audioKey !== objectKey,
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
