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

import { NextResponse, type NextRequest } from 'next/server';
import { Readable } from 'node:stream';

import { auth } from '@/lib/nextauth';
import prisma from '@meddoc/db';
import { TranscribeVisitStatus } from '@prisma/client';
import { buildAudioObjectKey, putAudioStream } from '@/lib/minio';
import {
  getTranscribeMdQueue,
  JOB_PROCESS_VISIT,
} from '@/lib/queue';

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

export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id: visitId } = await params;

  const session = await auth();
  const userId = session?.user?.id;
  if (!userId) {
    return NextResponse.json({ error: 'unauthorized' }, { status: 401 });
  }

  const visit = await prisma.transcribeVisit.findUnique({
    where: { id: visitId },
    select: { id: true, userId: true, inputMode: true, status: true },
  });
  if (!visit || visit.userId !== userId) {
    return NextResponse.json({ error: 'not found' }, { status: 404 });
  }
  if (visit.inputMode !== 'audio_upload') {
    return NextResponse.json(
      { error: 'this visit does not accept audio uploads' },
      { status: 400 }
    );
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
    return NextResponse.json(
      { error: 'visit is already processing or finalized' },
      { status: 409 }
    );
  }

  // Early content-length check. A client that lies about size will hit
  // the putObject-level limit; we also pass sizeBytes to putObject
  // below so MinIO will reject an over-claim.
  const contentLengthHeader = req.headers.get('content-length');
  const contentLength = contentLengthHeader
    ? Number.parseInt(contentLengthHeader, 10)
    : NaN;
  if (!Number.isFinite(contentLength) || contentLength <= 0) {
    return NextResponse.json(
      { error: 'content-length header missing or invalid' },
      { status: 400 }
    );
  }
  if (contentLength > MAX_BYTES) {
    return NextResponse.json(
      {
        error: `file too large: ${contentLength} bytes exceeds 500 MB limit`,
      },
      { status: 413 }
    );
  }

  const mimeType = req.headers.get('content-type')?.trim() ?? '';
  if (!mimeType || !ALLOWED_MIME.has(mimeType.split(';')[0]!.trim())) {
    return NextResponse.json(
      { error: `unsupported content-type: ${mimeType || '(missing)'}` },
      { status: 415 }
    );
  }

  const filename =
    req.headers.get('x-tm-filename')?.trim() || 'audio-upload';

  const objectKey = buildAudioObjectKey(userId, visitId, filename);

  if (!req.body) {
    return NextResponse.json({ error: 'empty body' }, { status: 400 });
  }

  // Adapt Web ReadableStream → Node Readable for the MinIO SDK.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const nodeReadable = Readable.fromWeb(req.body as any);

  try {
    await putAudioStream(objectKey, nodeReadable, contentLength, mimeType);
  } catch (err) {
    console.error('[upload] MinIO put failed:', err);
    return NextResponse.json(
      { error: 'storage write failed' },
      { status: 502 }
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
    await getTranscribeMdQueue().add(
      JOB_PROCESS_VISIT,
      { visitId, userId },
      { jobId: `visit-${visitId}-${Date.now()}` }
    );
  } catch (err) {
    console.error('[upload] queue enqueue failed:', err);
    // The audio is in MinIO and the visit is QUEUED; the user can retry
    // upload or an ops tool can re-enqueue. Don't lose the upload.
    return NextResponse.json(
      {
        error:
          'upload stored but worker enqueue failed; please refresh and try again',
      },
      { status: 502 }
    );
  }

  return NextResponse.json(
    { visitId, status: 'QUEUED' },
    { status: 202 }
  );
}
