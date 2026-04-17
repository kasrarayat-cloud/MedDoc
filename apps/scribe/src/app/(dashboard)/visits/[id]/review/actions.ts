'use server';

import { revalidatePath } from 'next/cache';
import prisma from '@meddoc/db';
import {
  SoapNoteSchema,
  CreateClinicalNoteRequestSchema,
  type SoapNote,
  type CreateClinicalNoteResponse,
} from '@meddoc/types';
import { getSession } from '@/lib/auth';
import { tenantScope } from '@meddoc/auth';

const MEDDOC_PRO_INTERNAL_URL =
  process.env.MEDDOC_PRO_INTERNAL_URL?.trim() || 'http://meddoc-pro:3000';

function getInternalToken(): string {
  const token = process.env.SCRIBE_SERVICE_TOKEN;
  if (!token) throw new Error('SCRIBE_SERVICE_TOKEN is not set.');
  return token;
}

interface SaveArgs {
  visitId: string;
  soap: SoapNote;
}

export async function saveEditedSoapAction(args: SaveArgs): Promise<void> {
  const session = await getSession();
  if (!session) throw new Error('Not authenticated.');

  const parsed = SoapNoteSchema.safeParse(args.soap);
  if (!parsed.success) {
    throw new Error('Edited SOAP failed schema validation: ' + JSON.stringify(parsed.error.issues));
  }

  const visit = await prisma.scribeVisit.findFirst({
    where: { id: args.visitId, ...tenantScope(session), deletedAt: null },
    select: { id: true, practiceId: true },
  });
  if (!visit) throw new Error('Visit not found.');

  const existing = await prisma.scribeOutput.findFirst({
    where: { visitId: visit.id, type: 'SOAP' },
    orderBy: { createdAt: 'desc' },
  });
  if (!existing) throw new Error('No SOAP output for this visit.');

  await prisma.scribeOutput.update({
    where: { id: existing.id },
    data: {
      content: parsed.data,
      editedByClinician: true,
    },
  });

  await prisma.scribeAuditEvent.create({
    data: {
      practiceId: visit.practiceId,
      visitId: visit.id,
      actorId: session.user.id,
      action: 'EDITED_SOAP',
      diff: { previous: existing.content, next: parsed.data },
    },
  });

  revalidatePath(`/visits/${visit.id}/review`);
}

export async function signAndSendVisitAction(args: {
  visitId: string;
}): Promise<{ documentId: string }> {
  const session = await getSession();
  if (!session) throw new Error('Not authenticated.');

  const visit = await prisma.scribeVisit.findFirst({
    where: { id: args.visitId, ...tenantScope(session), deletedAt: null },
    select: {
      id: true,
      practiceId: true,
      userId: true,
      patientId: true,
      status: true,
      specialty: { select: { displayName: true, version: true } },
      patient: { select: { firstName: true, lastName: true, chartId: true } },
    },
  });
  if (!visit) throw new Error('Visit not found.');
  if (visit.status !== 'READY_FOR_REVIEW') {
    throw new Error(`Visit is in status ${visit.status}; cannot sign.`);
  }

  const latest = await prisma.scribeOutput.findFirst({
    where: { visitId: visit.id, type: 'SOAP' },
    orderBy: { createdAt: 'desc' },
  });
  if (!latest) throw new Error('No SOAP output to sign.');

  const soapValidated = SoapNoteSchema.parse(latest.content);
  const signedAt = new Date().toISOString();

  const reqBody = CreateClinicalNoteRequestSchema.parse({
    sourceVisitId: visit.id,
    clinicianUserId: session.user.id,
    title: `${signedAt.slice(0, 10)} • ${visit.specialty.displayName} visit — ${visit.patient.lastName}, ${visit.patient.firstName}`,
    procedureType: visit.specialty.displayName,
    soap: soapValidated,
    signedAt,
  });

  const resp = await fetch(
    `${MEDDOC_PRO_INTERNAL_URL}/api/internal/patients/${visit.patientId}/notes`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${getInternalToken()}`,
      },
      body: JSON.stringify(reqBody),
    }
  );
  if (!resp.ok) {
    const txt = await resp.text().catch(() => '');
    throw new Error(`MedDoc Pro internal API returned ${resp.status}: ${txt.slice(0, 300)}`);
  }
  const respBody = (await resp.json()) as CreateClinicalNoteResponse;

  await prisma.scribeOutput.update({
    where: { id: latest.id },
    data: { signedAt: new Date(signedAt), signedBy: session.user.id },
  });
  await prisma.scribeVisit.update({
    where: { id: visit.id },
    data: { status: 'SIGNED' },
  });
  await prisma.scribeAuditEvent.create({
    data: {
      practiceId: visit.practiceId,
      visitId: visit.id,
      actorId: session.user.id,
      action: 'SIGNED_VISIT',
      diff: { documentId: respBody.documentId, signedAt },
    },
  });

  revalidatePath(`/visits/${visit.id}`);
  revalidatePath(`/visits/${visit.id}/review`);
  return { documentId: respBody.documentId };
}
