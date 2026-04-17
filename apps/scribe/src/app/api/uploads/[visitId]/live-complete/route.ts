// ============================================================================
// POST /api/uploads/:visitId/live-complete
// ----------------------------------------------------------------------------
// Called by RecordClient after the browser finishes the direct-to-MinIO
// audio PUT. Finalizes the live visit:
//   1. Verify the audio object exists (defense against spoofed "complete")
//   2. Flush Redis segments → ScribeTranscript (upsert)
//   3. Update visit status: RECORDING → PROCESSING, audio metadata
//   4. Audit LIVE_TRANSCRIPT_FLUSHED + LIVE_AUDIO_UPLOADED
//   5. Enqueue the SHARED finalize_visit job — same worker handles
//      cleanup + SOAP for both live and batch (spec §10)
// ============================================================================

import { NextResponse, type NextRequest } from 'next/server';
import IORedis from 'ioredis';
import { z } from 'zod';
import prisma from '@meddoc/db';
import { tenantScope } from '@meddoc/auth';
import { getSession } from '@/lib/auth';
import { statObject } from '@/lib/minio';
import {
  getScribeQueue,
  JOB_FINALIZE_VISIT,
  type FinalizeVisitPayload,
} from '@/lib/queue';
import { persistLiveTranscript } from '@/server/live/flush';

// The WS sidecar + this route both talk to the same Redis instance.
// Route-local singleton so we don't open a new connection per request.
let redisSingleton: IORedis | null = null;
function getRedis(): IORedis {
  if (redisSingleton) return redisSingleton;
  const url = process.env.REDIS_URL?.trim() || 'redis://redis:6379';
  redisSingleton = new IORedis(url, { maxRetriesPerRequest: null });
  redisSingleton.on('error', (err: Error) => {
    console.error('[live-complete] redis error:', err.message);
  });
  return redisSingleton;
}

const CompleteBodySchema = z.object({
  durationSec: z.number().int().min(0).max(4 * 3600),
  sourceFileName: z.string().min(1).max(240),
});

export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ visitId: string }> }
) {
  const { visitId } = await params;
  const session = await getSession();
  if (!session) {
    return NextResponse.json({ error: 'Not authenticated.' }, { status: 401 });
  }

  let parsed: z.infer<typeof CompleteBodySchema>;
  try {
    const body = (await req.json()) as unknown;
    const result = CompleteBodySchema.safeParse(body);
    if (!result.success) {
      return NextResponse.json(
        { error: result.error.issues.map((i) => i.message).join(' ') },
        { status: 400 }
      );
    }
    parsed = result.data;
  } catch {
    return NextResponse.json({ error: 'Malformed body.' }, { status: 400 });
  }

  const visit = await prisma.scribeVisit.findFirst({
    where: { id: visitId, ...tenantScope(session), deletedAt: null },
    select: {
      id: true,
      userId: true,
      mode: true,
      status: true,
      audioObjectKey: true,
      practiceId: true,
    },
  });
  if (!visit) {
    return NextResponse.json({ error: 'Visit not found.' }, { status: 404 });
  }
  if (visit.userId !== session.user.id) {
    return NextResponse.json({ error: 'Visit not found.' }, { status: 404 });
  }
  if (visit.mode !== 'LIVE') {
    return NextResponse.json({ error: 'Visit is not live mode.' }, { status: 400 });
  }
  if (visit.status !== 'RECORDING') {
    return NextResponse.json(
      { error: `Visit is ${visit.status}; cannot complete.` },
      { status: 409 }
    );
  }
  if (!visit.audioObjectKey) {
    return NextResponse.json(
      { error: 'No presigned upload prepared — hit /record first.' },
      { status: 400 }
    );
  }

  const stat = await statObject(visit.audioObjectKey);
  if (!stat || stat.size === 0) {
    return NextResponse.json(
      { error: 'Audio object not found or empty in storage.' },
      { status: 400 }
    );
  }

  // Flush Redis → ScribeTranscript. The Deepgram model name is stamped
  // onto the transcript provider string so downstream analytics can
  // distinguish live from batch (and cleanup-vs-raw) sources.
  const deepgramModel = process.env.DEEPGRAM_MODEL?.trim() || 'nova-3-medical';
  const { segmentCount, rawFullTextLength } = await persistLiveTranscript(
    getRedis(),
    {
      visitId: visit.id,
      practiceId: visit.practiceId,
      deepgramModel,
    }
  );

  await prisma.scribeVisit.update({
    where: { id: visit.id },
    data: {
      status: 'PROCESSING',
      audioDurationSec: parsed.durationSec,
      sourceFileName: parsed.sourceFileName,
      endedAt: new Date(),
    },
  });

  await prisma.scribeAuditEvent.createMany({
    data: [
      {
        practiceId: visit.practiceId,
        visitId: visit.id,
        actorId: session.user.id,
        action: 'LIVE_TRANSCRIPT_FLUSHED',
        diff: { segmentCount, rawFullTextLength },
      },
      {
        practiceId: visit.practiceId,
        visitId: visit.id,
        actorId: session.user.id,
        action: 'LIVE_AUDIO_UPLOADED',
        diff: { sizeBytes: stat.size, durationSec: parsed.durationSec },
      },
    ],
  });

  await getScribeQueue().add(JOB_FINALIZE_VISIT, {
    visitId: visit.id,
  } satisfies FinalizeVisitPayload);

  return NextResponse.json({
    ok: true,
    segmentCount,
  });
}
