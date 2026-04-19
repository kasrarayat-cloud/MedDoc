// ============================================================================
// GET /api/visits/[id]/dictation/audio (T-M5)
// ----------------------------------------------------------------------------
// Streams the dictation audio back to the browser so the Transcript tab
// can render a small <audio> player. Authed and scoped to the visit's
// owner — we never hand out a presigned URL to avoid exposing raw MinIO
// access; the bytes go through the Node runtime with session validation.
// ============================================================================

import { NextResponse, type NextRequest } from 'next/server';

import { auth } from '@/lib/nextauth';
import prisma from '@meddoc/db';
import { downloadAudio } from '@/lib/minio';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id: visitId } = await params;

  const session = await auth();
  const userId = session?.user?.id;
  if (!userId) {
    return new NextResponse('unauthorized', { status: 401 });
  }

  const visit = await prisma.transcribeVisit.findUnique({
    where: { id: visitId },
    select: {
      userId: true,
      dictationAudioKey: true,
      audioMimeType: true,
    },
  });
  if (!visit || visit.userId !== userId) {
    return new NextResponse('not found', { status: 404 });
  }
  if (!visit.dictationAudioKey) {
    return new NextResponse('no dictation recorded', { status: 404 });
  }

  let buf: Buffer;
  try {
    buf = await downloadAudio(visit.dictationAudioKey);
  } catch (err) {
    console.error('[dictation-audio] download failed:', err);
    return new NextResponse('storage read failed', { status: 502 });
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
