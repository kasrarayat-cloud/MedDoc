// ============================================================================
// POST /api/internal/patients/:patientId/billing-events
// ----------------------------------------------------------------------------
// Service-to-service endpoint: Scribe's Sign flow calls this with the
// validated ICD-10 + CPT coding output. Creates ONE BillingEvent per
// Scribe coding output (unique on sourceScribeOutputId) — retry is a
// no-op that returns the existing row's id.
// ============================================================================

import { NextResponse, type NextRequest } from 'next/server';
import type { Prisma } from '@prisma/client';
import prisma from '@meddoc/db';
import {
  CreateBillingEventRequestSchema,
  type CreateBillingEventResponse,
} from '@meddoc/types';
import { verifyInternalRequest } from '@/lib/internal-auth';
import { logAudit } from '@/lib/audit';

export async function POST(
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
  const parsed = CreateBillingEventRequestSchema.safeParse(body);
  if (!parsed.success) {
    return NextResponse.json(
      { error: 'Body failed schema validation.', details: parsed.error.issues },
      { status: 400 }
    );
  }
  const payload = parsed.data;

  const [clinician, patient] = await Promise.all([
    prisma.user.findUnique({
      where: { id: payload.clinicianUserId },
      select: { id: true, practiceId: true, isActive: true },
    }),
    prisma.patient.findUnique({
      where: { id: patientId },
      select: { id: true, practiceId: true, deletedAt: true },
    }),
  ]);
  if (!clinician || !clinician.isActive) {
    return NextResponse.json({ error: 'Clinician not found or inactive.' }, { status: 400 });
  }
  if (!patient || patient.deletedAt) {
    return NextResponse.json({ error: 'Patient not found.' }, { status: 404 });
  }
  if (clinician.practiceId !== patient.practiceId) {
    return NextResponse.json(
      { error: 'Clinician and patient are in different practices.' },
      { status: 403 }
    );
  }

  // One BillingEvent per ScribeOutput — upsert by unique sourceScribeOutputId.
  const row = await prisma.billingEvent.upsert({
    where: { sourceScribeOutputId: payload.sourceScribeOutputId },
    create: {
      practiceId: clinician.practiceId,
      patientId: patient.id,
      clinicianUserId: payload.clinicianUserId,
      icd10Items: payload.coding.icd10 as unknown as Prisma.InputJsonValue,
      cptItems: payload.coding.cpt as unknown as Prisma.InputJsonValue,
      sourceVisitId: payload.sourceVisitId,
      sourceScribeOutputId: payload.sourceScribeOutputId,
    },
    update: {
      // Idempotent retry: leave existing PENDING_REVIEW row intact so
      // billing ops don't see a surprise reset. Only touch if we need to
      // (future: allow clinician-edit replay).
    },
    select: { id: true },
  });

  await logAudit({
    action: 'CREATED_BILLING_EVENT',
    targetId: row.id,
    targetType: 'BillingEvent',
    userId: payload.clinicianUserId,
    practiceId: clinician.practiceId,
    metadata: {
      via: 'scribe',
      patientId: patient.id,
      icd10Count: payload.coding.icd10.length,
      cptCount: payload.coding.cpt.length,
      sourceVisitId: payload.sourceVisitId,
      sourceScribeOutputId: payload.sourceScribeOutputId,
    },
  });

  const resp: CreateBillingEventResponse = { billingEventId: row.id };
  return NextResponse.json(resp, { status: 201 });
}
