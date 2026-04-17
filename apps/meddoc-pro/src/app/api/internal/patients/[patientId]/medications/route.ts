// ============================================================================
// POST /api/internal/patients/:patientId/medications
// ----------------------------------------------------------------------------
// Service-to-service endpoint: Scribe's Sign flow appends the Rx drafts
// as active Medication rows on the patient chart.
//
// Idempotency is application-level (no DB composite unique) because drug
// names are free-text. We dedupe by (patientId, sourceScribeOutputId,
// lowercased+trimmed drug name). A retry with the same sourceScribeOutputId
// skips any drug name already present.
// ============================================================================

import { NextResponse, type NextRequest } from 'next/server';
import prisma from '@meddoc/db';
import {
  AppendMedicationsRequestSchema,
  type AppendMedicationsResponse,
} from '@meddoc/types';
import { verifyInternalRequest } from '@/lib/internal-auth';
import { logAudit } from '@/lib/audit';

function normalizeName(name: string): string {
  return name.trim().toLowerCase();
}

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
  const parsed = AppendMedicationsRequestSchema.safeParse(body);
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

  // Find existing meds already created from this ScribeOutput, keyed by
  // normalized name. We skip any incoming Rx whose name already exists.
  const existing = await prisma.medication.findMany({
    where: {
      patientId: patient.id,
      sourceScribeOutputId: payload.sourceScribeOutputId,
    },
    select: { id: true, name: true },
  });
  const existingByNormName = new Map<string, string>(
    existing.map((m: { id: string; name: string }) => [normalizeName(m.name), m.id])
  );

  const medicationIds: string[] = [];
  let dedupedCount = 0;
  const prescribedAt = new Date().toISOString().slice(0, 10);

  for (const rx of payload.prescriptions) {
    const nName = normalizeName(rx.drug);
    const prior = existingByNormName.get(nName);
    if (prior) {
      medicationIds.push(prior);
      dedupedCount += 1;
      continue;
    }
    const row = await prisma.medication.create({
      data: {
        patientId: patient.id,
        practiceId: clinician.practiceId,
        name: rx.drug,
        dosage: rx.dose,
        frequency: rx.frequency,
        isActive: true,
        notes: `Prescribed via Scribe visit ${payload.sourceVisitId} on ${prescribedAt}.`,
        createdById: payload.clinicianUserId,
        updatedById: payload.clinicianUserId,
        sourceScribeOutputId: payload.sourceScribeOutputId,
      },
      select: { id: true },
    });
    medicationIds.push(row.id);
    existingByNormName.set(nName, row.id);
  }

  await logAudit({
    action: 'CREATED_MEDICATION',
    targetId: payload.sourceVisitId,
    targetType: 'ScribeVisit',
    userId: payload.clinicianUserId,
    practiceId: clinician.practiceId,
    metadata: {
      via: 'scribe',
      patientId: patient.id,
      createdCount: medicationIds.length - dedupedCount,
      dedupedCount,
      sourceScribeOutputId: payload.sourceScribeOutputId,
    },
  });

  const resp: AppendMedicationsResponse = { medicationIds, dedupedCount };
  return NextResponse.json(resp, { status: 201 });
}
