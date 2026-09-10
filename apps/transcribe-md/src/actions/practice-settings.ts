'use server';

// ============================================================================
// ADMIN-2a — A PRACTICE OWNER'S ONE-TIME CLAIM OF A HUMAN-CHOSEN SLUG.
// ----------------------------------------------------------------------------
// 195 of 199 production practices carry the machine slug signup minted
// (`solo-<rand>-<base36 ts>`), and ADMIN-2 keys hostnames on `Practice.slug`.
// Until this file only a SUPER_ADMIN could change one, through
// `PATCH /api/admin/practices/[id]`.
//
// ⚠️ ONE-TIME, AND THE REASON IS ADMIN-2, NOT TIDINESS. Once a slug is a live
// subdomain, changing it strands every host-only cookie and every bookmark the
// practice has. So an owner may move OFF the machine namespace exactly once;
// every later change stays SUPER_ADMIN-only on the existing route, where a
// human who can see the consequences makes it. The refusal says so.
//
// ⚠️ A SEPARATE FILE FROM `practice-members.ts` ON PURPOSE. ADMIN-5 edits that
// file; the practice's own settings are a different axis from its members.
//
// ⚠️ NO `practice.update` HERE. The write goes through `updatePractice`, the one
// verb `gate-admin3a` pins, so the audit row, the allowlist and the label guard
// are the SUPER_ADMIN route's own — not a second copy of each.
// ============================================================================

import { revalidatePath } from 'next/cache';

import prisma from '@meddoc/db';

import { getSession } from '@/lib/auth';
import { requirePracticeAdmin, type AdminRefusal } from '@/lib/practice-admin';
import {
  isMachineSlug,
  practiceLabelRefusal,
  updatePractice,
  type PracticeWriteRefusal,
} from '@/lib/practice-write';

const MEMBERS_PATH = '/settings/members';

/** Recorded as the audit row's `reason`, so an owner's claim is greppable
 *  apart from a SUPER_ADMIN edit — both write `PRACTICE_UPDATED`. */
const CLAIM_AUDIT_REASON = 'ADMIN-2a one-time owner claim of a machine slug';

export type SlugClaimRefusal =
  | AdminRefusal
  | PracticeWriteRefusal
  | 'ALREADY_CLAIMED'
  | 'PRACTICE_ARCHIVED'
  | 'INVALID';

export type SlugClaimState =
  | { ok: true; slug: string }
  | { ok: false; reason: SlugClaimRefusal; message: string }
  | null;

/** Every refusal in the doctor's words. One map, so a message cannot drift
 *  from the code that returns it. (Not exported — a `'use server'` module may
 *  export async functions only.) */
const MESSAGE: Partial<Record<SlugClaimRefusal, string>> = {
  INVALID: 'Enter a name for your practice address.',
  invalid_slug:
    'Use 3 to 63 lowercase letters, numbers or hyphens. It cannot start or end with a hyphen, or have two hyphens in the third and fourth places.',
  reserved_slug:
    'That name is reserved — it is used by QuillMD itself, or begins with "solo-", which is kept for practices created automatically. Choose another.',
  slug_taken: 'Another practice already has that name. Choose another.',
  ALREADY_CLAIMED:
    "Your practice's address name has already been chosen, and an owner can choose it only once. Later changes are made by QuillMD support, so existing links and sign-ins keep working — contact support to change it.",
  changed_under_you:
    "Your practice's address name was changed by someone else a moment ago. Nothing was saved — reload the page to see it.",
  PRACTICE_ARCHIVED: 'This practice is archived, so its address name cannot be chosen.',
  not_found: 'Your practice could not be found. Reload the page and try again.',
};

function refuse(reason: SlugClaimRefusal, fallback?: string): SlugClaimState {
  return {
    ok: false,
    reason,
    message: MESSAGE[reason] ?? fallback ?? 'That could not be saved. Reload the page and try again.',
  };
}

export async function claimPracticeSlug(
  _prev: SlugClaimState,
  formData: FormData,
): Promise<SlugClaimState> {
  // ⚠️ THE GUARD FIRST, before the input is even read. It re-reads the actor's
  // role from the database and audits a refusal; an unauthenticated caller
  // learns nothing about which names are reserved or taken.
  const guard = await requirePracticeAdmin(await getSession());
  if (!guard.ok) return { ok: false, reason: guard.reason, message: guard.message };

  const raw = formData.get('slug');
  if (typeof raw !== 'string' || raw.trim().length === 0) return refuse('INVALID');
  // Trim and lowercase only. DNS labels are case-insensitive, so this cannot
  // turn one name into a different one; nothing else is rewritten.
  const slug = raw.trim().toLowerCase();

  // Pure, before any read — the same predicate `updatePractice` applies again.
  const labelRefusal = practiceLabelRefusal(slug);
  if (labelRefusal) return refuse(labelRefusal);

  // ⚠️ THE PRACTICE IS THE GUARD'S, NEVER THE FORM'S. A posted `practiceId` is
  // ignored — the only practice an owner can claim for is the one the database
  // says they administer.
  const practice = await prisma.practice.findUnique({
    where: { id: guard.practiceId },
    select: { slug: true, isActive: true },
  });
  if (!practice) return refuse('not_found');
  // Fail closed: an archived practice does not take a name from the pool.
  if (!practice.isActive) return refuse('PRACTICE_ARCHIVED');
  if (!isMachineSlug(practice.slug)) return refuse('ALREADY_CLAIMED');

  const result = await updatePractice({
    practiceId: guard.practiceId,
    patch: { slug },
    actorUserId: guard.actorId,
    reason: CLAIM_AUDIT_REASON,
    // ⚠️ THE COMPARE-AND-SET THAT MAKES "ONE-TIME" TRUE UNDER CONCURRENCY. Two
    // owners of one practice both read the machine slug; only the first UPDATE
    // matches `slug = <machine slug>`, and the second is refused.
    ifSlugIs: practice.slug,
  });
  if (!result.ok) return refuse(result.reason, result.detail);

  revalidatePath(MEMBERS_PATH);
  return { ok: true, slug };
}
