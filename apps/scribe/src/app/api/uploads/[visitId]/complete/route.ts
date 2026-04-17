// ============================================================================
// POST /api/uploads/:visitId/complete
// ----------------------------------------------------------------------------
// Called by the browser once the direct-to-MinIO PUT succeeds. We verify
// the caller's session + tenant ownership of the visit, confirm the
// audio object actually exists in MinIO (defense against spoofed
// "upload complete" calls), then enqueue the transcribe_batch job.
// ============================================================================

import { NextResponse, type NextRequest } from 'next/server';
import prisma from '@meddoc/db';
import { tenantScope } from '@meddoc/auth';
import { getSession } from '@/lib/auth';
import { statObject } from '@/lib/minio';
import { getScribeQueue, JOB_TRANSCRIBE_BATCH, type TranscribeBatchPayload } from '@/lib/queue';

export async function POST(
  _req: NextRequest,
  { params }: { params: Promise<{ visitId: string }> }
) {
  const { visitId } = await params;
  const session = await getSession();
  if (!session) {
    return NextResponse.json({ error: 'Not authenticated.' }, { status: 401 });
  }

  const visit = await prisma.scribeVisit.findFirst({
    where: { id: visitId, ...tenantScope(session), deletedAt: null },
    select: {
      id: true,
      status: true,
      mode: true,
      audioObjectKey: true,
      sourceFileName: true,
      practiceId: true,
    },
  });
  if (!visit) return NextResponse.json({ error: 'Visit not found.' }, { status: 404 });
  if (visit.mode !== 'BATCH') {
    return NextResponse.json({ error: 'Visit is not batch mode.' }, { status: 400 });
  }
  if (!visit.audioObjectKey || !visit.sourceFileName) {
    return NextResponse.json(
      { error: 'No upload was prepared — hit /upload first.' },
      { status: 400 }
    );
  }
  if (visit.status === 'PROCESSING' || visit.status === 'READY_FOR_REVIEW' || visit.status === 'SIGNED') {
    return NextResponse.json({ error: 'Visit already processed.' }, { status: 409 });
  }

  // Verify the object actually exists in MinIO before enqueueing. Avoids
  // a "stuck PROCESSING" state if the browser reported success but the
  // PUT silently failed.
  const stat = await statObject(visit.audioObjectKey);
  if (!stat || stat.size === 0) {
    return NextResponse.json({ error: 'Audio object not found or empty in storage.' }, { status: 400 });
  }

  await getScribeQueue().add(JOB_TRANSCRIBE_BATCH, {
    visitId: visit.id,
    audioObjectKey: visit.audioObjectKey,
    sourceFileName: visit.sourceFileName,
  } satisfies TranscribeBatchPayload);

  await prisma.scribeAuditEvent.create({
    data: {
      practiceId: visit.practiceId,
      visitId: visit.id,
      actorId: session.user.id,
      action: 'UPLOADED_AUDIO',
      diff: { sizeBytes: stat.size, fileName: visit.sourceFileName },
    },
  });

  return NextResponse.json({ ok: true });
}
