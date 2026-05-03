'use server';

import { revalidatePath } from 'next/cache';
import { z } from 'zod';

import prisma from '@meddoc/db';
import { SPECIALTY_IDS } from '@meddoc/shared/specialties';
import { requireSession } from '@/lib/auth';

// Gate 1 added User.specialty + npi + clinicName + timeZone columns to
// support the redesign's Settings screen. All are optional on the
// form; empty strings clear the stored value. Name stays required so
// the navbar + avatar never render a blank.
const UpdateProfileSchema = z.object({
  name: z.string().trim().min(1, 'Name is required').max(120),
  // Settings dropdown includes 'unspecified' as the no-default sentinel,
  // so the enum is the full SPECIALTY_IDS list (visit-create's enum
  // would have rejected it). Saving 'unspecified' clears the column to
  // NULL via the unspecifiedToNull helper below.
  specialty: z.enum(SPECIALTY_IDS).optional().default('unspecified'),
  npi: z
    .string()
    .trim()
    .max(20)
    .regex(/^[0-9]*$/, 'NPI is digits only (10 characters)')
    .optional()
    .default(''),
  clinicName: z.string().trim().max(120).optional().default(''),
  timeZone: z.string().trim().max(60).optional().default(''),
});

export type ProfileState =
  | { ok: true; savedAt: number }
  | { ok: false; errors: Record<string, string> }
  | null;

function orNull(v: string): string | null {
  return v.length === 0 ? null : v;
}

function unspecifiedToNull(v: string): string | null {
  return v === 'unspecified' || v === '' ? null : v;
}

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
      data: {
        name: parsed.data.name,
        specialty: unspecifiedToNull(parsed.data.specialty),
        npi: orNull(parsed.data.npi),
        clinicName: orNull(parsed.data.clinicName),
        timeZone: orNull(parsed.data.timeZone),
      },
    });
  } catch (err) {
    console.error('[profile] update failed:', err);
    return { ok: false, errors: { _form: 'Could not save. Try again.' } };
  }

  revalidatePath('/settings');
  return { ok: true, savedAt: Date.now() };
}
