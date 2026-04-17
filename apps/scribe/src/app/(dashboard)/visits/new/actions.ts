'use server';

import { redirect } from 'next/navigation';
import { z } from 'zod';
import prisma from '@meddoc/db';
import { getSession } from '@/lib/auth';
import { patientAccessWhere } from '@meddoc/auth';

const CreateVisitSchema = z.object({
  patientId: z.string().min(1, 'Pick a patient.'),
  specialtyId: z.string().min(1, 'Pick a specialty.'),
  mode: z.enum(['LIVE', 'BATCH']),
});

export async function createVisitAction(formData: FormData) {
  const session = await getSession();
  if (!session) throw new Error('Not authenticated.');

  const parsed = CreateVisitSchema.safeParse({
    patientId: formData.get('patientId'),
    specialtyId: formData.get('specialtyId'),
    mode: formData.get('mode'),
  });
  if (!parsed.success) {
    // Server actions + form submissions don't have a clean inline-error
    // surface yet — M1 throws so the caller sees it; polish in M2.
    throw new Error(parsed.error.issues.map((i) => i.message).join(' '));
  }

  // Tenant-gate the patient at the query layer — patientAccessWhere
  // enforces practice + role-based ownership, so a client that forges
  // a patientId from another practice gets "Patient not found."
  const patient = await prisma.patient.findFirst({
    where: {
      id: parsed.data.patientId,
      ...patientAccessWhere(session),
    },
    select: { id: true },
  });
  if (!patient) throw new Error('Patient not found.');

  // Specialty is global (not tenant-scoped). Just ensure it exists + active.
  const specialty = await prisma.scribeSpecialtyTemplate.findFirst({
    where: { id: parsed.data.specialtyId, active: true },
    select: { id: true },
  });
  if (!specialty) throw new Error('Specialty not found.');

  const visit = await prisma.scribeVisit.create({
    data: {
      practiceId: session.user.practiceId,
      userId: session.user.id,
      patientId: patient.id,
      specialtyId: specialty.id,
      mode: parsed.data.mode,
      status: 'DRAFT',
      startedAt: new Date(),
    },
    select: { id: true },
  });

  await prisma.scribeAuditEvent.create({
    data: {
      practiceId: session.user.practiceId,
      visitId: visit.id,
      actorId: session.user.id,
      action: 'CREATED_VISIT',
    },
  });

  redirect(`/visits/${visit.id}`);
}
