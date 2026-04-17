// ============================================================================
// POST /api/internal/patients/:patientId/notes
// ----------------------------------------------------------------------------
// Service-to-service endpoint: Scribe calls this after the clinician
// hits "Sign & Send" on a SOAP review. Writes a Document with the full
// SOAP JSON in content; MedDoc Pro renders the JSON as markdown at
// display time (see SoapNoteRenderer / lib/soap-sniff.ts).
//
// Auth: bearer token + IP allowlist — see lib/internal-auth.ts.
// ============================================================================

import { NextResponse, type NextRequest } from 'next/server';
import prisma from '@meddoc/db';
import {
  CreateClinicalNoteRequestSchema,
  type CreateClinicalNoteResponse,
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
  const parsed = CreateClinicalNoteRequestSchema.safeParse(body);
  if (!parsed.success) {
    return NextResponse.json(
      { error: 'Body failed schema validation.', details: parsed.error.issues },
      { status: 400 }
    );
  }
  const payload = parsed.data;

  // Sanity gate: the clinician's practice must own the patient. This is
  // a defense layer — the service token already proves we trust the
  // caller, but we don't want a Scribe bug to send a Practice-A SOAP
  // into a Practice-B patient chart.
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

  // Persist the raw SOAP JSON as the Document.content. MedDoc Pro's
  // display layer detects JSON and renders markdown at view time — the
  // JSON stays authoritative so schema improvements can re-render old
  // documents without a backfill.
  const document = await prisma.document.create({
    data: {
      patientId: patient.id,
      title: payload.title,
      procedureType: payload.procedureType,
      status: 'SIGNED',
      content: JSON.stringify(payload.soap),
      createdById: clinician.id,
      updatedById: clinician.id,
    },
    select: { id: true },
  });

  await logAudit({
    action: 'CREATED_CLINICAL_NOTE',
    targetId: document.id,
    targetType: 'Document',
    userId: clinician.id,
    practiceId: clinician.practiceId,
    metadata: {
      via: 'scribe',
      sourceVisitId: payload.sourceVisitId,
      signedAt: payload.signedAt,
      hasMissingRequired: payload.soap.missing_required_elements.length > 0,
      soapConfidence: payload.soap.confidence,
    },
  });

  const resp: CreateClinicalNoteResponse = { documentId: document.id };
  return NextResponse.json(resp, { status: 201 });
}
