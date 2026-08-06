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

import { getSession } from '@/lib/auth';
import prisma from '@meddoc/db';
import { TranscribeVisitStatus } from '@prisma/client';
import { enqueueProcessVisit } from '@/lib/queue';

import { apiError, withApiHandler } from '@/lib/api-error';
import { visitByIdScope } from '@/lib/practice-scope';
import { RATE_LIMITS, rateLimitOr429 } from '@/lib/rate-limit';
import { redactPhi } from '@meddoc/ai';
import { logAudit } from '@/lib/audit';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

const MIN_CHARS = 30;
// Round 3 PR-J — A07-P1 server-side ceiling. 5000 chars covers a
// dense paragraph of typed shorthand; anything past that is either
// pasted PHI (probably accidental) or an attack surface.
const MAX_CHARS = 5000;

const BodySchema = z.object({
  text: z.string().min(MIN_CHARS).max(MAX_CHARS),
});

export const POST = withApiHandler<{ id: string }>(
  'api:visits:text',
  async (req, { params }) => {
    const { id: visitId } = await params;

    const session = await getSession();
    const userId = session?.user.id;
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
      // Round 3 PR-J — audit the rejection so a flood of oversize
      // attempts surfaces in the audit log even when no DB write
      // occurs. Length-only metadata; never log the rejected
      // content (could be partial PHI).
      const rawLen =
        typeof (body as { text?: unknown })?.text === 'string'
          ? ((body as { text: string }).text.length)
          : null;
      const tooLong = typeof rawLen === 'number' && rawLen > MAX_CHARS;
      if (tooLong) {
        void logAudit({
          action: 'TEXT_INPUT_REJECTED_TOO_LARGE',
          targetType: 'transcribe_visit',
          targetId: visitId,
          success: false,
          errorCode: 'TEXT_TOO_LONG',
          metadata: { length: rawLen, maxChars: MAX_CHARS },
        });
      }
      return apiError(`text must be ${MIN_CHARS}-${MAX_CHARS} characters`, 400);
    }

    const visit = await prisma.transcribeVisit.findFirst({
      where: visitByIdScope(visitId, session.user.practiceId),
      select: {
        id: true,
        userId: true,
        inputMode: true,
        status: true,
        rawTextInput: true,
        deletedAt: true,
        archivedAt: true,
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
      await enqueueProcessVisit(visitId, userId);
    } catch (err) {
      console.error(
        '[api:visits:text] queue enqueue failed:',
        redactPhi(err instanceof Error ? err.message : err)
      );
      return apiError(
        'text stored but worker enqueue failed; please refresh and try again',
        502
      );
    }

    return NextResponse.json({ visitId, status: 'QUEUED' }, { status: 202 });
  }
);
