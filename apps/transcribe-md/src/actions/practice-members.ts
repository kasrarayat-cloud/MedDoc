'use server';

// ============================================================================
// ADMIN-1 — SEAT MINTING AND MEMBER ROLES.
// ----------------------------------------------------------------------------
// The two gaps the row names, and nothing else. Role enforcement across the
// other 48 mutating surfaces is RULED AGAINST, not missing — signing is the
// sole role-gated action, techs prepare and deliver. Administration is a third
// axis and this file is the whole of it.
// ============================================================================

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
import { changeRoleGuarded, removeMemberGuarded } from '@/lib/practice-owner-guard';
import { hashInviteCode, normalizeInviteCode } from '@/lib/signup-invite';

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

/** Removal takes an id and NOTHING else. There is no role to choose and no
 *  free text to carry — the act is fully described by who is being removed, and
 *  a parameter nobody needs is a parameter somebody can abuse. */
const RemoveSchema = z.object({
  userId: z.string().trim().min(1),
});

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
    // LISTING HAS IT. A removed member keeps their `practiceId`, so the row is
    // still findable by id+practice; without this conjunct the action could
    // write a role onto somebody `listPracticeMembers` does not render.
    //
    // ⚠️ THIS COMMENT PREVIOUSLY CARRIED THREE CLAIMS THAT ARE NOW FALSE, AND
    // THEY ARE NAMED RATHER THAN QUIETLY DELETED, because each was load-bearing
    // for somebody's reasoning:
    //
    //   1. "deactivation leaves practiceRole intact" — `removeMemberAction`
    //      sets it to NULL, which the column's own doc requires of a
    //      deactivated row ("a sentinel there would be a claim nobody made").
    //   2. "`CANNOT_CHANGE_AN_OWNER` refuses to ever move it again" — that
    //      refusal is retired; an owner is movable now, subject to the
    //      last-owner guard.
    //   3. "this is the ONLY `practiceRole` write in application code" — FALSE
    //      WHEN IT WAS WRITTEN, not merely outdated. The legacy app's
    //      `activateUserAction` (apps/meddoc-pro/src/app/system-admin/
    //      actions.ts:109-119) writes `practiceRole: 'OWNER'` on an existing
    //      user whose role is NULL. That app is decommissioned and its
    //      container is not running, but it is not architecturally removed and
    //      `docker compose up` restores it.
    //
    // ⚠️ AND (3) HAS A LIVE CONSEQUENCE FOR THIS FEATURE, RECORDED SO IT IS NOT
    // MET BY SURPRISE: because removal NULLs the role, that legacy reactivation
    // path would restore a removed TECH as an OWNER. It is not fixed here —
    // fixing a decommissioned app is a different change — but the guard's own
    // count reads `deactivatedAt IS NULL`, so a removed row can never be
    // counted as an owner while it is removed.
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

  // ⚠️ AN OWNER IS NOW EDITABLE, AND THE INVARIANT MOVED RATHER THAN LAPSED.
  // Until ADMIN-5 this branch refused every change to an owner unconditionally,
  // and that refusal was what made "a practice always has at least one owner"
  // hold STRUCTURALLY — no count was ever read, so no count could be read
  // wrongly. Opening demotion is exactly what destroys that, so the structural
  // guarantee is replaced by a database-enforced one, not by a weaker version
  // of itself.
  //
  // ⚠️ AND THE REPLACEMENT IS NOT A COUNT READ HERE. `changeRoleGuarded` takes
  // the practice's row lock and puts the owner count INSIDE the UPDATE's own
  // WHERE clause, so Postgres decides and writes in one statement. There is no
  // number in this file to get wrong. See `lib/practice-owner-guard.ts` for the
  // interleaving it survives and for why the two shapes the ADMIN-5 row names
  // were measured and set aside.
  //
  // ⚠️ THE NO-OP ARM STAYS ABOVE THE GUARD, DELIBERATELY. An append-only trail
  // that records changes which did not happen is worse than one that misses
  // none — and a lateral OWNER -> OWNER must not be refused for want of a
  // second owner, which is the one case the guard's clause cannot distinguish
  // from a demotion.
  if (target.practiceRole === parsed.data.role) {
    return { ok: true, changedAt: Date.now() };
  }

  const guarded = await changeRoleGuarded({
    practiceId: guard.practiceId,
    userId: target.id,
    toRole: parsed.data.role,
  });

  if (guarded.outcome === 'LAST_OWNER') {
    // ⚠️ AUDITED, BECAUSE A REFUSED ADMINISTRATIVE ACT IS AN EVENT. Somebody
    // tried to leave a practice with no owner; that it failed is exactly what
    // the trail should be able to show later.
    await logAudit({
      action: 'PRACTICE_ADMIN_REFUSED',
      targetType: 'User',
      targetId: target.id,
      metadata: {
        refusal: 'LAST_OWNER',
        attempted: 'ROLE_CHANGE',
        to: parsed.data.role,
        practiceId: guard.practiceId,
      },
    });
    return { ok: false, reason: 'LAST_OWNER', message: ADMIN_REFUSAL_MESSAGE.LAST_OWNER };
  }

  if (guarded.outcome === 'TARGET_MOVED') {
    // The row moved between the read and the guarded write, or is no longer in
    // this practice. Fail closed: we cannot know the change is still safe.
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
      // ⚠️ READ UNDER THE LOCK, NOT FROM THE PRE-LOCK SNAPSHOT. `target` was
      // read before the practice was locked, so it can name a role the row no
      // longer held when the UPDATE ran — a false entry in an append-only
      // trail, which is worse than a missing one. The guard returns what it
      // saw inside the transaction it wrote in.
      from: guarded.from ?? null,
      to: parsed.data.role,
      practiceId: guard.practiceId,
    },
  });

  revalidatePath(MEMBERS_PATH);
  return { ok: true, changedAt: Date.now() };
}

export async function removeMemberAction(
  _prev: RoleState,
  formData: FormData,
): Promise<RoleState> {
  const guard = await requirePracticeAdmin(await getSession());
  if (!guard.ok) return { ok: false, reason: guard.reason, message: guard.message };

  const parsed = RemoveSchema.safeParse({ userId: formData.get('userId') });
  if (!parsed.success) {
    return {
      ok: false,
      reason: 'TARGET_NOT_IN_PRACTICE',
      message: ADMIN_REFUSAL_MESSAGE.TARGET_NOT_IN_PRACTICE,
    };
  }

  // ⚠️ SELF-REMOVAL IS REFUSED, AND IT IS A DIFFERENT REFUSAL FROM THE ROLE
  // ONE. `CANNOT_CHANGE_OWN_ROLE` names a role change; a doctor who has just
  // clicked "Remove" needs to be told about removal. Same reasoning, and the
  // last-owner guard would NOT catch this on its own: a practice with two
  // owners lets either remove themselves, and both could leave.
  if (parsed.data.userId === guard.actorId) {
    return {
      ok: false,
      reason: 'CANNOT_REMOVE_YOURSELF',
      message: ADMIN_REFUSAL_MESSAGE.CANNOT_REMOVE_YOURSELF,
    };
  }

  // ⚠️ REMOVAL GOES THROUGH THE SAME GUARD AS DEMOTION, AND THAT IS THE POINT.
  // Removing the last owner destroys "every practice has at least one owner"
  // exactly as demoting them does — it is the SECOND DOOR to one invariant, and
  // a guard fitted to only the first door is a guard that looks complete.
  const guarded = await removeMemberGuarded({
    practiceId: guard.practiceId,
    userId: parsed.data.userId,
    actorId: guard.actorId,
  });

  if (guarded.outcome === 'LAST_OWNER') {
    await logAudit({
      action: 'PRACTICE_ADMIN_REFUSED',
      targetType: 'User',
      targetId: parsed.data.userId,
      metadata: {
        refusal: 'LAST_OWNER',
        attempted: 'REMOVE',
        practiceId: guard.practiceId,
      },
    });
    return { ok: false, reason: 'LAST_OWNER', message: ADMIN_REFUSAL_MESSAGE.LAST_OWNER };
  }

  if (guarded.outcome === 'TARGET_MOVED') {
    return {
      ok: false,
      reason: 'TARGET_NOT_IN_PRACTICE',
      message: ADMIN_REFUSAL_MESSAGE.TARGET_NOT_IN_PRACTICE,
    };
  }

  await logAudit({
    // ⚠️ ITS OWN LABEL, NOT `USER_DEACTIVATED`. The mechanism is shared with
    // the platform's account deactivation; the ACT is not. A practice owner
    // removing a colleague and a super-admin disabling an account are different
    // events with different actors, and an action-level rollup that cannot tell
    // them apart is the reason ADMIN-1 declined to reuse `USER_ROLE_CHANGED`
    // for practice roles. Same axis argument, one migration later.
    action: 'PRACTICE_MEMBER_REMOVED',
    targetType: 'User',
    targetId: parsed.data.userId,
    metadata: {
      // ⚠️ THE ROLE THEY HELD, CAPTURED UNDER THE LOCK BEFORE IT WAS NULLED.
      // The row no longer carries it, so this entry is the only record of what
      // was removed — and re-adding somebody needs to know.
      removedRole: guarded.from ?? null,
      practiceId: guard.practiceId,
    },
  });

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
