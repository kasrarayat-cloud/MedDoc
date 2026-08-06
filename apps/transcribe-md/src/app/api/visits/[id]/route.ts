// ============================================================================
// GET   /api/visits/[id]  — full visit shape (smoke F-B-003 fix)
// PATCH /api/visits/[id]  (T-M17.3 Phase 3 Commit 5)
// ----------------------------------------------------------------------------
// GET returns the same prisma row that /visits/[id]/page.tsx loads
// server-side, so API consumers (Playwright harnesses, future
// integrations) can read a visit without screen-scraping. Slim
// status-only data still lives at /api/visits/[id]/status; this
// route is the full object.
//
// PATCH edits a draft QUEUED visit — the small window between "I
// clicked a capture-mode tile by mistake" and "the pipeline is
// actually running". Once any input lands (audioKey,
// dictationAudioKey, or rawTextInput), the visit becomes immutable
// via this route and the doctor's corrective action is
// Delete-and-retry instead.
//
// Editable fields: patientId, specialty, chiefComplaint, inputMode.
// All optional in the body (undefined = leave unchanged, null clears
// only chiefComplaint — the other three are NOT NULL on the model).
//
// Error shape matches the T-M16.4 classification (code + retry):
//   VISIT_NOT_DRAFT   — status != QUEUED, or any input field has
//                       content. Retry after clearing inputs, or use
//                       Delete instead.
//   VISIT_DELETED     — deletedAt IS NOT NULL (not technically
//                       "deleted" yet but in the 15-day trash window).
//   VISIT_ARCHIVED    — archivedAt IS NOT NULL (impossible today —
//                       only SIGNED visits archive and SIGNED ≠
//                       QUEUED — but the gate is defensive against
//                       future archive-expansion).
//   INVALID_PATIENT   — patientId doesn't exist, belongs to a
//                       different practice, or is soft-deleted.
// ============================================================================

import { z } from 'zod';
import { NextResponse } from 'next/server';

import prisma from '@meddoc/db';
import { TranscribeVisitStatus } from '@prisma/client';
import { SPECIALTY_IDS } from '@meddoc/shared/specialties';

import { apiError, withApiHandler } from '@/lib/api-error';
import { visitByIdScope } from '@/lib/practice-scope';
import { getSession } from '@/lib/auth';
import { RATE_LIMITS, rateLimitOr429 } from '@/lib/rate-limit';
import { log } from '@/lib/log';
import { logAudit } from '@/lib/audit';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

const INPUT_MODES = ['audio_upload', 'voice_dictation', 'text_notes'] as const;

const BodySchema = z.object({
  patientId: z.string().trim().min(1).optional(),
  specialty: z.enum(SPECIALTY_IDS, { message: 'Pick a specialty' }).optional(),
  chiefComplaint: z
    .union([z.string().trim().max(500), z.null()])
    .optional()
    .transform((v) => {
      if (v === undefined) return undefined;
      if (v === null) return null;
      return v.length === 0 ? null : v;
    }),
  inputMode: z.enum(INPUT_MODES).optional(),
});

export const GET = withApiHandler<{ id: string }>(
  'api:visits:get',
  async (_req, { params }) => {
    const { id: visitId } = await params;

    const session = await getSession();
    const userId = session?.user.id;
    if (!userId) return apiError('unauthorized', 401);

    const visit = await prisma.transcribeVisit.findFirst({
      where: visitByIdScope(visitId, session.user.practiceId),
      select: {
        id: true,
        userId: true,
        patientId: true,
        patientName: true,
        specialty: true,
        chiefComplaint: true,
        inputMode: true,
        status: true,
        signedAt: true,
        deletedAt: true,
        archivedAt: true,
        patient: {
          select: {
            id: true,
            name: true,
            dateOfBirth: true,
            externalId: true,
            mrn: true,
            insurance: true,
            problemList: true,
          },
        },
        createdAt: true,
        updatedAt: true,
        audioKey: true,
        audioMimeType: true,
        audioSizeBytes: true,
        audioDurationSec: true,
        audioUploadedAt: true,
        dictationAudioKey: true,
        dictationDurationSec: true,
        rawTextInput: true,
        transcriptRaw: true,
        transcriptText: true,
        speakerMap: true,
        entities: true,
        soapDraft: true,
        critique: true,
        soapFinal: true,
        signedSoap: true,
        needsReview: true,
        reviewReason: true,
        failureCategory: true,
        manualRetryCount: true,
        processingStartedAt: true,
        processingFinishedAt: true,
        processingCostCents: true,
        icdCodes: true,
        cptCodes: true,
        rxDrafts: true,
        referrals: true,
        patientSummary: true,
        confidenceScores: true,
      },
    });
    // 404 on both "not found" AND "not yours" prevents ID enumeration.
    if (!visit || visit.userId !== userId) return apiError('not found', 404);

    // Round 3 PR-C — §164.312(b) PHI-read audit (A05-P0-004). Fire-and-
    // forget; logAudit never throws and pulls userId/IP/UA from session
    // + headers internally. metadata uses field NAMES only, never PHI.
    void logAudit({
      action: 'VIEWED_VISIT',
      targetId: visit.id,
      targetType: 'TranscribeVisit',
      metadata: { source: 'api:GET /api/visits/[id]' },
    });

    return NextResponse.json({ visit }, { status: 200 });
  }
);

export const PATCH = withApiHandler<{ id: string }>(
  'api:visits:edit',
  async (req, { params }) => {
    const { id: visitId } = await params;

    const session = await getSession();
    const userId = session?.user.id;
    if (!userId) return apiError('unauthorized', 401);

    const blocked = rateLimitOr429(RATE_LIMITS.VISIT_OPS, userId);
    if (blocked) return blocked;

    let body: unknown;
    try {
      body = await req.json();
    } catch {
      return apiError('invalid JSON body', 400);
    }
    const parsed = BodySchema.safeParse(body);
    if (!parsed.success) {
      const first = parsed.error.issues[0];
      const field = first?.path.join('.') || '_form';
      return NextResponse.json(
        { error: first?.message || 'invalid payload', field },
        { status: 400 }
      );
    }

    // Need the caller's practiceId to gate patient-FK changes. Cheap.
    const user = await prisma.user.findUnique({
      where: { id: userId },
      select: { practiceId: true },
    });
    if (!user) return apiError('user not found', 404);

    const visit = await prisma.transcribeVisit.findFirst({
      where: visitByIdScope(visitId, session.user.practiceId),
      select: {
        id: true,
        userId: true,
        status: true,
        audioKey: true,
        dictationAudioKey: true,
        rawTextInput: true,
        deletedAt: true,
        archivedAt: true,
        patientId: true,
      },
    });
    if (!visit || visit.userId !== userId) return apiError('not found', 404);

    if (visit.deletedAt !== null) {
      return NextResponse.json(
        {
          error: 'Visit is in trash. Restore it before editing.',
          code: 'VISIT_DELETED',
        },
        { status: 400 }
      );
    }
    // archivedAt is impossible here (only SIGNED visits can be archived,
    // and SIGNED ≠ QUEUED), but check defensively for future changes.
    if (visit.archivedAt !== null) {
      return NextResponse.json(
        {
          error: 'Archived visits cannot be edited.',
          code: 'VISIT_ARCHIVED',
        },
        { status: 400 }
      );
    }

    const noInput =
      visit.audioKey === null &&
      visit.dictationAudioKey === null &&
      (visit.rawTextInput === null || visit.rawTextInput.length === 0);

    if (visit.status !== TranscribeVisitStatus.QUEUED || !noInput) {
      return NextResponse.json(
        {
          error:
            'Only draft visits (queued with no input uploaded) can be edited. Delete it instead.',
          code: 'VISIT_NOT_DRAFT',
        },
        { status: 400 }
      );
    }

    // If patientId is being changed, validate against caller's practice.
    if (
      parsed.data.patientId !== undefined &&
      parsed.data.patientId !== visit.patientId
    ) {
      const newPatient = await prisma.transcribeMdPatient.findUnique({
        where: { id: parsed.data.patientId },
        select: { id: true, name: true, practiceId: true, deletedAt: true },
      });
      if (
        !newPatient ||
        newPatient.practiceId !== user.practiceId ||
        newPatient.deletedAt !== null
      ) {
        return NextResponse.json(
          {
            error: 'Selected patient is not available.',
            code: 'INVALID_PATIENT',
          },
          { status: 400 }
        );
      }
    }

    const data: {
      patientId?: string;
      patientName?: string;
      specialty?: string;
      chiefComplaint?: string | null;
      inputMode?: (typeof INPUT_MODES)[number];
    } = {};
    if (
      parsed.data.patientId !== undefined &&
      parsed.data.patientId !== visit.patientId
    ) {
      data.patientId = parsed.data.patientId;
      // Denormalised legacy column; keep it in sync with the FK so
      // anywhere that still reads `visit.patientName` agrees with
      // the linked patient's name.
      const newPatient = await prisma.transcribeMdPatient.findUnique({
        where: { id: parsed.data.patientId },
        select: { name: true },
      });
      if (newPatient) data.patientName = newPatient.name;
    }
    if (parsed.data.specialty !== undefined) {
      data.specialty = parsed.data.specialty;
    }
    if (parsed.data.chiefComplaint !== undefined) {
      data.chiefComplaint = parsed.data.chiefComplaint;
    }
    if (parsed.data.inputMode !== undefined) {
      data.inputMode = parsed.data.inputMode;
    }

    if (Object.keys(data).length === 0) {
      return NextResponse.json(
        { error: 'No fields to update.', field: '_form' },
        { status: 400 }
      );
    }

    const updated = await prisma.transcribeVisit.update({
      where: { id: visit.id },
      data,
      select: {
        id: true,
        patientId: true,
        specialty: true,
        chiefComplaint: true,
        inputMode: true,
        updatedAt: true,
      },
    });

    log.info('api:visits:edit', 'draft edited', {
      userId,
      visitId,
      changedKeys: Object.keys(data),
    });

    return NextResponse.json({ visit: updated });
  }
);
