// ============================================================================
// /api/patients/[id] — read, update, soft-delete (T-M17.2 Phase 2 Commit 4)
// ----------------------------------------------------------------------------
// All three handlers 404 on mismatched practiceId (anti-enumeration,
// matches the pattern used by /api/visits/[id]/retry).
//
// Soft-delete is idempotent: DELETE on an already-deleted patient
// returns 200 without touching the row again, so repeated calls from
// a flaky client are harmless. Hard delete is intentionally not
// exposed — the DB FK from transcribe_visits uses ON DELETE RESTRICT,
// so a hard drop while visits exist would fail anyway.
// ============================================================================

import { z } from 'zod';
import { NextResponse } from 'next/server';

import prisma from '@meddoc/db';
import { visitScope } from '@/lib/practice-scope';

import { apiError, withApiHandler } from '@/lib/api-error';
import { getSession } from '@/lib/auth';
import { ProblemListSchema } from '@/lib/problem-list';
import { RATE_LIMITS, rateLimitOr429 } from '@/lib/rate-limit';
import { logAudit } from '@/lib/audit';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

async function loadPatientForSession(
  id: string,
  practiceId: string,
  { includeDeleted = false }: { includeDeleted?: boolean } = {}
) {
  const patient = await prisma.transcribeMdPatient.findUnique({
    where: { id },
    select: {
      id: true,
      practiceId: true,
      name: true,
      dateOfBirth: true,
      externalId: true,
      mrn: true,
      insurance: true,
      problemList: true,
      deletedAt: true,
      createdAt: true,
      updatedAt: true,
    },
  });
  if (!patient || patient.practiceId !== practiceId) return null;
  if (!includeDeleted && patient.deletedAt !== null) return null;
  return patient;
}

export const GET = withApiHandler<{ id: string }>(
  'api:patients:get',
  async (_req, { params }) => {
    const session = await getSession();
    if (!session) return apiError('unauthorized', 401);

    const blocked = rateLimitOr429(RATE_LIMITS.PATIENT_READ, session.user.id);
    if (blocked) return blocked;

    const { id } = await params;
    const patient = await loadPatientForSession(id, session.user.practiceId);
    if (!patient) return apiError('not found', 404);

    // Attach visit count + last-visit-at so the detail page doesn't
    // need a second round-trip.
    const aggregate = await prisma.transcribeVisit.aggregate({
      where: {
        patientId: patient.id,
        ...visitScope(session.user.practiceId),
        deletedAt: null,
        archivedAt: null,
      },
      _count: { _all: true },
      _max: { createdAt: true },
    });

    // Round 3 PR-C — §164.312(b) PHI-read audit (A05-P0-004).
    void logAudit({
      action: 'VIEWED_PATIENT_FILE',
      targetId: patient.id,
      targetType: 'TranscribeMdPatient',
      metadata: { source: 'api:GET /api/patients/[id]' },
    });

    return NextResponse.json({
      patient: {
        id: patient.id,
        name: patient.name,
        dateOfBirth: patient.dateOfBirth,
        externalId: patient.externalId,
        mrn: patient.mrn,
        insurance: patient.insurance,
        problemList: patient.problemList,
        createdAt: patient.createdAt,
        updatedAt: patient.updatedAt,
        visitCount: aggregate._count._all,
        lastVisitAt: aggregate._max.createdAt,
      },
    });
  }
);

const UpdateBodySchema = z.object({
  name: z.string().trim().min(1).max(200).optional(),
  /** Pass null to clear a previously-set DOB (e.g. typo correction);
   *  pass a string to set/update it; omit to leave unchanged. */
  dateOfBirth: z
    .union([
      z
        .string()
        .min(1)
        .refine((s) => !Number.isNaN(Date.parse(s)), {
          message: 'Invalid date',
        }),
      z.null(),
    ])
    .optional(),
  externalId: z
    .union([z.string().trim().max(100), z.null()])
    .optional()
    .transform((v) => {
      if (v === undefined) return undefined;
      if (v === null) return null;
      return v.length === 0 ? null : v;
    }),
  mrn: z
    .union([z.string().trim().max(50), z.null()])
    .optional()
    .transform((v) => {
      if (v === undefined) return undefined;
      if (v === null) return null;
      return v.length === 0 ? null : v;
    }),
  insurance: z
    .union([z.string().trim().max(200), z.null()])
    .optional()
    .transform((v) => {
      if (v === undefined) return undefined;
      if (v === null) return null;
      return v.length === 0 ? null : v;
    }),
  /** Full-array replace. Caller sends the complete post-edit list;
   *  server treats it as truth. `null` clears the list. */
  problemList: z.union([ProblemListSchema, z.null()]).optional(),
});

export const PATCH = withApiHandler<{ id: string }>(
  'api:patients:update',
  async (req, { params }) => {
    const session = await getSession();
    if (!session) return apiError('unauthorized', 401);

    const blocked = rateLimitOr429(RATE_LIMITS.PATIENT_OPS, session.user.id);
    if (blocked) return blocked;

    const { id } = await params;
    const existing = await loadPatientForSession(id, session.user.practiceId);
    if (!existing) return apiError('not found', 404);

    let body: unknown;
    try {
      body = await req.json();
    } catch {
      return apiError('invalid JSON body', 400);
    }
    const parsed = UpdateBodySchema.safeParse(body);
    if (!parsed.success) {
      const first = parsed.error.issues[0];
      const field = first?.path.join('.') || '_form';
      return NextResponse.json(
        { error: first?.message || 'invalid payload', field },
        { status: 400 }
      );
    }

    // Build the update payload from only the fields the caller sent.
    // Touching every field on every PATCH would also bump updatedAt
    // spuriously and would mask "what changed?" in audit logs later.
    const data: {
      name?: string;
      dateOfBirth?: Date | null;
      externalId?: string | null;
      mrn?: string | null;
      insurance?: string | null;
      problemList?: unknown;
    } = {};
    if (parsed.data.name !== undefined) data.name = parsed.data.name;
    if (parsed.data.dateOfBirth !== undefined) {
      data.dateOfBirth =
        parsed.data.dateOfBirth === null
          ? null
          : new Date(parsed.data.dateOfBirth);
    }
    if (parsed.data.externalId !== undefined) {
      data.externalId = parsed.data.externalId;
    }
    if (parsed.data.mrn !== undefined) data.mrn = parsed.data.mrn;
    if (parsed.data.insurance !== undefined) {
      data.insurance = parsed.data.insurance;
    }
    if (parsed.data.problemList !== undefined) {
      data.problemList = parsed.data.problemList;
    }

    if (Object.keys(data).length === 0) {
      return NextResponse.json(
        { error: 'No fields to update.', field: '_form' },
        { status: 400 }
      );
    }

    const updated = await prisma.transcribeMdPatient.update({
      where: { id: existing.id },
      data,
      select: {
        id: true,
        name: true,
        dateOfBirth: true,
        externalId: true,
        mrn: true,
        insurance: true,
        problemList: true,
        updatedAt: true,
      },
    });

    void logAudit({
      action: 'TM_PATIENT_UPDATED',
      targetType: 'TranscribeMdPatient',
      targetId: updated.id,
      metadata: {
        changedFields: Object.keys(data),
      },
    });

    return NextResponse.json({ patient: updated });
  }
);

export const DELETE = withApiHandler<{ id: string }>(
  'api:patients:delete',
  async (_req, { params }) => {
    const session = await getSession();
    if (!session) return apiError('unauthorized', 401);

    const blocked = rateLimitOr429(RATE_LIMITS.PATIENT_OPS, session.user.id);
    if (blocked) return blocked;

    const { id } = await params;
    // includeDeleted:true so a repeat call returns 200 (idempotent)
    // instead of flipping to 404 after the first soft-delete.
    const existing = await loadPatientForSession(id, session.user.practiceId, {
      includeDeleted: true,
    });
    if (!existing) return apiError('not found', 404);

    if (existing.deletedAt !== null) {
      return NextResponse.json({ ok: true, alreadyDeleted: true });
    }

    await prisma.transcribeMdPatient.update({
      where: { id: existing.id },
      data: { deletedAt: new Date() },
    });

    void logAudit({
      action: 'TM_PATIENT_DELETED',
      targetType: 'TranscribeMdPatient',
      targetId: existing.id,
      metadata: { mode: 'soft' },
    });

    return NextResponse.json({ ok: true });
  }
);
