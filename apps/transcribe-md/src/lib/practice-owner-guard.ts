// ============================================================================
// ADMIN-5 — THE LAST-OWNER GUARD.
// ----------------------------------------------------------------------------
// Ruling #195 opened PROMOTION and left demotion and removal refused, because
// those are the half that can leave a practice with NOBODY able to administer
// it. This module is that half, and the whole of it.
//
// THE INTERLEAVING IT EXISTS TO SURVIVE, written down because it is invisible
// to every sequential test:
//
//   two owners demote each other at the same instant, `SELECT count(*) WHERE
//   practiceRole='OWNER'` returns 2 to BOTH, both conclude "there is another
//   owner", both write, and the practice is left with ZERO owners.
//
// That is not a window to narrow. A read-then-act check cannot see it BY
// CONSTRUCTION, which is why the ADMIN-5 row rules the guard's SHAPE rather
// than leaving it to whoever builds it.
//
// ⚠️ THE PROHIBITION IS HONOURED EXACTLY: nothing here reads a count and then
// acts on it. The count lives INSIDE the UPDATE's own WHERE clause, so the
// database evaluates the predicate and the write in one statement, and
// `rowsAffected === 0` IS the refusal. There is no arithmetic in TypeScript to
// get wrong.
//
// ⚠️ AND THE SHAPE IS A THIRD ONE, WHICH IS SURFACED RATHER THAN SUBSTITUTED IN
// SILENCE. The row permits "a PARTIAL UNIQUE INDEX or a SERIALIZABLE
// transaction". Measured on pg16, both options are defective for this
// invariant — the full matrix is in
// `docs/foundation/evidence/admin5-last-owner-guard-probes.md`:
//
//   * a partial unique index bounds a MAXIMUM; this invariant is a MINIMUM.
//     Applied naively it re-imposes one-owner-per-practice, which is exactly
//     the exclusivity #195 overturned. (Reached independently by two sessions.)
//   * SERIALIZABLE is correct but FALSELY ABORTS demotions in UNRELATED
//     practices, at every scale measured — because the supporting index is on
//     ("practiceId","practiceRole"), so ('PA','OWNER') and ('PB','OWNER') are
//     adjacent keys sharing a leaf page. Worse, the last-owner refusal then
//     arrives as a serialization failure, so the only honest first message is
//     "try again" and the doctor learns the real reason on the retry.
//
// So: a row lock on the practice, then one conditional statement. The lock is
// what makes the guard's own read authoritative; the conditional statement is
// what removes the arithmetic. The question "does the row's option set stand?"
// is the owner's, and it is asked in the PR rather than answered here.
// ============================================================================

import type { Prisma, PracticeRole } from '@prisma/client';

import prisma from '@meddoc/db';

import {
  CHANGE_ROLE_GUARDED_SQL,
  PRACTICE_LOCK_SQL,
  PROMOTE_SQL,
  REMOVE_MEMBER_GUARDED_SQL,
} from './practice-owner-guard-sql';

/**
 * ⚠️ EVERY WRITER THAT CAN MOVE A USER **OUT OF** `OWNER` MUST GO THROUGH THIS
 * MODULE. A pessimistic lock is only as good as its least disciplined writer,
 * and nothing in the type system enforces that — so `gate-admin5-owner-guard`
 * pins the set by name and reds when a new one appears.
 *
 * The obligation is deliberately NARROWER than "every `practiceRole` writer",
 * because narrower is what makes it enforceable. Seat redemption
 * (`signup-invite.ts` → `actions/auth.ts:599`) and the legacy app's
 * `activateUserAction` only ever ADD a member or fill a NULL role, so they can
 * only RAISE the owner count and cannot break "at least one owner". They are
 * outside this module on purpose, and the gate records why.
 */
export const DEMOTING_WRITERS = [
  'apps/transcribe-md/src/lib/practice-owner-guard.ts',
] as const;

export type OwnerGuardOutcome =
  /** The write landed. Exactly one row moved. */
  | { outcome: 'APPLIED'; from: PracticeRole | null }
  /** Refused by the database: this member is the practice's last owner. */
  | { outcome: 'LAST_OWNER' }
  /** The row is not in this practice, is already deactivated, or moved under
   *  us between the lock and the statement. Fail closed and say look again. */
  | { outcome: 'TARGET_MOVED' };

/** A transaction client and the full client share the parts we use. */
type Db = Prisma.TransactionClient;

/**
 * Take the practice's row lock, then run `fn`.
 *
 * ⚠️ THE LOCK IS ON `practices`, NOT ON `users`, AND THAT IS THE DESIGN. Two
 * admin actions in the SAME practice serialise on one row; two in DIFFERENT
 * practices never meet. Locking the user rows instead would serialise nothing
 * useful — the invariant is about the SET of owners, and the row that must not
 * be missed is the one the other actor is about to write.
 *
 * ⚠️ AND IT IS TAKEN BEFORE ANY READ THIS FUNCTION TRUSTS. A read taken before
 * the lock is a snapshot of a set somebody else is mid-way through changing.
 */
async function withPracticeLock<T>(
  practiceId: string,
  fn: (tx: Db) => Promise<T>,
): Promise<T> {
  return prisma.$transaction(async (tx) => {
    // ⚠️ THE STATEMENT COMES FROM `practice-owner-guard-sql`, NOT FROM HERE.
    // The E2E arm PREPAREs the same exported string and races it against a real
    // Postgres; a copy typed in this file would let the two drift and the proof
    // would stay green anyway.
    //
    // Parameterised — never interpolated. `practiceId` reaches here from a
    // session, but the discipline does not depend on where it came from.
    await tx.$queryRawUnsafe(PRACTICE_LOCK_SQL, practiceId);
    return fn(tx);
  });
}

/**
 * Why a write of zero rows happened. Called ONLY while the practice lock is
 * held, and only AFTER the conditional statement has already run — so this is
 * an explanation of a decision the database already made, never an input to
 * one. That distinction is the whole reason it is safe to read here at all.
 */
async function explainZero(
  tx: Db,
  practiceId: string,
  userId: string,
): Promise<'LAST_OWNER' | 'TARGET_MOVED'> {
  const target = await tx.user.findFirst({
    where: { id: userId, practiceId, deactivatedAt: null },
    select: { practiceRole: true },
  });
  if (!target) return 'TARGET_MOVED';
  if (target.practiceRole !== 'OWNER') return 'TARGET_MOVED';
  return 'LAST_OWNER';
}

/**
 * Move a member to `toRole`, refusing if that would remove the practice's last
 * owner.
 *
 * ⚠️ THE OWNER-COUNT CLAUSE IS OMITTED WHEN `toRole` IS `OWNER`, and that is a
 * decision about an INPUT, not about data. A lateral OWNER→OWNER cannot reduce
 * the owner count, so guarding it would refuse a move that is safe by
 * construction — and it would refuse it precisely when the practice has one
 * owner, which is the case a solo owner would meet first.
 */
export async function changeRoleGuarded(args: {
  practiceId: string;
  userId: string;
  toRole: PracticeRole;
}): Promise<OwnerGuardOutcome> {
  const { practiceId, userId, toRole } = args;

  return withPracticeLock(practiceId, async (tx) => {
    const before = await tx.user.findFirst({
      where: { id: userId, practiceId, deactivatedAt: null },
      select: { practiceRole: true },
    });

    // ⚠️ ONE STATEMENT. The count is a correlated subquery in the WHERE, so
    // Postgres evaluates "is there another owner?" and performs the write
    // atomically. `rowsAffected` is the answer, not a number we then reason
    // about. Both statements take the SAME parameter list, in the same order,
    // so choosing between them cannot also mis-order the arguments.
    const rows = await tx.$executeRawUnsafe(
      toRole === 'OWNER' ? PROMOTE_SQL : CHANGE_ROLE_GUARDED_SQL,
      userId,
      practiceId,
      toRole,
    );

    if (rows === 1) return { outcome: 'APPLIED', from: before?.practiceRole ?? null };
    return { outcome: await explainZero(tx, practiceId, userId) };
  });
}

/**
 * Remove a member from the practice.
 *
 * ⚠️ REMOVAL IS DEACTIVATION, AND THAT IS FORCED BY THE SCHEMA RATHER THAN
 * CHOSEN. `User.practiceId` is NOT NULL — "Every user belongs to exactly one
 * Practice" (`schema.prisma`) — so there is no such row as a user detached
 * from a practice. The alternative, re-homing them into a fresh synthetic
 * Practice, mints a practice per removal and is a different decision with
 * billing reach; it is filed, not taken.
 *
 * ⚠️ AND `practiceRole` GOES TO NULL, WHICH IS WHAT MAKES REMOVAL A DEMOTING
 * WRITER. `users_active_member_has_practice_role` is
 * `CHECK ("isActive" = false OR "practiceId" IS NULL OR "practiceRole" IS NOT
 * NULL)`, and the column's own doc says a deactivated account carries NULL
 * because "a deactivated account has no role in a practice, and a sentinel
 * there would be a claim nobody made". So removing the last owner destroys the
 * invariant exactly as demoting them does, and it takes the SAME guard. A
 * version of this that guarded only the role change would have left the second
 * door open.
 */
export async function removeMemberGuarded(args: {
  practiceId: string;
  userId: string;
  actorId: string;
}): Promise<OwnerGuardOutcome> {
  const { practiceId, userId, actorId } = args;

  return withPracticeLock(practiceId, async (tx) => {
    const before = await tx.user.findFirst({
      where: { id: userId, practiceId, deactivatedAt: null },
      select: { practiceRole: true },
    });

    const rows = await tx.$executeRawUnsafe(
      REMOVE_MEMBER_GUARDED_SQL,
      userId,
      practiceId,
      actorId,
    );

    if (rows === 1) return { outcome: 'APPLIED', from: before?.practiceRole ?? null };
    return { outcome: await explainZero(tx, practiceId, userId) };
  });
}
