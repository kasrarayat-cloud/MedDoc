'use server';

import bcrypt from 'bcryptjs';
import { revalidatePath } from 'next/cache';
import prisma from '@meddoc/db';
import { getSession } from '@/lib/auth';
import { logAudit } from '@/lib/audit';
import { validatePassword } from '@/lib/password-schema';

export interface ActionResult {
  ok: boolean;
  error?: string;
}

export async function updateProfile(formData: FormData): Promise<ActionResult> {
  const session = await getSession();
  if (!session) return { ok: false, error: 'Not authenticated.' };

  const nameRaw = formData.get('name');
  if (typeof nameRaw !== 'string' || !nameRaw.trim()) {
    return { ok: false, error: 'Name is required.' };
  }

  try {
    await prisma.user.update({
      where: { id: session.user.id },
      data: { name: nameRaw.trim() },
    });

    revalidatePath('/dashboard/settings');
    return { ok: true };
  } catch (err) {
    console.error('[settings] Profile update failed:', err);
    return { ok: false, error: 'Failed to update profile.' };
  }
}

export async function updatePassword(formData: FormData): Promise<ActionResult> {
  const session = await getSession();
  if (!session) return { ok: false, error: 'Not authenticated.' };

  const currentPassword = formData.get('currentPassword');
  const newPassword = formData.get('newPassword');
  const confirmNewPassword = formData.get('confirmNewPassword');

  if (typeof currentPassword !== 'string' || !currentPassword) {
    return { ok: false, error: 'Current password is required.' };
  }
  if (typeof newPassword !== 'string' || !newPassword) {
    return { ok: false, error: 'New password is required.' };
  }
  const policy = validatePassword(newPassword);
  if (!policy.ok) {
    return { ok: false, error: policy.error };
  }
  if (newPassword !== String(confirmNewPassword ?? '')) {
    return { ok: false, error: 'New passwords do not match.' };
  }

  try {
    const user = await prisma.user.findUnique({
      where: { id: session.user.id },
      select: { passwordHash: true },
    });
    if (!user) return { ok: false, error: 'User not found.' };

    const valid = await bcrypt.compare(currentPassword, user.passwordHash);
    if (!valid) return { ok: false, error: 'Current password is incorrect.' };

    const passwordHash = await bcrypt.hash(newPassword, 12);
    await prisma.user.update({
      where: { id: session.user.id },
      data: { passwordHash },
    });

    logAudit({
      action: 'PASSWORD_CHANGED',
      targetId: session.user.id,
      targetType: 'User',
    }).catch(() => {});

    return { ok: true };
  } catch (err) {
    console.error('[settings] Password update failed:', err);
    return { ok: false, error: 'Failed to update password.' };
  }
}
