'use server';

// ============================================================================
// ADMIN-1 — SEAT MINTING AND MEMBER ROLES.
// ----------------------------------------------------------------------------
// The two gaps the row names, and nothing else. Role enforcement across the
// other 48 mutating surfaces is RULED AGAINST, not missing — signing is the
// sole role-gated action, techs prepare and deliver. Administration is a third
// axis and this file is the whole of it.
// ============================================================================

import { randomUUID } from 'node:crypto';

import type { PracticeRole } from '@prisma/client';
import { revalidatePath } from 'next/cache';
import { z } from 'zod';

import prisma from '@meddoc/db';

import { logAudit } from '@/lib/audit';
import { getSession } from '@/lib/auth';
import {
  ADMIN_REFUSAL_MESSAGE,
  ASSIGNABLE_ROLES,
  generateInviteCode,
  requirePracticeAdmin,
  type AdminRefusal,
} from '@/lib/practice-admin';
import { LEAVE_PRACTICE, PRACTICE_ADMIN_ROLE, isStepDownOption } from '@/lib/practice-roles';
import { hashInviteCode, normalizeInviteCode } from '@/lib/signup-invite';
import {
  ACTIVE_OWNER_WHERE,
  LIVE_MEMBER_WHERE,
  classifyGuardError,
  withPracticeLock,
} from '@/lib/last-owner-invariant';

const MEMBERS_PATH = '/settings/members';

export type SeatState =
  /** ⚠️ THE RAW CODE IS RETURNED EXACTLY ONCE AND NEVER STORED. The row keeps
   *  only a SHA-256, so this value cannot be recovered from the database — the
   *  same discipline AuthToken uses. If the owner loses it, they mint another. */
  | { ok: true; code: string; role: string; expiresAt: string | null }
  | { ok: false; reason: AdminRefusal | 'INVALID'; message: string }
  | null;

export type RoleState =
  | { ok: true; changedAt: number }
  | { ok: false; reason: AdminRefusal | 'INVALID'; message: string }
  | null;

const MintSchema = z.object({
  role: z.enum(ASSIGNABLE_ROLES),
  // Operational, never clinical. The invite table is outside the clinical
  // retention rules, which is exactly why it must never carry PHI.
  label: z.string().trim().min(1, 'Give the seat a label').max(120),
  expiresInDays: z.coerce.number().int().min(1).max(90).optional(),
});

const RoleSchema = z.object({
  userId: z.string().trim().min(1),
  role: z.enum(ASSIGNABLE_ROLES),
});

const TargetSchema = z.object({ userId: z.string().trim().min(1) });

type AdminAct = 'ROLE_CHANGE' | 'REMOVE' | 'TRANSFER';

/**
 * ⚠️ EVERY REFUSAL ON THESE DOORS IS RECORDED, as `requirePracticeAdmin`'s are:
 * a gate nothing records is one path away from not existing. Structured only —
 * the refusal, the act, the practice. Never a name.
 */
async function recordRefusal(
  targetId: string,
  practiceId: string,
  refusal: AdminRefusal,
  attempted: AdminAct,
  extra: Record<string, unknown> = {},
): Promise<void> {
  await logAudit({
    action: 'PRACTICE_ADMIN_REFUSED',
    targetType: 'User',
    targetId,
    metadata: { refusal, attempted, practiceId, ...extra },
  });
}

/** ⚠️ NOT EXPORTED — a `'use server'` file may export async functions only. */
class StepDownMissed extends Error {}

/** ⚠️ THE SAME REFUSAL THE SHIPPED SCRIPT MAKES, AND FOR THE SAME REASON: a
 *  label is free text an operator types, and free text next to a clinical
 *  system is where an identifier ends up. */
const SSN_SHAPED = /\b\d{3}-?\d{2}-?\d{4}\b/;

export async function mintSeatInviteAction(
  _prev: SeatState,
  formData: FormData,
): Promise<SeatState> {
  const guard = await requirePracticeAdmin(await getSession());
  if (!guard.ok) return { ok: false, reason: guard.reason, message: guard.message };

  const parsed = MintSchema.safeParse({
    role: formData.get('role'),
    label: formData.get('label'),
    expiresInDays: formData.get('expiresInDays') || undefined,
  });
  if (!parsed.success) {
    return {
      ok: false,
      reason: 'INVALID',
      message: parsed.error.issues[0]?.message ?? 'Check the form and try again.',
    };
  }
  if (SSN_SHAPED.test(parsed.data.label)) {
    return {
      ok: false,
      reason: 'INVALID',
      message: 'That label looks like it contains an SSN. Use a name or a role.',
    };
  }

  const raw = generateInviteCode();
  const expiresAt = parsed.data.expiresInDays
    ? new Date(Date.now() + parsed.data.expiresInDays * 86_400_000)
    : null;

  const row = await prisma.inviteCode.create({
    data: {
      codeHash: hashInviteCode(raw),
      label: parsed.data.label,
      // ⚠️ ONE USE. A seat is a person. `maxUses > 1` is the shared
      // pilot-cohort shape and belongs to the operator script, not here — a
      // reusable code handed to one hire admits everyone they forward it to.
      maxUses: 1,
      expiresAt,
      // ⚠️ BOTH, OR THE DATABASE REFUSES. The CHECK pairing practiceId with
      // practiceRole is what stops an invite silently minting an OWNER of
      // somebody else's clinic.
      practiceId: guard.practiceId,
      practiceRole: parsed.data.role,
    },
    select: { id: true },
  });

  await logAudit({
    action: 'PRACTICE_SEAT_INVITED',
    targetType: 'InviteCode',
    targetId: row.id,
    // ⚠️ NEVER THE RAW CODE, and never the hash either — an audit row that
    // carries the hash lets a database read mint signups, which is the exact
    // property `codeHash` exists to deny.
    metadata: {
      practiceRole: parsed.data.role,
      practiceId: guard.practiceId,
      expiresAt: expiresAt?.toISOString() ?? null,
    },
  });

  revalidatePath(MEMBERS_PATH);
  return {
    ok: true,
    code: normalizeInviteCode(raw),
    role: parsed.data.role,
    expiresAt: expiresAt?.toISOString() ?? null,
  };
}

export async function changeMemberRoleAction(
  _prev: RoleState,
  formData: FormData,
): Promise<RoleState> {
  const guard = await requirePracticeAdmin(await getSession());
  if (!guard.ok) return { ok: false, reason: guard.reason, message: guard.message };

  const parsed = RoleSchema.safeParse({
    userId: formData.get('userId'),
    role: formData.get('role'),
  });
  if (!parsed.success) {
    return { ok: false, reason: 'ROLE_NOT_ASSIGNABLE', message: ADMIN_REFUSAL_MESSAGE.ROLE_NOT_ASSIGNABLE };
  }

  // ⚠️ THE SELF-DEMOTION GUARD, AND IT IS CHECKED BEFORE THE READ. An owner
  // demoting themselves is the one move that can leave a practice with nobody
  // able to administer it, and it is also the easiest misclick on the page.
  if (parsed.data.userId === guard.actorId) {
    return {
      ok: false,
      reason: 'CANNOT_CHANGE_OWN_ROLE',
      message: ADMIN_REFUSAL_MESSAGE.CANNOT_CHANGE_OWN_ROLE,
    };
  }

  const target = await prisma.user.findFirst({
    // ⚠️ SCOPED IN THE QUERY, NOT AFTER IT. `findUnique` by id and then
    // comparing practiceId in JS is the same check written so that forgetting
    // one line reads any user in the system.
    //
    // ⚠️ AND `deactivatedAt: null` IS A CONJUNCT HERE FOR THE SAME REASON THE
    // LISTING HAS IT. A deactivated (or, since ADMIN-5, REMOVED) member keeps
    // their `practiceId`, so the row is still findable by id+practice. Without
    // this conjunct the action could write a role onto somebody
    // `listPracticeMembers` does not render — an invisible owner.
    where: { id: parsed.data.userId, practiceId: guard.practiceId, deactivatedAt: null },
    select: { id: true, practiceRole: true },
  });
  if (!target) {
    return {
      ok: false,
      reason: 'TARGET_NOT_IN_PRACTICE',
      message: ADMIN_REFUSAL_MESSAGE.TARGET_NOT_IN_PRACTICE,
    };
  }

  // ⚠️ ADMIN-5 — AN OWNER IS EDITABLE NOW, AND THE INVARIANT MOVED RATHER THAN
  // LAPSED. Until this change `CANNOT_CHANGE_AN_OWNER` refused every change to
  // an owner unconditionally, and that refusal is what made "a practice always
  // has at least one owner" hold STRUCTURALLY. Opening demotion destroys that,
  // so the guarantee is now the DATABASE's: `users_last_owner_guard` (ruling
  // #210) refuses any write that would leave a practice with members and no
  // active owner. It is the ONLY enforcer (#310(a), "one predicate per rule") —
  // there is deliberately no second count here, and no pre-check either,
  // because the actor re-check below already guarantees an active owner
  // survives this write: the actor themselves.
  //
  // ⚠️ THE COMPARE-AND-SET BELOW STAYS, for the reason it was added (#195's
  // pass): this read is a snapshot, and a concurrent promotion can move the row
  // between here and the write. Count 0 means it moved, and we refuse.

  if (target.practiceRole === parsed.data.role) {
    // A no-op writes no row. An append-only trail that records changes which
    // did not happen is worse than one that misses none.
    return { ok: true, changedAt: Date.now() };
  }

  // ⚠️ COMPARE-AND-SET ON THE EXACT ROLE THAT WAS READ — one statement, no
  // transaction, no isolation-level dependency. `updateMany` takes a full
  // predicate where `update` takes only a unique key, and re-asserting
  // `practiceRole: target.practiceRole` in the WHERE is what makes the write
  // conditional on nothing having moved underneath it.
  //
  // ⚠️ AND IT IS ALSO WHAT MAKES THE AUDIT ROW TRUE. `from` is read from the
  // snapshot; if the row had changed under us, `from` would name a value the
  // row did not hold when the UPDATE ran — a false entry in an append-only
  // trail, which is worse than a missing one. Count 0 means the row moved, so
  // we refuse rather than write, and the trail says nothing rather than
  // something wrong.
  // ⚠️ RULING #268 — THE PRACTICE LOCK IS TAKEN BEFORE THE UPDATE, NOT BY THE
  // TRIGGER AFTERWARDS. Two admins demoting two DIFFERENT owners of the same
  // practice deadlocked 10 of 10 at the default isolation level, because each
  // held its own row lock before the trigger could reach for the shared one.
  // Taking it here means the second writer blocks on the LOCK, before it has
  // taken any row lock at all, so there is no cycle to detect.
  //
  // ⚠️ THE COMPARE-AND-SET BELOW IS UNCHANGED AND STILL LOAD-BEARING. The lock
  // orders the writers; the `practiceRole` in the WHERE is what makes the write
  // conditional on nothing having moved. A lock is not a substitute for it —
  // the row can still have changed before this transaction started.
  let outcome: 'WROTE' | 'MOVED' | 'ACTOR';
  try {
    outcome = await prisma.$transaction((tx) =>
      withPracticeLock(tx, guard.practiceId, async () => {
        // ⚠️ ADMIN-5 — THE ACTOR IS RE-READ UNDER THE LOCK, WITH THE ONE
        // PREDICATE. `requirePracticeAdmin` ran BEFORE the lock and checks the
        // role column only. Two owners demoting each other both pass it; the
        // lock serializes them, and without this re-read the second acts on
        // authority the first has just taken away. `ACTIVE_OWNER_WHERE` — never
        // a restated predicate — is what "may administer" means in this file.
        const actor = await tx.user.findFirst({
          where: { id: guard.actorId, practiceId: guard.practiceId, ...ACTIVE_OWNER_WHERE },
          select: { id: true },
        });
        if (!actor) return 'ACTOR' as const;
        const r = await tx.user.updateMany({
          where: {
            id: target.id,
            practiceId: guard.practiceId,
            deactivatedAt: null,
            practiceRole: target.practiceRole,
          },
          data: { practiceRole: parsed.data.role },
        });
        return r.count === 0 ? ('MOVED' as const) : ('WROTE' as const);
      }),
    );
  } catch (err) {
    // ⚠️ THE DATABASE REFUSED — MAP IT TO THE SENTENCE, NEVER AROUND IT.
    // Only a last-owner refusal is spoken; anything else is rethrown, because
    // this door cannot honestly name a remedy for an error it cannot read.
    const refusal = classifyGuardError(err);
    if (refusal?.kind !== 'LAST_OWNER') throw err;
    await recordRefusal(target.id, guard.practiceId, 'LAST_OWNER', 'ROLE_CHANGE', {
      to: parsed.data.role,
      source: 'trigger',
      variant: refusal.variant,
    });
    return { ok: false, reason: 'LAST_OWNER', message: refusal.reason };
  }

  if (outcome === 'ACTOR') {
    await recordRefusal(target.id, guard.practiceId, 'ROLE_MAY_NOT_ADMINISTER', 'ROLE_CHANGE', {
      recheckedUnderLock: true,
    });
    return {
      ok: false,
      reason: 'ROLE_MAY_NOT_ADMINISTER',
      message: ADMIN_REFUSAL_MESSAGE.ROLE_MAY_NOT_ADMINISTER,
    };
  }

  if (outcome === 'MOVED') {
    // The row changed between the read and the write. We cannot know it is
    // still safe to demote, so we refuse — fail-closed, and the doctor is told
    // to look again rather than being shown a success that did not happen.
    return {
      ok: false,
      reason: 'ROLE_CHANGED_UNDER_YOU',
      message: ADMIN_REFUSAL_MESSAGE.ROLE_CHANGED_UNDER_YOU,
    };
  }

  await logAudit({
    action: 'PRACTICE_ROLE_CHANGED',
    targetType: 'User',
    targetId: target.id,
    metadata: {
      from: target.practiceRole ?? null,
      to: parsed.data.role,
      practiceId: guard.practiceId,
    },
  });

  revalidatePath(MEMBERS_PATH);
  return { ok: true, changedAt: Date.now() };
}

// ============================================================================
// ADMIN-5 — REMOVING A MEMBER FROM THE PRACTICE.
// ----------------------------------------------------------------------------
// Removal is DEACTIVATION WITH A PRACTICE ACTOR: `isActive=false`,
// `deactivatedAt`, `deactivatedBy`, `forceLogoutAt` (so a live session dies on
// its next request) and `practiceRole = NULL` — the column's own doc requires
// it of a deactivated row ("a deactivated account has no role in a practice,
// and a sentinel there would be a claim nobody made"). The role they held is
// kept in the audit row instead, captured under the lock.
//
// ⚠️ NOTHING IS DELETED. Their visits, patients and audit history stay exactly
// where they are: the chart belongs to the practice, not to the person.
//
// ⚠️ THE SAME DATABASE GUARD AS DEMOTION, BECAUSE IT IS THE SAME INVARIANT.
// Removing the last owner strands a practice exactly as demoting them does.
// ============================================================================
export async function removeMemberAction(
  _prev: RoleState,
  formData: FormData,
): Promise<RoleState> {
  const guard = await requirePracticeAdmin(await getSession());
  if (!guard.ok) return { ok: false, reason: guard.reason, message: guard.message };

  const parsed = TargetSchema.safeParse({ userId: formData.get('userId') });
  if (!parsed.success) {
    return {
      ok: false,
      reason: 'TARGET_NOT_IN_PRACTICE',
      message: ADMIN_REFUSAL_MESSAGE.TARGET_NOT_IN_PRACTICE,
    };
  }

  // ⚠️ SELF-REMOVAL IS REFUSED, BEFORE ANY READ. It has its own words because a
  // doctor who clicked "Remove" needs to be told about removal, and because the
  // last-owner guard would NOT catch it: in a two-owner practice either owner
  // could remove themselves, and then the other. Leaving is ADMIN-5a's
  // transfer, which hands the practice on in the same transaction.
  if (parsed.data.userId === guard.actorId) {
    return {
      ok: false,
      reason: 'CANNOT_REMOVE_YOURSELF',
      message: ADMIN_REFUSAL_MESSAGE.CANNOT_REMOVE_YOURSELF,
    };
  }

  type Removal =
    | { outcome: 'WROTE'; removedRole: PracticeRole | null }
    | { outcome: 'ACTOR' }
    | { outcome: 'NOT_FOUND' }
    | { outcome: 'MOVED' };

  let result: Removal;
  try {
    result = await prisma.$transaction((tx) =>
      withPracticeLock(tx, guard.practiceId, async (): Promise<Removal> => {
        // ⚠️ THE ACTOR, RE-READ UNDER THE LOCK — AND FOR REMOVAL IT IS THE ONLY
        // THING STANDING BETWEEN TWO OWNERS AND AN EMPTY PRACTICE. Two owners
        // of a practice with no other live member remove each other: both pass
        // `requirePracticeAdmin`, the lock serializes them, the first removal
        // commits, and the second — removing the LAST active owner — is
        // ALLOWED by the trigger's exemption 2, because the first victim's row
        // is now inactive with a NULL role and counts as neither a member nor
        // a rescuer. The practice ends with no live user at all. Re-reading the
        // actor here refuses the second removal: its actor was just removed.
        const actor = await tx.user.findFirst({
          where: { id: guard.actorId, practiceId: guard.practiceId, ...ACTIVE_OWNER_WHERE },
          select: { id: true },
        });
        if (!actor) return { outcome: 'ACTOR' };

        // ⚠️ READ UNDER THE LOCK, so `removedRole` names what the row held when
        // it was written, not what a pre-lock snapshot said.
        const target = await tx.user.findFirst({
          where: { id: parsed.data.userId, practiceId: guard.practiceId, deactivatedAt: null },
          select: { id: true, practiceRole: true },
        });
        if (!target) return { outcome: 'NOT_FOUND' };

        const now = new Date();
        const r = await tx.user.updateMany({
          // ⚠️ COMPARE-AND-SET on the role just read — a writer that does not
          // take the lock can still move the row, and the audit row must not
          // name a role the row did not hold.
          where: {
            id: target.id,
            practiceId: guard.practiceId,
            deactivatedAt: null,
            practiceRole: target.practiceRole,
          },
          data: {
            isActive: false,
            deactivatedAt: now,
            deactivatedBy: guard.actorId,
            practiceRole: null,
            forceLogoutAt: now,
          },
        });
        return r.count === 0
          ? { outcome: 'MOVED' }
          : { outcome: 'WROTE', removedRole: target.practiceRole };
      }),
    );
  } catch (err) {
    const refusal = classifyGuardError(err);
    if (refusal?.kind !== 'LAST_OWNER') throw err;
    await recordRefusal(parsed.data.userId, guard.practiceId, 'LAST_OWNER', 'REMOVE', {
      source: 'trigger',
      variant: refusal.variant,
    });
    return { ok: false, reason: 'LAST_OWNER', message: refusal.reason };
  }

  if (result.outcome === 'ACTOR') {
    await recordRefusal(parsed.data.userId, guard.practiceId, 'ROLE_MAY_NOT_ADMINISTER', 'REMOVE', {
      recheckedUnderLock: true,
    });
    return {
      ok: false,
      reason: 'ROLE_MAY_NOT_ADMINISTER',
      message: ADMIN_REFUSAL_MESSAGE.ROLE_MAY_NOT_ADMINISTER,
    };
  }
  if (result.outcome === 'NOT_FOUND') {
    return {
      ok: false,
      reason: 'TARGET_NOT_IN_PRACTICE',
      message: ADMIN_REFUSAL_MESSAGE.TARGET_NOT_IN_PRACTICE,
    };
  }
  if (result.outcome === 'MOVED') {
    return {
      ok: false,
      reason: 'ROLE_CHANGED_UNDER_YOU',
      message: ADMIN_REFUSAL_MESSAGE.ROLE_CHANGED_UNDER_YOU,
    };
  }

  await logAudit({
    // ⚠️ ITS OWN LABEL, NOT `USER_DEACTIVATED` — same mechanism, different act
    // and actor. See the migration `20260910120000_admin5_practice_member_removed`.
    action: 'PRACTICE_MEMBER_REMOVED',
    targetType: 'User',
    targetId: parsed.data.userId,
    metadata: {
      // The row no longer carries the role; this entry is the only record of
      // what was removed.
      removedRole: result.removedRole ?? null,
      practiceId: guard.practiceId,
    },
  });

  revalidatePath(MEMBERS_PATH);
  return { ok: true, changedAt: Date.now() };
}

// ============================================================================
// ADMIN-5a — A DEPARTING OWNER HANDS THE PRACTICE ON, ATOMICALLY.
// ----------------------------------------------------------------------------
// Every door refuses self-action by design, which is right for demotion and
// leaves "a partner is leaving" with no door at all. This is that door: ONE
// transaction, under the practice lock, that promotes a named live member to
// OWNER and THEN steps the actor down (to CLINICIAN/TECH) or out (LEAVE).
//
// ⚠️ THE ORDER IS LOAD-BEARING, AND GETTING IT BACKWARDS FAILS CLOSED. The
// trigger is a constraint trigger `DEFERRABLE INITIALLY IMMEDIATE`, so it judges
// each statement on the state that statement produced: step-down-first, by a
// sole owner, reads zero owners left and is REFUSED. Promote-first means the
// step-down statement already sees the new owner. No count is read here.
// ============================================================================
export async function transferOwnershipAction(
  _prev: RoleState,
  formData: FormData,
): Promise<RoleState> {
  const guard = await requirePracticeAdmin(await getSession());
  if (!guard.ok) return { ok: false, reason: guard.reason, message: guard.message };

  const then = formData.get('then');
  if (!isStepDownOption(then)) {
    return { ok: false, reason: 'ROLE_NOT_ASSIGNABLE', message: ADMIN_REFUSAL_MESSAGE.ROLE_NOT_ASSIGNABLE };
  }
  const parsed = TargetSchema.safeParse({ userId: formData.get('userId') });
  if (!parsed.success || parsed.data.userId === guard.actorId) {
    return {
      ok: false,
      reason: 'TRANSFER_TARGET_INVALID',
      message: ADMIN_REFUSAL_MESSAGE.TRANSFER_TARGET_INVALID,
    };
  }
  const toUserId = parsed.data.userId;
  // ⚠️ ONE ID FOR THE WHOLE ACT, so the two or three audit rows it writes can be
  // read back as one event rather than as unrelated role changes.
  const transferId = randomUUID();

  type Transfer =
    | { outcome: 'WROTE'; promotedFrom: PracticeRole | null }
    | { outcome: 'ACTOR' }
    | { outcome: 'TARGET' }
    | { outcome: 'MOVED' };

  let result: Transfer;
  try {
    result = await prisma.$transaction((tx) =>
      withPracticeLock(tx, guard.practiceId, async (): Promise<Transfer> => {
        const actor = await tx.user.findFirst({
          where: { id: guard.actorId, practiceId: guard.practiceId, ...ACTIVE_OWNER_WHERE },
          select: { id: true },
        });
        if (!actor) return { outcome: 'ACTOR' };

        // ⚠️ THE INCOMING OWNER MUST BE A LIVE MEMBER. `LIVE_MEMBER_WHERE` plus
        // `practiceRole = OWNER` is exactly `ACTIVE_OWNER_WHERE`, so the person
        // handed the practice is guaranteed able to administer it. A suspended
        // or soft-deleted member would be an owner nobody can sign in as.
        const target = await tx.user.findFirst({
          where: { id: toUserId, practiceId: guard.practiceId, ...LIVE_MEMBER_WHERE },
          select: { id: true, practiceRole: true },
        });
        if (!target) return { outcome: 'TARGET' };

        // STATEMENT 1 — the incoming owner. Skipped when they already are one:
        // handing over to a co-owner and stepping down is a legitimate transfer.
        let promotedFrom: PracticeRole | null = null;
        if (target.practiceRole !== PRACTICE_ADMIN_ROLE) {
          const promoted = await tx.user.updateMany({
            where: {
              id: target.id,
              practiceId: guard.practiceId,
              ...LIVE_MEMBER_WHERE,
              practiceRole: target.practiceRole,
            },
            data: { practiceRole: PRACTICE_ADMIN_ROLE },
          });
          if (promoted.count === 0) return { outcome: 'MOVED' };
          promotedFrom = target.practiceRole;
        }

        // STATEMENT 2 — the outgoing owner, AFTER statement 1. See the header.
        const now = new Date();
        const steppedDown = await tx.user.updateMany({
          where: { id: guard.actorId, practiceId: guard.practiceId, ...ACTIVE_OWNER_WHERE },
          data:
            then === LEAVE_PRACTICE
              ? {
                  isActive: false,
                  deactivatedAt: now,
                  deactivatedBy: guard.actorId,
                  practiceRole: null,
                  forceLogoutAt: now,
                }
              : { practiceRole: then },
        });
        // ⚠️ THROW, NEVER RETURN. Statement 1 has already written; returning
        // here would COMMIT a promotion without the step-down it was paired
        // with. Throwing rolls both back.
        if (steppedDown.count === 0) throw new StepDownMissed();
        return { outcome: 'WROTE', promotedFrom };
      }),
    );
  } catch (err) {
    if (err instanceof StepDownMissed) {
      return {
        ok: false,
        reason: 'ROLE_CHANGED_UNDER_YOU',
        message: ADMIN_REFUSAL_MESSAGE.ROLE_CHANGED_UNDER_YOU,
      };
    }
    const refusal = classifyGuardError(err);
    if (refusal?.kind !== 'LAST_OWNER') throw err;
    await recordRefusal(toUserId, guard.practiceId, 'LAST_OWNER', 'TRANSFER', {
      then,
      source: 'trigger',
      variant: refusal.variant,
      transferId,
    });
    return { ok: false, reason: 'LAST_OWNER', message: refusal.reason };
  }

  if (result.outcome === 'ACTOR') {
    await recordRefusal(toUserId, guard.practiceId, 'ROLE_MAY_NOT_ADMINISTER', 'TRANSFER', {
      recheckedUnderLock: true,
    });
    return {
      ok: false,
      reason: 'ROLE_MAY_NOT_ADMINISTER',
      message: ADMIN_REFUSAL_MESSAGE.ROLE_MAY_NOT_ADMINISTER,
    };
  }
  if (result.outcome === 'TARGET') {
    return {
      ok: false,
      reason: 'TRANSFER_TARGET_INVALID',
      message: ADMIN_REFUSAL_MESSAGE.TRANSFER_TARGET_INVALID,
    };
  }
  if (result.outcome === 'MOVED') {
    return {
      ok: false,
      reason: 'ROLE_CHANGED_UNDER_YOU',
      message: ADMIN_REFUSAL_MESSAGE.ROLE_CHANGED_UNDER_YOU,
    };
  }

  // ⚠️ WRITTEN AFTER COMMIT, and only for what actually changed: a target who
  // was already an owner gets no promotion row.
  if (result.promotedFrom !== null) {
    await logAudit({
      action: 'PRACTICE_ROLE_CHANGED',
      targetType: 'User',
      targetId: toUserId,
      metadata: { from: result.promotedFrom, to: PRACTICE_ADMIN_ROLE, practiceId: guard.practiceId, transferId },
    });
  }
  if (then === LEAVE_PRACTICE) {
    await logAudit({
      action: 'PRACTICE_MEMBER_REMOVED',
      targetType: 'User',
      targetId: guard.actorId,
      metadata: { removedRole: PRACTICE_ADMIN_ROLE, practiceId: guard.practiceId, transferId, via: 'TRANSFER' },
    });
  } else {
    await logAudit({
      action: 'PRACTICE_ROLE_CHANGED',
      targetType: 'User',
      targetId: guard.actorId,
      metadata: { from: PRACTICE_ADMIN_ROLE, to: then, practiceId: guard.practiceId, transferId },
    });
  }

  revalidatePath(MEMBERS_PATH);
  return { ok: true, changedAt: Date.now() };
}

export async function revokeSeatInviteAction(
  _prev: RoleState,
  formData: FormData,
): Promise<RoleState> {
  const guard = await requirePracticeAdmin(await getSession());
  if (!guard.ok) return { ok: false, reason: guard.reason, message: guard.message };

  const id = String(formData.get('inviteId') ?? '').trim();
  if (!id) {
    return { ok: false, reason: 'INVALID', message: 'That invite no longer exists.' };
  }

  // ⚠️ REVOKE, NEVER DELETE. `revokedAt` exists precisely so the audit trail of
  // a code's use survives its withdrawal — the schema says so in its own words.
  // Scoped by practice in the WHERE, so an id from another clinic updates zero
  // rows rather than one.
  const { count } = await prisma.inviteCode.updateMany({
    where: { id, practiceId: guard.practiceId, revokedAt: null },
    data: { revokedAt: new Date() },
  });
  if (count === 0) {
    return {
      ok: false,
      reason: 'TARGET_NOT_IN_PRACTICE',
      message: 'That invite is not yours, or was already revoked.',
    };
  }

  await logAudit({
    action: 'PRACTICE_SEAT_INVITED',
    targetType: 'InviteCode',
    targetId: id,
    // Same label, `revoked: true` — the seat's lifecycle is one story, and a
    // second enum value for the withdrawal would split it across two.
    metadata: { revoked: true, practiceId: guard.practiceId },
  });

  revalidatePath(MEMBERS_PATH);
  return { ok: true, changedAt: Date.now() };
}
