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
    // LISTING HAS IT. Deactivation writes `{isActive:false, deactivatedAt}` and
    // leaves `practiceId`/`practiceRole` intact, so a deactivated member is
    // still findable by id+practice. Without this the action could write OWNER
    // onto a row `listPracticeMembers` does not render — and once written,
    // `CANNOT_CHANGE_AN_OWNER` below refuses to ever move it again, because
    // this is the ONLY `practiceRole` write in application code. An invisible
    // owner nobody can revoke.
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

  // ⚠️ AN OWNER IS NOT EDITABLE HERE, AND THAT IS HALF OF WHAT KEEPS THE
  // INVARIANT. Every practice starts with at least one OWNER (a solo signup's
  // fallback), and since ruling #195 an OWNER may also be minted or promoted —
  // so this refusal is what makes "a practice always has at least one owner"
  // hold STRUCTURALLY rather than by a last-owner count.
  //
  // ⚠️ THIS READ IS A SNAPSHOT, AND UNTIL RULING #195 THAT DID NOT MATTER.
  // While `ASSIGNABLE_ROLES` was `['CLINICIAN','TECH']`, no in-app path could
  // turn a target INTO an owner, so the row could never become OWNER between
  // this read and the write below — the read-then-write shape was incidentally
  // safe. Widening the vocabulary is exactly what made that window reachable:
  // two concurrent requests, one promoting B to OWNER and one demoting B, both
  // read B as CLINICIAN, both pass this guard, and the demotion lands on an
  // OWNER. Demonstrated by an adversarial pass on this branch, with a
  // sequential control that is correctly refused and a base-tree control that
  // cannot reach the state at all.
  //
  // So the guard below is kept AND the write is made a COMPARE-AND-SET. Do not
  // remove either: this one refuses fast and speaks the doctor-facing reason;
  // the CAS is what makes the refusal true under concurrency.
  if (target.practiceRole === 'OWNER') {
    return {
      ok: false,
      reason: 'CANNOT_CHANGE_AN_OWNER',
      message: ADMIN_REFUSAL_MESSAGE.CANNOT_CHANGE_AN_OWNER,
    };
  }

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
  const { count } = await prisma.user.updateMany({
    where: {
      id: target.id,
      practiceId: guard.practiceId,
      deactivatedAt: null,
      practiceRole: target.practiceRole,
    },
    data: { practiceRole: parsed.data.role },
  });

  if (count === 0) {
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
