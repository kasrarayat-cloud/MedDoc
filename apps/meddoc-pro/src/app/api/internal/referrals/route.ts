// ============================================================================
// POST /api/internal/referrals
// ----------------------------------------------------------------------------
// Service-to-service endpoint: Scribe's Sign flow creates one Document
// per generated referral letter (M6 D2 — reuse the existing Document
// table with procedureType='Referral Letter', rather than a separate
// Referral model).
//
// Idempotency via the composite unique on documents
// (sourceScribeOutputId, sourceItemIndex). Duplicate letters at the
// same index resolve to the already-created Document.id.
// ============================================================================

import { NextResponse, type NextRequest } from 'next/server';
import type { Prisma } from '@prisma/client';
import prisma from '@meddoc/db';
import {
  CreateReferralsRequestSchema,
  type CreateReferralsResponse,
} from '@meddoc/types';
import { verifyInternalRequest } from '@/lib/internal-auth';
import { logAudit } from '@/lib/audit';

export async function POST(req: NextRequest) {
  const auth = verifyInternalRequest(req);
  if (!auth.ok) {
    return NextResponse.json({ error: auth.error }, { status: auth.status });
  }

  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: 'Invalid JSON body.' }, { status: 400 });
  }
  const parsed = CreateReferralsRequestSchema.safeParse(body);
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
      where: { id: payload.patientId },
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

  const documentIds: string[] = [];

  for (let i = 0; i < payload.letters.length; i++) {
    const letter = payload.letters[i];
    const title = `Referral Letter — ${letter.specialty} (${letter.urgency})`;

    const row = await prisma.document.upsert({
      where: {
        document_scribe_source_unique: {
          sourceScribeOutputId: payload.sourceScribeOutputId,
          sourceItemIndex: i,
        },
      },
      create: {
        patientId: patient.id,
        title,
        procedureType: 'Referral Letter',
        status: 'SIGNED',
        // Full structured letter JSON lives in content. Document render
        // layer can fall through to a plain-text fallback when it
        // doesn't recognise the shape.
        content: JSON.stringify(letter),
        createdById: payload.clinicianUserId,
        updatedById: payload.clinicianUserId,
        sourceScribeOutputId: payload.sourceScribeOutputId,
        sourceItemIndex: i,
      } satisfies Prisma.DocumentUncheckedCreateInput,
      update: {
        // Idempotent retry — preserve original contents.
      },
      select: { id: true },
    });
    documentIds.push(row.id);
  }

  await logAudit({
    action: 'CREATED_DOCUMENT',
    targetId: payload.sourceVisitId,
    targetType: 'ScribeVisit',
    userId: payload.clinicianUserId,
    practiceId: clinician.practiceId,
    metadata: {
      via: 'scribe',
      patientId: patient.id,
      subtype: 'Referral Letter',
      letterCount: documentIds.length,
      sourceScribeOutputId: payload.sourceScribeOutputId,
    },
  });

  const resp: CreateReferralsResponse = { documentIds };
  return NextResponse.json(resp, { status: 201 });
}
