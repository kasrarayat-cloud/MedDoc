// ============================================================================
// GET /api/visits/[id]/dictation/audio (T-M5)
// ----------------------------------------------------------------------------
// Streams the dictation audio back to the browser so the Transcript tab
// can render a small <audio> player. Authed and scoped to the visit's
// owner — we never hand out a presigned URL to avoid exposing raw MinIO
// access; the bytes go through the Node runtime with session validation.
// ============================================================================

import { NextResponse } from 'next/server';

import { auth } from '@/lib/nextauth';
import prisma from '@meddoc/db';
import { downloadAudio } from '@/lib/minio';

import { apiError, withApiHandler } from '@/lib/api-error';
import { redactPhi } from '@meddoc/ai';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export const GET = withApiHandler<{ id: string }>(
  'api:visits:dictation:audio',
  async (_req, { params }) => {
    const { id: visitId } = await params;

    const session = await auth();
    const userId = session?.user?.id;
    if (!userId) return apiError('unauthorized', 401);

    const visit = await prisma.transcribeVisit.findUnique({
      where: { id: visitId },
      select: {
        userId: true,
        dictationAudioKey: true,
        audioMimeType: true,
      },
    });
    if (!visit || visit.userId !== userId) return apiError('not found', 404);
    if (!visit.dictationAudioKey) {
      return apiError('no dictation recorded', 404);
    }

    let buf: Buffer;
    try {
      buf = await downloadAudio(visit.dictationAudioKey);
    } catch (err) {
      console.error(
        '[api:visits:dictation:audio] download failed:',
        redactPhi(err instanceof Error ? err.message : err)
      );
      return apiError('storage read failed', 502);
    }

    // For 10-min webm clips we return the whole buffer — cheaper to
    // render in one shot than to stream for the browser's audio element.
    // If dictations ever grow beyond a few MB a streaming variant is the
    // obvious follow-up.
    return new NextResponse(buf as unknown as BodyInit, {
      status: 200,
      headers: {
        'Content-Type': visit.audioMimeType ?? 'audio/webm',
        'Content-Length': String(buf.byteLength),
        // Disable caching — the bytes are PHI and the session gate is the
        // only thing keeping them private.
        'Cache-Control': 'no-store, private',
      },
    });
  }
);
