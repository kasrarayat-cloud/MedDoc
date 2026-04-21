'use server';

import { revalidatePath } from 'next/cache';
import { z } from 'zod';

import prisma from '@meddoc/db';
import { requireSession } from '@/lib/auth';

// T-M18.3 A22: specialty field removed from the form + schema. It was
// never persisted (no User.specialty column) — the dropdown read from
// the doctor's most-recent visit's specialty on open and silently
// discarded any edit on save. Specialty still gets picked per-visit
// on /visits/new, which is the actual source of truth.
const UpdateProfileSchema = z.object({
  name: z.string().trim().min(1, 'Name is required').max(120),
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
