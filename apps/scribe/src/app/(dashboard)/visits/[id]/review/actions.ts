'use server';

import { revalidatePath } from 'next/cache';
import type { OutputType } from '@prisma/client';
import type { z } from 'zod';
import prisma from '@meddoc/db';
import {
  SoapNoteSchema,
  CodingOutputSchema,
  RxOutputSchema,
  ReferralOutputSchema,
  PatientSummarySchema,
  CreateClinicalNoteRequestSchema,
  type SoapNote,
  type CodingOutput,
  type RxOutput,
  type ReferralOutput,
  type PatientSummary,
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

/**
 * Shared save-edit helper. Re-validates the edited blob with the output's
 * success schema (the schema is .strict() so it refuses to accept an
 * OutputError sentinel, per D2), finds the latest row of this type, and
 * updates its content + marks editedByClinician.
 */
async function saveEditedOutput<T>(args: {
  visitId: string;
  type: OutputType;
  schema: z.ZodType<T>;
  value: T;
  editAction: string;
}): Promise<void> {
  const session = await getSession();
  if (!session) throw new Error('Not authenticated.');

  const parsed = args.schema.safeParse(args.value);
  if (!parsed.success) {
    throw new Error(
      `Edited ${args.type} failed schema validation: ${JSON.stringify(parsed.error.issues)}`
    );
  }

  const visit = await prisma.scribeVisit.findFirst({
    where: { id: args.visitId, ...tenantScope(session), deletedAt: null },
    select: { id: true, practiceId: true },
  });
  if (!visit) throw new Error('Visit not found.');

  const existing = await prisma.scribeOutput.findFirst({
    where: { visitId: visit.id, type: args.type },
    orderBy: { createdAt: 'desc' },
  });
  if (!existing) throw new Error(`No ${args.type} output for this visit.`);

  await prisma.scribeOutput.update({
    where: { id: existing.id },
    data: {
      content: parsed.data as object,
      editedByClinician: true,
    },
  });

  await prisma.scribeAuditEvent.create({
    data: {
      practiceId: visit.practiceId,
      visitId: visit.id,
      actorId: session.user.id,
      action: args.editAction,
      diff: { previous: existing.content, next: parsed.data },
    },
  });

  revalidatePath(`/visits/${visit.id}/review`);
}

export async function saveEditedSoapAction(args: { visitId: string; soap: SoapNote }): Promise<void> {
  await saveEditedOutput({
    visitId: args.visitId,
    type: 'SOAP',
    schema: SoapNoteSchema,
    value: args.soap,
    editAction: 'EDITED_SOAP',
  });
}

export async function saveEditedCodingAction(args: {
  visitId: string; coding: CodingOutput;
}): Promise<void> {
  await saveEditedOutput({
    visitId: args.visitId,
    type: 'ICD10_CPT',
    schema: CodingOutputSchema,
    value: args.coding,
    editAction: 'EDITED_CODING',
  });
}

export async function saveEditedRxAction(args: {
  visitId: string; rx: RxOutput;
}): Promise<void> {
  await saveEditedOutput({
    visitId: args.visitId,
    type: 'RX',
    schema: RxOutputSchema,
    value: args.rx,
    editAction: 'EDITED_RX',
  });
}

export async function saveEditedReferralsAction(args: {
  visitId: string; referrals: ReferralOutput;
}): Promise<void> {
  await saveEditedOutput({
    visitId: args.visitId,
    type: 'REFERRAL',
    schema: ReferralOutputSchema,
    value: args.referrals,
    editAction: 'EDITED_REFERRAL',
  });
}

export async function saveEditedPatientSummaryAction(args: {
  visitId: string; summary: PatientSummary;
}): Promise<void> {
  await saveEditedOutput({
    visitId: args.visitId,
    type: 'PATIENT_SUMMARY',
    schema: PatientSummarySchema,
    value: args.summary,
    editAction: 'EDITED_PATIENT_SUMMARY',
  });
}

/**
 * Sign the visit:
 *   - Validate the latest SOAP row
 *   - POST it to MedDoc Pro's /api/internal/patients/:id/notes
 *     (unchanged from M2; non-SOAP outputs remain in Scribe until M6)
 *   - Stamp signedAt/signedBy on the latest row of EVERY output type so
 *     the review UI becomes read-only across all tabs (D9)
 *   - Transition visit status to SIGNED
 */
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

  const latestSoap = await prisma.scribeOutput.findFirst({
    where: { visitId: visit.id, type: 'SOAP' },
    orderBy: { createdAt: 'desc' },
  });
  if (!latestSoap) throw new Error('No SOAP output to sign.');
  const soapValidated = SoapNoteSchema.parse(latestSoap.content);
  const signedAt = new Date();
  const signedAtIso = signedAt.toISOString();

  const reqBody = CreateClinicalNoteRequestSchema.parse({
    sourceVisitId: visit.id,
    clinicianUserId: session.user.id,
    title: `${signedAtIso.slice(0, 10)} • ${visit.specialty.displayName} visit — ${visit.patient.lastName}, ${visit.patient.firstName}`,
    procedureType: visit.specialty.displayName,
    soap: soapValidated,
    signedAt: signedAtIso,
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

  // Stamp signedAt/signedBy on the latest row of EVERY output type —
  // even FLAG_OFF / ERROR rows — so the UI uniformly locks all tabs on
  // a signed visit (D9). If no row exists for a type, skip.
  const types: OutputType[] = ['SOAP', 'ICD10_CPT', 'RX', 'REFERRAL', 'PATIENT_SUMMARY'];
  for (const type of types) {
    const latest = await prisma.scribeOutput.findFirst({
      where: { visitId: visit.id, type, signedAt: null },
      orderBy: { createdAt: 'desc' },
      select: { id: true },
    });
    if (latest) {
      await prisma.scribeOutput.update({
        where: { id: latest.id },
        data: { signedAt, signedBy: session.user.id },
      });
    }
  }

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
      diff: { documentId: respBody.documentId, signedAt: signedAtIso, outputsStamped: types },
    },
  });

  revalidatePath(`/visits/${visit.id}`);
  revalidatePath(`/visits/${visit.id}/review`);
  return { documentId: respBody.documentId };
}
