// ============================================================================
// PATCH /api/internal/patients/:patientId/problem-list
// ----------------------------------------------------------------------------
// Service-to-service endpoint: Scribe's Sign flow merges new Dx lines
// into the patient's Patient.briefHistory array (MedDoc Pro's existing
// running clinical-context list, M6 D8).
//
// Idempotency: exact-string presence check — lines already in
// briefHistory are silently skipped. Ordering preserved; new lines are
// appended after existing ones.
// ============================================================================

import { NextResponse, type NextRequest } from 'next/server';
import prisma from '@meddoc/db';
import {
  UpdateProblemListRequestSchema,
  type UpdateProblemListResponse,
} from '@meddoc/types';
import { verifyInternalRequest } from '@/lib/internal-auth';
import { logAudit } from '@/lib/audit';

export async function PATCH(
  req: NextRequest,
  { params }: { params: Promise<{ patientId: string }> }
) {
  const auth = verifyInternalRequest(req);
  if (!auth.ok) {
    return NextResponse.json({ error: auth.error }, { status: auth.status });
  }

  const { patientId } = await params;
  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: 'Invalid JSON body.' }, { status: 400 });
  }
  const parsed = UpdateProblemListRequestSchema.safeParse(body);
  if (!parsed.success) {
    return NextResponse.json(
      { error: 'Body failed schema validation.', details: parsed.error.issues },
      { status: 400 }
    );
  }
  const payload = parsed.data;

  const patient = await prisma.patient.findUnique({
    where: { id: patientId },
    select: { id: true, practiceId: true, briefHistory: true, deletedAt: true },
  });
  if (!patient || patient.deletedAt) {
    return NextResponse.json({ error: 'Patient not found.' }, { status: 404 });
  }

  // Exact-string dedupe (D8). Order: existing lines first, then new ones
  // in the order they arrived.
  const existing = new Set(patient.briefHistory);
  const toAppend = payload.problemLines.filter((line) => !existing.has(line));
  const nextBriefHistory = [...patient.briefHistory, ...toAppend];

  if (toAppend.length > 0) {
    await prisma.patient.update({
      where: { id: patient.id },
      data: { briefHistory: nextBriefHistory },
    });
  }

  await logAudit({
    action: 'UPDATED_PATIENT',
    targetId: patient.id,
    targetType: 'Patient',
    practiceId: patient.practiceId,
    metadata: {
      via: 'scribe',
      field: 'briefHistory',
      appendedCount: toAppend.length,
      dedupedCount: payload.problemLines.length - toAppend.length,
      sourceVisitId: payload.sourceVisitId,
      sourceScribeOutputId: payload.sourceScribeOutputId,
    },
  });

  const resp: UpdateProblemListResponse = {
    appendedCount: toAppend.length,
    totalSize: nextBriefHistory.length,
  };
  return NextResponse.json(resp, { status: 200 });
}
