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
import { PRACTICE_ADMIN_ROLE } from './practice-roles';

/**
 * The ONE definition of an active practice OWNER, as a Prisma filter.
 *
 * ⚠️ THE COLUMN LIST IS NOT ARBITRARY AND IT IS NOT `deactivatedAt` ALONE.
 * `users` carries five independent expressions of "no longer active", and the
 * choice among them changes the answer on real data. Measured on production
 * 2026-09-07, re-measured with a positive control under ruling #253: **ONE**
 * OWNER row passes `deactivatedAt IS NULL` while being unable to sign in, in
 * **ONE** practice — and that practice has ELEVEN members, two rows the loose
 * predicate counts as owners, and exactly ONE owner who can actually administer
 * it. A predicate that counts an owner who cannot authenticate implements a
 * proxy for the invariant, not the invariant.
 *
 * ⚠️ THIS SAID "SIX" UNTIL #253, AND SIX IS A DIFFERENT CLAIM'S NUMBER — it is
 * the count of zero-owner PRACTICES, and the two predicates agree on every one
 * of those. One eleven-member practice with a single able owner is the whole
 * case, and it is enough; quoting six weakened it.
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
 * #1026's clause counts `deactivatedAt IS NULL` alone, so ONE owner row counts
 * as an owner while unable to sign in — in the practice with ELEVEN members,
 * which reads two owners against ONE who can actually administer it. (This read
 * "SIX" until #253; see the correction above.)
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
/**
 * ⚠️ RESTORABLE, WHICH IS A DIFFERENT QUESTION FROM LIVE — ROUND FINDING 1.
 *
 * Exemption 2 asks "is anyone STRANDED if the last owner goes", and a SUSPENDED
 * member is not live and is very much stranded. Counting live members let two
 * ordinary admin clicks — suspend the only clinician, then soft-delete the only
 * owner — reach a practice with no active owner whose clinician can then NEVER
 * be unsuspended: `users_no_orphan_member` refuses it and names two remedies,
 * neither of which exists. `softDeletedAt` is written in one place and cleared
 * NOWHERE, and every role-writing door demands `practiceRole === 'OWNER'`, so an
 * ownerless practice cannot appoint one.
 *
 * A member is restorable when they are not soft-deleted: suspension and
 * deactivation have doors that clear them, soft-delete has none.
 */
export const RESTORABLE_MEMBER_WHERE = {
  softDeletedAt: null,
} as const;

/** The SAME predicate as raw SQL — see `liveMemberSql` for why this exists. */
export function restorableMemberSql(alias: string): string {
  return whereToSql(RESTORABLE_MEMBER_WHERE, alias);
}

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

/**
 * ⚠️ ITS OWN SENTENCE, BECAUSE THE SITUATION IS ITS OWN — the same reasoning as
 * #256. `LAST_OWNER_REFUSAL` says "transfer ownership to another member", and
 * here there is no member who can receive it: they are all suspended or
 * deactivated. Naming a remedy nobody can perform is the defect this whole file
 * calls worse than no refusal.
 */
export const STRANDS_RESTORABLE_REFUSAL =
  'This is the practice’s last active owner, and the remaining member(s) are ' +
  'suspended or deactivated. Restoring them afterwards would be refused, so ' +
  'reinstate a member and transfer ownership, or remove them, first.';

export const LAST_OWNER_REFUSAL =
  'This is the practice’s last active owner. Transfer ownership to another member first.';

/**
 * ⚠️ A THIRD SENTENCE, FOR THE THIRD SITUATION THE TRIGGER NAMES — #256's rule.
 * The trigger distinguishes a SOLE owner who is also the practice's only member
 * ("there is no one to transfer ownership to"). `LAST_OWNER_REFUSAL` would tell
 * that person to transfer ownership to somebody who does not exist, which is
 * the defect class this file calls worse than no refusal.
 */
export const SOLE_MEMBER_REFUSAL =
  'You are this practice’s only owner and its only member, so there is nobody to hand ' +
  'ownership to. Invite another member and make them an owner first.';

// ============================================================================
// ADMIN-5 — READING THE TRIGGER'S REFUSAL BACK AS A SENTENCE.
// ----------------------------------------------------------------------------
// ⚠️ THIS ENFORCES NOTHING EITHER. It runs AFTER the database has refused, and
// its only job is to turn that refusal into the same words the pre-check would
// have used — so a caller who lost a race is told the truth instead of "500".
//
// ⚠️ THE SHAPE IS MEASURED, NOT ASSUMED. Against a scratch pg16 with every
// migration applied, Prisma 7 + @prisma/adapter-pg surfaced EVERY one of the
// trigger's RAISEs — and a plain CHECK violation — as a `DriverAdapterError`
// with NO Prisma `P` code:
//
//   err.name                 'DriverAdapterError'
//   err.cause.originalCode   '23514'  (or '0A000' for the isolation refusal)
//   err.cause.originalMessage  the RAISE text, verbatim
//
// ⚠️ SO NEITHER THE CODE NOR THE PREFIX IS ENOUGH, AND BOTH ARE REQUIRED.
//   · `23514` is SHARED with every CHECK constraint on `users` — measured:
//     `users_active_member_has_practice_role` arrives with the identical code.
//   · `users_last_owner_guard:` prefixes FOUR different sentences, and two of
//     them (the isolation refusal and the orphan refusal) are NOT a last-owner
//     situation: telling an admin "transfer ownership" because a transaction
//     ran at the wrong isolation level names a remedy that fixes nothing.
// Each sentence is therefore matched on its DISTINCTIVE CLAUSE, together with
// the SQLSTATE the migration pairs it with. Anything else is `null`, and the
// caller rethrows — an unrecognised database error stays a 500, which is the
// honest answer to a question this file cannot read.
//
// `gate-admin5-last-owner-invariant.test.ts` feeds every RAISE format string
// in the migration through this function, so a reworded sentence reds here
// rather than silently degrading back to a 500.
// ============================================================================

export type GuardErrorClass =
  | {
      kind: 'LAST_OWNER';
      /** Which of the trigger's refusal situations this was. */
      variant: 'MEMBERS_REMAIN' | 'STRANDS_RESTORABLE' | 'SOLE_MEMBER';
      /** The doctor-facing sentence — one of this file's constants, never a new one. */
      reason: string;
      /** Other members the trigger counted as left behind (0 for the sole/stranded cases). */
      membersLeft: number;
    }
  | { kind: 'ISOLATION' }
  | { kind: 'ORPHAN' };

const RAISE_MEMBERS_REMAIN =
  /^users_last_owner_guard: refusing to leave practice .+ with zero active OWNERs while (\d+) other member\(s\) remain\. Transfer ownership first\.$/;
const RAISE_SOLE_MEMBER =
  /^users_last_owner_guard: refusing to leave practice .+ unadministered\. You are its only active OWNER and its only member, /;
const RAISE_ISOLATION =
  /^users_last_owner_guard: cannot enforce the last-owner invariant at isolation level /;
const RAISE_ORPHAN =
  /^users_last_owner_guard: refusing to place a live member in practice .+, which has no active OWNER\. /;

/** The SQLSTATE and the server's message, read STRUCTURALLY (not by `instanceof`
 *  — a driver error crossing a bundling boundary has the right shape and the
 *  wrong prototype; the sign route makes the same argument). */
function sqlStateAndMessage(err: unknown): { code: string | null; message: string | null } {
  if (err == null || typeof err !== 'object') return { code: null, message: null };
  const e = err as { message?: unknown; cause?: unknown };
  const cause = (e.cause && typeof e.cause === 'object' ? e.cause : {}) as {
    originalCode?: unknown;
    code?: unknown;
    originalMessage?: unknown;
    message?: unknown;
  };
  const code =
    typeof cause.originalCode === 'string'
      ? cause.originalCode
      : typeof cause.code === 'string'
        ? cause.code
        : null;
  const message =
    typeof cause.originalMessage === 'string'
      ? cause.originalMessage
      : typeof cause.message === 'string'
        ? cause.message
        : typeof e.message === 'string'
          ? e.message
          : null;
  return { code, message };
}

export function classifyGuardError(err: unknown): GuardErrorClass | null {
  const { code, message } = sqlStateAndMessage(err);
  if (code === null || message === null) return null;

  if (code === '0A000' && RAISE_ISOLATION.test(message)) return { kind: 'ISOLATION' };
  if (code !== '23514') return null;

  if (RAISE_ORPHAN.test(message)) return { kind: 'ORPHAN' };
  if (RAISE_SOLE_MEMBER.test(message)) {
    return { kind: 'LAST_OWNER', variant: 'SOLE_MEMBER', reason: SOLE_MEMBER_REFUSAL, membersLeft: 0 };
  }
  const m = RAISE_MEMBERS_REMAIN.exec(message);
  if (m) {
    const membersLeft = Number(m[1]);
    // ⚠️ ZERO IS THE TRIGGER'S "TRAPPED" BRANCH, NOT A TYPO. The RAISE is
    // reached with no live member left only when a RESTORABLE non-owner would
    // be stranded with no rescuer — the `STRANDS_RESTORABLE_REFUSAL` situation.
    // Telling that admin to "transfer ownership to another member" names a
    // member who cannot receive it.
    return membersLeft > 0
      ? { kind: 'LAST_OWNER', variant: 'MEMBERS_REMAIN', reason: LAST_OWNER_REFUSAL, membersLeft }
      : { kind: 'LAST_OWNER', variant: 'STRANDS_RESTORABLE', reason: STRANDS_RESTORABLE_REFUSAL, membersLeft: 0 };
  }
  return null;
}

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
/**
 * ⚠️ RULING #268 — TAKE THE PRACTICE LOCK **BEFORE** ANY USER-ROW WRITE.
 *
 * THE DEADLOCK THIS EXISTS FOR WAS MEASURED, 10 OF 10, AT THE **DEFAULT**
 * ISOLATION LEVEL, ON TWO WRITES THAT ARE BOTH ENTIRELY LEGAL. Practice with
 * three active owners; two admins each demote a different one; the invariant is
 * nowhere near being touched. Every trial, one of them died with
 * `ERROR: deadlock detected` and its demotion silently did not happen.
 *
 * THE CYCLE, because the fix only makes sense once it is written down:
 *
 *   T1  UPDATE user A      -> row lock A
 *       trigger fires      -> pg_advisory_xact_lock(guard, practice)   ACQUIRED
 *       guard counts       -> SELECT siblings ... FOR UPDATE           WANTS B
 *   T2  UPDATE user B      -> row lock B
 *       trigger fires      -> pg_advisory_xact_lock(guard, practice)   WANTS T1's
 *
 * T1 holds the advisory lock and wants row B; T2 holds row B and wants the
 * advisory lock. The observed error is `ShareLock on transaction` — a ROW wait,
 * not a lock-key wait — which is what pins this shape rather than a guess.
 *
 * ⚠️ **NO TRIGGER-SIDE FIX CAN CLOSE IT, AND THAT IS THE WHOLE POINT.** By the
 * time the trigger runs, its transaction is ALREADY holding a row lock it did
 * not choose the order of. The lock must be taken before the statement, which
 * only the caller can do. Widening the trigger, reordering its counts, or
 * changing its lock strength all leave the row lock exactly where it was.
 *
 * ⚠️ **THE TRIGGER KEEPS ITS OWN LOCK.** This helper is application code, and
 * the next writer somebody adds will not call it — the same argument this
 * file's header already makes about enforcement. Same key
 * (`hashtext('users_last_owner_guard')`, `hashtext(practiceId)`), same session,
 * so the trigger's acquisition is a re-entry and not a second lock: Postgres
 * advisory locks are re-entrant within a session and `pg_advisory_xact_lock`
 * releases on COMMIT or ROLLBACK whatever the nesting depth.
 *
 * ⚠️ **AND IT ASSERTS `READ COMMITTED` — RULING #269.** The guard cannot be
 * correct above it: a snapshot taken before the lock never refreshes, so a
 * transaction waits its turn correctly and then counts owners on a view of the
 * world from before the other writer committed. No amount of locking repairs a
 * stale snapshot, so the honest thing is to refuse rather than to serialize
 * something into a wrong answer. The trigger refuses too; this is the friendly
 * half, and it names the level it saw.
 */
export const PRACTICE_LOCK_KEY = 'users_last_owner_guard';

export class IsolationLevelUnsupportedError extends Error {
  constructor(public readonly level: string) {
    super(
      `The last-owner guard requires READ COMMITTED and this transaction is ${level}. ` +
        'A snapshot taken before the practice lock never refreshes, so the owner count ' +
        'would be read from before the competing write committed.'
    );
    this.name = 'IsolationLevelUnsupportedError';
  }
}

export async function withPracticeLock<T>(
  tx: {
    $queryRaw: <R = unknown>(q: TemplateStringsArray, ...v: unknown[]) => Promise<R>;
    $executeRaw: (q: TemplateStringsArray, ...v: unknown[]) => Promise<number>;
  },
  practiceId: string,
  write: () => Promise<T>,
): Promise<T> {
  // ⚠️ THE ASSERTION COMES FIRST, AND IT IS NOT A FORMALITY. Taking the lock
  // inside a REPEATABLE READ transaction would produce the most expensive
  // outcome available here: a write that waits politely, passes every guard,
  // and commits the forbidden state. Refusing before the lock means the
  // transaction has changed nothing when it aborts.
  const [{ level }] = await tx.$queryRaw<{ level: string }[]>`
    SELECT current_setting('transaction_isolation') AS level`;
  if (level.toLowerCase() !== 'read committed') {
    throw new IsolationLevelUnsupportedError(level);
  }

  // ⚠️ THE KEY PAIR IS THE TRIGGER'S, COMPUTED BY POSTGRES' OWN `hashtext` —
  // never re-implemented here. A second hash function is a second reader of the
  // rule, and the two would take DIFFERENT locks while looking identical,
  // which is precisely the failure this helper exists to end.
  //
  // ⚠️ `$executeRaw`, NOT `$queryRaw`, AND THE FIRST VERSION OF THIS GOT IT
  // WRONG. `pg_advisory_xact_lock` returns **`void`** — asserted from
  // `pg_get_function_result`, not assumed — and `$queryRaw` has to DESERIALIZE
  // the row it gets back. It cannot deserialize a void column, so the call
  // throws and the route answers 500. Every unit arm passed because they mock
  // the client; the e2e caught it against a real database, on the ordinary
  // suspend of a solo owner.
  //
  // The repository already had the answer one package over:
  // `billing-charge.ts:453` takes its advisory lock with `$executeRaw*` for
  // exactly this reason. A statement whose result you do not read is an
  // EXECUTE, not a QUERY.
  await tx.$executeRaw`
    SELECT pg_advisory_xact_lock(hashtext(${PRACTICE_LOCK_KEY}), hashtext(${practiceId}))`;

  return write();
}

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

  // ⚠️ EXEMPTION 2, NARROWED TO MATCH THE TRIGGER — ROUND FINDING 1.
  // "Nobody left to strand" now means nobody RESTORABLE. Two halves, because
  // they cancel: a restorable NON-owner is a person locked out for good (the
  // orphan arm will not make them live again), while a restorable OWNER is a
  // rescuer — that arm short-circuits on `users_is_active_owner`, so restoring
  // one is allowed and puts the practice back on its feet.
  if (membersLeft === 0) {
    const [trappedLeft, rescuerLeft] = await Promise.all([
      prisma.user.count({
        where: {
          practiceId: user.practiceId,
          id: { not: user.id },
          practiceRole: { not: PRACTICE_ADMIN_ROLE },
          ...RESTORABLE_MEMBER_WHERE,
        },
      }),
      prisma.user.count({
        where: {
          practiceId: user.practiceId,
          id: { not: user.id },
          practiceRole: PRACTICE_ADMIN_ROLE,
          ...RESTORABLE_MEMBER_WHERE,
        },
      }),
    ]);
    if (trappedLeft > 0 && rescuerLeft === 0) {
      return { wouldStrand: true, reason: STRANDS_RESTORABLE_REFUSAL, membersLeft: trappedLeft };
    }
    return { wouldStrand: false };
  }

  return { wouldStrand: true, reason: LAST_OWNER_REFUSAL, membersLeft };
}
