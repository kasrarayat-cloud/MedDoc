// ============================================================================
// GET /api/internal/patients/:patientId/clinical-safety
// ----------------------------------------------------------------------------
// Service-to-service endpoint: Scribe's finalize_visit worker calls this
// before drafting Rx, so Claude can see the patient's active medications
// and allergies when flagging interactions / duplicates / allergy
// conflicts (spec §11 item 4 + M4 D3/D4).
//
// Auth: bearer SCRIBE_SERVICE_TOKEN + IP allowlist (reject any request
// carrying x-forwarded-for — Caddy doesn't proxy /api/internal/* so an
// XFF header means external origin). Same pattern as the M2 /notes
// endpoint.
//
// Active/deletion filtering:
//   - Medications: all non-deleted rows; we include isActive so Claude
//     can distinguish current from historical prescriptions (and the
//     patient's chart has a "show stopped meds" toggle already).
//   - Allergies: non-soft-deleted rows only. deletedAt=null.
// ============================================================================

import { NextResponse, type NextRequest } from 'next/server';
import prisma from '@meddoc/db';
import {
  ClinicalSafetyResponseSchema,
  type ClinicalSafetyResponse,
} from '@meddoc/types';
import { verifyInternalRequest } from '@/lib/internal-auth';

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ patientId: string }> }
) {
  const auth = verifyInternalRequest(req);
  if (!auth.ok) {
    return NextResponse.json({ error: auth.error }, { status: auth.status });
  }

  const { patientId } = await params;

  const patient = await prisma.patient.findFirst({
    where: { id: patientId, deletedAt: null },
    select: {
      id: true,
      allergies: {
        where: { deletedAt: null },
        select: {
          allergen: true,
          reaction: true,
          severity: true,
          notes: true,
        },
      },
      medications: {
        where: { deletedAt: null },
        select: {
          name: true,
          dosage: true,
          frequency: true,
          isActive: true,
          notes: true,
        },
      },
    },
  });
  if (!patient) {
    return NextResponse.json({ error: 'Patient not found.' }, { status: 404 });
  }

  const body: ClinicalSafetyResponse = {
    patientId: patient.id,
    medications: patient.medications,
    allergies: patient.allergies,
  };
  // Validate before returning so a Prisma shape drift can't silently
  // break the Scribe contract — this schema is the single source of
  // truth for both apps (packages/types).
  const parsed = ClinicalSafetyResponseSchema.safeParse(body);
  if (!parsed.success) {
    return NextResponse.json(
      {
        error: 'Internal shape drift — response failed schema validation.',
        details: parsed.error.issues,
      },
      { status: 500 }
    );
  }
  return NextResponse.json(parsed.data);
}
