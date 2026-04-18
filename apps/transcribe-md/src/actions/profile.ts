'use server';

import { revalidatePath } from 'next/cache';
import { z } from 'zod';

import prisma from '@meddoc/db';
import { requireSession } from '@/lib/auth';

const UpdateProfileSchema = z.object({
  name: z.string().trim().min(1, 'Name is required').max(120),
  specialty: z.string().trim().min(1, 'Specialty is required'),
});

export type ProfileState =
  | { ok: true; savedAt: number }
  | { ok: false; errors: Record<string, string> }
  | null;

export async function updateProfileAction(
  _prev: ProfileState,
  formData: FormData
): Promise<ProfileState> {
  const session = await requireSession();
  const parsed = UpdateProfileSchema.safeParse(
    Object.fromEntries(formData.entries())
  );
  if (!parsed.success) {
    const errors: Record<string, string> = {};
    for (const issue of parsed.error.issues) {
      const key = issue.path.join('.') || '_form';
      if (!errors[key]) errors[key] = issue.message;
    }
    return { ok: false, errors };
  }

  // Specialty is stored as the most recent visit's specialty field
  // (there's no User.specialty column yet; T-M2.5 adds one). For now
  // we only persist the name. The specialty defaults to user's most-
  // recent visit at /visits/new time.
  try {
    await prisma.user.update({
      where: { id: session.user.id },
      data: { name: parsed.data.name },
    });
  } catch (err) {
    console.error('[profile] update failed:', err);
    return { ok: false, errors: { _form: 'Could not save. Try again.' } };
  }

  revalidatePath('/settings');
  return { ok: true, savedAt: Date.now() };
}
