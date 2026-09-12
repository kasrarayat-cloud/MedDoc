'use server';

// ============================================================================
// TEMPLATE-CHOICE-1 (#318) — set the PRACTICE'S DEFAULT note template.
// ----------------------------------------------------------------------------
// The minimal OWNER setter the ruling names. Role-gated on the same
// requirePracticeAdmin gate the members page uses (DB-read practiceRole,
// fail-closed on NULL, refuse by name), validates the target is a CERTIFIED
// template IN THIS PRACTICE — the exact condition the visit fill honours, so a
// default can never be set to something the fill would reject — and audits every
// change (old -> new) under the existing PRACTICE_UPDATED action. Passing '' or
// '__clear__' clears the default (the picker falls back to per-doctor resolution).
// A members/settings surface beyond this setter is the ADMIN lane's (#318).
// ============================================================================
import { revalidatePath } from 'next/cache';
import { z } from 'zod';

import prisma from '@meddoc/db';

import { logAudit } from '@/lib/audit';
import { getSession } from '@/lib/auth';
import { requirePracticeAdmin, type AdminRefusal } from '@/lib/practice-admin';

export type DefaultTemplateState =
  | { ok: true; defaultNoteTemplateId: string | null }
  | {
      ok: false;
      reason: AdminRefusal | 'INVALID' | 'TEMPLATE_NOT_CERTIFIED';
      message: string;
    }
  | null;

const Schema = z.object({
  // '' or '__clear__' clears the default; otherwise a template id in the practice.
  templateId: z.string().trim().max(200),
});

export async function setPracticeDefaultTemplateAction(
  _prev: DefaultTemplateState,
  formData: FormData,
): Promise<DefaultTemplateState> {
  const guard = await requirePracticeAdmin(await getSession());
  if (!guard.ok) return { ok: false, reason: guard.reason, message: guard.message };

  const parsed = Schema.safeParse({ templateId: formData.get('templateId') ?? '' });
  if (!parsed.success) {
    return { ok: false, reason: 'INVALID', message: 'Invalid template selection.' };
  }

  const raw = parsed.data.templateId;
  let toSet: string | null = null;
  if (raw !== '' && raw !== '__clear__') {
    // The SAME condition the worker + fill honour (certificationStatus ===
    // 'CERTIFIED'), scoped to THIS practice — a default is never a co-tenant's
    // draft, another practice's row, or an uncertified template.
    const t = await prisma.noteTemplate.findFirst({
      where: {
        id: raw,
        practiceId: guard.practiceId,
        templateTwinCompiledVersion: { is: { certificationStatus: 'CERTIFIED' } },
      },
      select: { id: true },
    });
    if (!t) {
      return {
        ok: false,
        reason: 'TEMPLATE_NOT_CERTIFIED',
        message: 'That template is not a certified template in your practice.',
      };
    }
    toSet = t.id;
  }

  const before = await prisma.practice.findUnique({
    where: { id: guard.practiceId },
    select: { defaultNoteTemplateId: true },
  });
  await prisma.practice.update({
    where: { id: guard.practiceId },
    data: { defaultNoteTemplateId: toSet },
  });

  await logAudit({
    action: 'PRACTICE_UPDATED',
    targetType: 'Practice',
    targetId: guard.practiceId,
    metadata: {
      field: 'defaultNoteTemplateId',
      from: before?.defaultNoteTemplateId ?? null,
      to: toSet,
    },
  });

  revalidatePath('/settings');
  revalidatePath('/visits/new');
  return { ok: true, defaultNoteTemplateId: toSet };
}
