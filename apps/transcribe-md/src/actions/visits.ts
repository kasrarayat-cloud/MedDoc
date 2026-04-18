'use server';

import { redirect } from 'next/navigation';
import { revalidatePath } from 'next/cache';
import { z } from 'zod';

import prisma from '@meddoc/db';
import { requireSession } from '@/lib/auth';

const INPUT_MODES = ['audio_upload', 'voice_dictation', 'text_notes'] as const;

const CreateVisitSchema = z.object({
  patientName: z
    .string()
    .trim()
    .max(120)
    .transform((v) => (v === '' ? null : v))
    .nullable()
    .optional(),
  specialty: z.string().min(1, 'Pick a specialty'),
  chiefComplaint: z
    .string()
    .trim()
    .max(500)
    .transform((v) => (v === '' ? null : v))
    .nullable()
    .optional(),
  inputMode: z.enum(INPUT_MODES),
});

export async function createVisitAction(formData: FormData): Promise<void> {
  const session = await requireSession();
  const raw = Object.fromEntries(formData.entries());
  const parsed = CreateVisitSchema.safeParse({
    ...raw,
    // HTML checkbox/select can coerce empty strings we'd like to nullify.
    patientName: raw.patientName ?? null,
    chiefComplaint: raw.chiefComplaint ?? null,
  });
  if (!parsed.success) {
    // The form's client component re-renders and shows the error. With
    // a 1-field reason (usually invalid inputMode via query tamper) we
    // just throw — this path shouldn't be reached from the legit UI.
    throw new Error('Invalid visit input');
  }

  const visit = await prisma.transcribeVisit.create({
    data: {
      userId: session.user.id,
      patientName: parsed.data.patientName ?? null,
      specialty: parsed.data.specialty,
      chiefComplaint: parsed.data.chiefComplaint ?? null,
      inputMode: parsed.data.inputMode,
    },
    select: { id: true },
  });

  revalidatePath('/dashboard');
  redirect(`/visits/${visit.id}`);
}
