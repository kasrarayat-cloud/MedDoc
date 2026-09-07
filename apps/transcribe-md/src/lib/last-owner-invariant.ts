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

/**
 * The SAME predicate as raw SQL, for callers that write SQL rather than Prisma.
 *
 * ⚠️ RULING #221 — THE TRIGGER, THIS FILE, AND #1026'S GUARD ALL DERIVE FROM
 * `ACTIVE_OWNER_WHERE`. #1026 writes a raw `LAST_OWNER_CLAUSE`, so without a
 * generator its only options were to import nothing and restate the rule, or to
 * "add four conditions to that subquery" — which authors the second copy the
 * ruling exists to prevent. This is the third reader's door in.
 *
 * ⚠️ AND THE DIVERGENCE IS NOT HYPOTHETICAL. Measured against production:
 * #1026's clause counts `deactivatedAt IS NULL` alone, so SIX owner rows count
 * as owners while unable to sign in, and one practice with ELEVEN members reads
 * two owners against ONE who can actually administer it.
 *
 * `gate-admin5-last-owner-invariant.test.ts` asserts this generator's output is
 * clause-for-clause the migration's `users_is_active_owner` body, so the SQL
 * side cannot drift from the TypeScript side without something going red.
 */
function whereToSql(where: Readonly<Record<string, unknown>>, alias: string): string {
  return (Object.entries(where) as [string, unknown][])
    .map(([column, value]) => {
      if (value === null) return `${alias}."${column}" IS NULL`;
      if (value === true) return `${alias}."${column}"`;
      return `${alias}."${column}" = '${String(value)}'::"PracticeRole"`;
    })
    .join('\n       AND ');
}

export function activeOwnerSql(alias: string): string {
  return whereToSql(ACTIVE_OWNER_WHERE, alias);
}

/**
 * The ONE definition of a member who could actually be STRANDED — ruling #239.
 *
 * ⚠️ THIS EXISTS BECAUSE THE FIX WAS APPLIED TO ONE READER AND NOT THE OTHER.
 * The migration's own comment beside `users_is_live_member` records it:
 * *"Exemption 2 asks 'is anyone left to strand?', and the first version answered
 * it with a bare row count. Refuted in this change's adversarial pass."* The
 * trigger was corrected. `wouldStrandPractice` below still counted rows, so the
 * two layers disagreed on real production practices — **and the disagreement
 * runs in the harmful direction**: the app refuses a write the trigger ALLOWS,
 * and the refusal tells the doctor to *"transfer ownership to another member"*
 * when the only other member is a soft-deleted ex-employee who cannot receive
 * it.
 *
 * ⚠️ A REFUSAL NAMING A REMEDY THAT CANNOT BE PERFORMED IS WORSE THAN NO
 * REFUSAL, because the doctor spends the afternoon trying to perform it.
 *
 * #221 gave "able owner" one predicate. This is the same rule for the other
 * half, and the same gate reads both against the migration's SQL.
 */
export const LIVE_MEMBER_WHERE = {
  isActive: true,
  deactivatedAt: null,
  softDeletedAt: null,
  suspendedAt: null,
} as const;

/** The SAME predicate as raw SQL, for callers that write SQL rather than Prisma. */
export function liveMemberSql(alias: string): string {
  return whereToSql(LIVE_MEMBER_WHERE, alias);
}

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
  // ⚠️ THE SELECT IS DERIVED FROM THE PREDICATE, NOT RETYPED BESIDE IT.
  // The adversarial pass found this list was a THIRD uncoupled restatement of
  // the column set: adding a column to `ACTIVE_OWNER_WHERE` and forgetting it
  // here makes the field arrive `undefined`, `undefined === null` is false, and
  // the row silently stops counting as an active owner — no error, no red test.
  // Derived, a forgotten column is impossible by construction.
  const user = await prisma.user.findUnique({
    where: { id: userId },
    select: {
      id: true,
      practiceId: true,
      ...(Object.fromEntries(
        Object.keys(ACTIVE_OWNER_WHERE).map((c) => [c, true])
      ) as Record<keyof typeof ACTIVE_OWNER_WHERE, true>),
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
    // ⚠️ LIVE MEMBERS, NOT ROWS — RULING #239. This was
    // `count({ where: { practiceId, id: { not } } })`: a bare row count, while
    // the trigger asks `users_is_live_member`. A practice whose only other row
    // is soft-deleted or deactivated reads `membersLeft > 0` here and `0` at the
    // trigger, so this file refused a write the database permits — and named a
    // remedy nobody can perform.
    prisma.user.count({
      where: { practiceId: user.practiceId, id: { not: user.id }, ...LIVE_MEMBER_WHERE },
    }),
  ]);

  if (ownersLeft > 0) return { wouldStrand: false };
  // Exemption 2 — nobody left to strand.
  if (membersLeft === 0) return { wouldStrand: false };

  return { wouldStrand: true, reason: LAST_OWNER_REFUSAL, membersLeft };
}
