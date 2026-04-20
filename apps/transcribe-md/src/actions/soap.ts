'use server';

import { revalidatePath } from 'next/cache';
import { z } from 'zod';

import prisma from '@meddoc/db';
import { TranscribeVisitStatus } from '@prisma/client';
import { requireSession } from '@/lib/auth';
import { captureEditPattern } from '@/lib/edit-tracking';

const SaveSoapSchema = z.object({
  visitId: z.string().min(1),
  text: z.string().max(50_000),
});

export interface SaveSoapResult {
  ok: boolean;
  error?: string;
}

/** Persists the user's edits to soapFinal. Signed visits are locked —
 *  the action rejects rather than silently dropping the write. */
export async function saveSoapDraftAction(
  visitId: string,
  text: string
): Promise<SaveSoapResult> {
  const session = await requireSession();
  const parsed = SaveSoapSchema.safeParse({ visitId, text });
  if (!parsed.success) {
    return { ok: false, error: 'Invalid input.' };
  }

  const visit = await prisma.transcribeVisit.findUnique({
    where: { id: visitId },
    select: { id: true, userId: true, status: true },
  });
  if (!visit || visit.userId !== session.user.id) {
    return { ok: false, error: 'Visit not found.' };
  }
  if (visit.status === TranscribeVisitStatus.SIGNED) {
    return { ok: false, error: 'Signed notes cannot be edited.' };
  }
  if (visit.status !== TranscribeVisitStatus.READY) {
    return { ok: false, error: 'Note is still processing.' };
  }

  await prisma.transcribeVisit.update({
    where: { id: visitId },
    data: { soapFinal: parsed.data.text },
  });

  revalidatePath(`/visits/${visitId}`);
  return { ok: true };
}

/** Freezes the current soapFinal into signedSoap and flips status to
 *  SIGNED. Idempotent — signing an already-signed visit is a no-op
 *  from the client's perspective. */
export async function signVisitAction(
  visitId: string
): Promise<SaveSoapResult> {
  const session = await requireSession();

  const visit = await prisma.transcribeVisit.findUnique({
    where: { id: visitId },
    select: {
      id: true,
      userId: true,
      status: true,
      soapFinal: true,
      signedAt: true,
    },
  });
  if (!visit || visit.userId !== session.user.id) {
    return { ok: false, error: 'Visit not found.' };
  }
  if (visit.status === TranscribeVisitStatus.SIGNED) {
    return { ok: true };
  }
  if (visit.status !== TranscribeVisitStatus.READY) {
    return { ok: false, error: 'Note is still processing.' };
  }
  if (!visit.soapFinal?.trim()) {
    return { ok: false, error: 'No SOAP content to sign.' };
  }

  await prisma.transcribeVisit.update({
    where: { id: visitId },
    data: {
      status: TranscribeVisitStatus.SIGNED,
      signedSoap: visit.soapFinal,
      signedAt: new Date(),
    },
  });

  // T-M14.1: fire-and-forget edit-pattern capture. captureEditPattern
  // swallows every error internally — discarding the promise with
  // `void` keeps this action's happy path unaffected.
  void captureEditPattern({ visitId, doctorId: session.user.id });

  revalidatePath(`/visits/${visitId}`);
  revalidatePath('/dashboard');
  return { ok: true };
}

const SpeakerRoleKeys = z.enum(['doctor', 'patient', 'family', 'other', 'unknown']);

const ReassignSpeakerSchema = z.object({
  visitId: z.string().min(1),
  speakerId: z.string().min(1),
  role: SpeakerRoleKeys,
});

/** Manual override for Layer 2 — doctor can correct a mis-assigned
 *  speaker role from the Transcript tab. Updates speakerMap in place,
 *  keeps reasoning + confidence intact (just flips role).
 *  Does NOT re-run the downstream layers; surfaces a toast to the
 *  client asking them to regenerate if they want the SOAP updated. */
export async function reassignSpeakerAction(
  visitId: string,
  speakerId: string,
  role: string
): Promise<SaveSoapResult> {
  const session = await requireSession();
  const parsed = ReassignSpeakerSchema.safeParse({ visitId, speakerId, role });
  if (!parsed.success) {
    return { ok: false, error: 'Invalid speaker role.' };
  }

  const visit = await prisma.transcribeVisit.findUnique({
    where: { id: visitId },
    select: { id: true, userId: true, status: true, speakerMap: true },
  });
  if (!visit || visit.userId !== session.user.id) {
    return { ok: false, error: 'Visit not found.' };
  }
  if (visit.status === TranscribeVisitStatus.SIGNED) {
    return { ok: false, error: 'Signed notes cannot be edited.' };
  }

  // Prisma Json typing is loose; treat as record + write back.
  const map = (visit.speakerMap as Record<string, {
    role: string;
    confidence: number;
    reasoning: string;
  }> | null) ?? {};
  map[parsed.data.speakerId] = {
    ...(map[parsed.data.speakerId] ?? { confidence: 1, reasoning: '' }),
    role: parsed.data.role,
    // Manual override → high confidence, marker reasoning so the
    // Pipeline tab can show "(manually reassigned)" later.
    confidence: 1,
    reasoning: `Manually reassigned by ${session.user.email}.`,
  };

  await prisma.transcribeVisit.update({
    where: { id: visitId },
    data: { speakerMap: map as unknown as object },
  });

  revalidatePath(`/visits/${visitId}`);
  return { ok: true };
}
