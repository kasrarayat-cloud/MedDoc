// ============================================================================
// POST /api/visits/[id]/text (T-M5)
// ----------------------------------------------------------------------------
// Accepts a JSON body { text: string } and kicks off the text-mode
// pipeline (L3 text variant → L4 → L5 → L6; no transcription).
//
// One-shot: the route 409s if rawTextInput is already populated so a
// click-thrash can't re-submit and duplicate the pipeline run.
// ============================================================================

import { NextResponse } from 'next/server';
import { z } from 'zod';

import { auth } from '@/lib/nextauth';
import prisma from '@meddoc/db';
import { TranscribeVisitStatus } from '@prisma/client';
import {
  getTranscribeMdQueue,
  JOB_PROCESS_VISIT,
} from '@/lib/queue';

import { apiError, withApiHandler } from '@/lib/api-error';
import { RATE_LIMITS, rateLimitOr429 } from '@/lib/rate-limit';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

const MIN_CHARS = 30;
const MAX_CHARS = 5000;

const BodySchema = z.object({
  text: z.string().min(MIN_CHARS).max(MAX_CHARS),
});

export const POST = withApiHandler<{ id: string }>(
  'api:visits:text',
  async (req, { params }) => {
    const { id: visitId } = await params;

    const session = await auth();
    const userId = session?.user?.id;
    if (!userId) return apiError('unauthorized', 401);

    const blocked = rateLimitOr429(RATE_LIMITS.UPLOAD, userId);
    if (blocked) return blocked;

    let body: unknown;
    try {
      body = await req.json();
    } catch {
      return apiError('invalid JSON body', 400);
    }
    const parsed = BodySchema.safeParse(body);
    if (!parsed.success) {
      return apiError(`text must be ${MIN_CHARS}-${MAX_CHARS} characters`, 400);
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
    if (!visit || visit.userId !== userId) return apiError('not found', 404);
    if (visit.inputMode !== 'text_notes') {
      return apiError('this visit is not a text-to-SOAP visit', 400);
    }
    if (visit.rawTextInput?.trim()) {
      return apiError('text has already been submitted for this visit', 409);
    }
    if (visit.status !== TranscribeVisitStatus.QUEUED) {
      return apiError('visit is already processing or finalized', 409);
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
      console.error('[api:visits:text] queue enqueue failed:', err);
      return apiError(
        'text stored but worker enqueue failed; please refresh and try again',
        502
      );
    }

    return NextResponse.json({ visitId, status: 'QUEUED' }, { status: 202 });
  }
);
