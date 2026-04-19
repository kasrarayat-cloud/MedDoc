// ============================================================================
// POST /api/visits/[id]/text (T-M5)
// ----------------------------------------------------------------------------
// Accepts a JSON body { text: string } and kicks off the text-mode
// pipeline (L3 text variant → L4 → L5 → L6; no transcription).
//
// One-shot: the route 409s if rawTextInput is already populated so a
// click-thrash can't re-submit and duplicate the pipeline run.
// ============================================================================

import { NextResponse, type NextRequest } from 'next/server';
import { z } from 'zod';

import { auth } from '@/lib/nextauth';
import prisma from '@meddoc/db';
import { TranscribeVisitStatus } from '@prisma/client';
import {
  getTranscribeMdQueue,
  JOB_PROCESS_VISIT,
} from '@/lib/queue';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

const MIN_CHARS = 30;
const MAX_CHARS = 5000;

const BodySchema = z.object({
  text: z.string().min(MIN_CHARS).max(MAX_CHARS),
});

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

  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: 'invalid JSON body' }, { status: 400 });
  }
  const parsed = BodySchema.safeParse(body);
  if (!parsed.success) {
    return NextResponse.json(
      {
        error: `text must be ${MIN_CHARS}-${MAX_CHARS} characters`,
      },
      { status: 400 }
    );
  }

  const visit = await prisma.transcribeVisit.findUnique({
    where: { id: visitId },
    select: {
      id: true,
      userId: true,
      inputMode: true,
      status: true,
      rawTextInput: true,
    },
  });
  if (!visit || visit.userId !== userId) {
    return NextResponse.json({ error: 'not found' }, { status: 404 });
  }
  if (visit.inputMode !== 'text_notes') {
    return NextResponse.json(
      { error: 'this visit is not a text-to-SOAP visit' },
      { status: 400 }
    );
  }
  if (visit.rawTextInput?.trim()) {
    return NextResponse.json(
      { error: 'text has already been submitted for this visit' },
      { status: 409 }
    );
  }
  if (visit.status !== TranscribeVisitStatus.QUEUED) {
    return NextResponse.json(
      { error: 'visit is already processing or finalized' },
      { status: 409 }
    );
  }

  await prisma.transcribeVisit.update({
    where: { id: visitId },
    data: {
      rawTextInput: parsed.data.text,
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
    console.error('[text-submit] queue enqueue failed:', err);
    return NextResponse.json(
      {
        error:
          'text stored but worker enqueue failed; please refresh and try again',
      },
      { status: 502 }
    );
  }

  return NextResponse.json(
    { visitId, status: 'QUEUED' },
    { status: 202 }
  );
}
