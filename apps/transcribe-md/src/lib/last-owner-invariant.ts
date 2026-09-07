// ============================================================================
// RULING #210 — THE FRIENDLY REFUSAL. THE ENFORCEMENT IS IN THE DATABASE.
// ----------------------------------------------------------------------------
// ⚠️ NOTHING IN THIS FILE ENFORCES ANYTHING, AND THAT IS THE DESIGN.
//
// The last-owner invariant is enforced ONCE, by the `users_last_owner_guard`
// trigger (migration `20260907040000_admin5_last_owner_trigger`), because five
// application doors can reduce a practice's active-owner count and the set is
// open — the sixth is written by whoever adds the next admin surface, and they
// will not read this file. A guard per door is a guard per door you remembered.
//
// What this file is for is the part a trigger cannot do: telling a person WHY,
// in words they can act on, BEFORE the write is attempted. A database error is
// not a user experience.
//
// ⚠️ SO A BUG HERE IS A UX DEFECT, NEVER A SAFETY ONE. If this check wrongly
// says "fine", the trigger still refuses and the caller gets a 500 instead of a
// sentence. If it wrongly says "refused", a legitimate action is blocked with a
// clear message. Neither one can strand a practice. Do not "harden" this into a
// second enforcement point — two enforcers that disagree is strictly worse than
// one, and the disagreement is invisible until it matters.
//
// ⚠️ THE PREDICATE BELOW MUST MEAN WHAT `users_is_active_owner` MEANS.
// `gate-admin5-last-owner-invariant.test.ts` asserts that by READING BOTH — the
// migration's SQL and this file — rather than by trusting the comment. A rule
// with two readers contradicts itself the day one of them is edited, and
// nothing fails while they disagree.
// ============================================================================

import prisma from '@meddoc/db';

/**
 * The ONE definition of an active practice OWNER, as a Prisma filter.
 *
 * ⚠️ THE COLUMN LIST IS NOT ARBITRARY AND IT IS NOT `deactivatedAt` ALONE.
 * `users` carries five independent expressions of "no longer active", and the
 * choice among them changes the answer on real data. Measured on production
 * 2026-09-07: six OWNER rows pass `deactivatedAt IS NULL` while being unable to
 * sign in, and one practice with ELEVEN members has two such rows and exactly
 * ONE owner who can actually administer it. A predicate that counts an owner
 * who cannot authenticate implements a proxy for the invariant, not the
 * invariant.
 */
export const ACTIVE_OWNER_WHERE = {
  practiceRole: 'OWNER',
  isActive: true,
  deactivatedAt: null,
  suspendedAt: null,
  softDeletedAt: null,
} as const;

export const LAST_OWNER_REFUSAL =
  'This is the practice’s last active owner. Transfer ownership to another member first.';

export type LastOwnerVerdict =
  | { wouldStrand: false }
  | { wouldStrand: true; reason: string; membersLeft: number };

/**
 * Would removing this user's active-owner seat leave their practice with
 * members but nobody who can administer it?
 *
 * ⚠️ MIRRORS THE TRIGGER'S TWO EXEMPTIONS DELIBERATELY, so the friendly refusal
 * and the enforcement do not disagree about the ordinary cases:
 *   1. the user is not an active owner  -> nothing is lost
 *   2. no other member remains          -> nobody is stranded; the practice is
 *      being torn down, which is the self-service deletion path
 */
export async function wouldStrandPractice(userId: string): Promise<LastOwnerVerdict> {
  const user = await prisma.user.findUnique({
    where: { id: userId },
    select: {
      id: true,
      practiceId: true,
      practiceRole: true,
      isActive: true,
      deactivatedAt: true,
      suspendedAt: true,
      softDeletedAt: true,
    },
  });
  if (!user) return { wouldStrand: false };

  // ⚠️ DERIVED FROM `ACTIVE_OWNER_WHERE`, NEVER RESTATED. Spelling the same five
  // conditions out again here would make this file its own second reader of the
  // rule — and the copy that drifts is always the one nobody is looking at.
  const isActiveOwner = (Object.entries(ACTIVE_OWNER_WHERE) as [keyof typeof ACTIVE_OWNER_WHERE, unknown][])
    .every(([column, expected]) => (user as Record<string, unknown>)[column] === expected);

  // Exemption 1 — not an active owner, so this write cannot reduce the count.
  if (!isActiveOwner) return { wouldStrand: false };

  const [ownersLeft, membersLeft] = await Promise.all([
    prisma.user.count({
      where: { practiceId: user.practiceId, id: { not: user.id }, ...ACTIVE_OWNER_WHERE },
    }),
    prisma.user.count({ where: { practiceId: user.practiceId, id: { not: user.id } } }),
  ]);

  if (ownersLeft > 0) return { wouldStrand: false };
  // Exemption 2 — nobody left to strand.
  if (membersLeft === 0) return { wouldStrand: false };

  return { wouldStrand: true, reason: LAST_OWNER_REFUSAL, membersLeft };
}
