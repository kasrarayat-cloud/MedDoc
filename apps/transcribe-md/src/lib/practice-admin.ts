// ============================================================================
// ADMIN-1 — WHO MAY ADMINISTER A PRACTICE, AND WHAT THAT PERMITS.
// ----------------------------------------------------------------------------
// The guard is the SIGN ROUTE'S OWN PATTERN, deliberately, because that is the
// one ruled shape for a role gate in this codebase:
//
//     DB read  ->  fail closed on NULL  ->  refuse BY NAME  ->  audit
//
// ⚠️ THE ROLE IS READ FROM THE DATABASE, NEVER FROM THE SESSION. A JWT is
// minted at sign-in and lives for its own lifetime: a member demoted from
// OWNER five minutes ago still carries `OWNER` in their token. Reading the
// column is what makes a demotion take effect NOW rather than at next login,
// and this file exists to hand out SEATS — the one surface where a stale
// elevation mints durable access for somebody else.
//
// ⚠️ AND NOTE WHAT IS *NOT* HERE. Role enforcement across the other 48 mutating
// surfaces is RULED AGAINST, not missing: `SIGNING IS THE SOLE ROLE-GATED
// ACTION` (RULINGS 2026-08-06), re-ratified 2026-09-05 — techs prepare,
// including deleting unsigned drafts, and deliver. Administration is a THIRD
// axis, distinct from both signing and delivery; conflating axes is how the
// "48 ungated surfaces" misreading happened in the first place.
// ============================================================================

import { randomBytes } from 'node:crypto';

import type { PracticeRole } from '@prisma/client';

import prisma from '@meddoc/db';

import { logAudit } from '@/lib/audit';
import { LAST_OWNER_REFUSAL } from '@/lib/last-owner-invariant';

/**
 * The role that administers a practice.
 *
 * ⚠️ THIS IS NOT A DECISION THIS FILE MAKES. `schema.prisma`'s own doc comment
 * on the enum — applied in production — reads: *"OWNER: Signs, and administers
 * the practice."* The constant names it so the guard and the schema cannot
 * drift, and so a reader can find the authority in one hop.
 */
// ⚠️ THE ROLE VOCABULARY LIVES IN `practice-roles.ts` AND IS RE-EXPORTED HERE.
// This module is server-only — `node:crypto`, Prisma, the audit logger — and
// the members panel is a client component that needs the assignable list to
// draw its selects. Re-exporting keeps every existing import of
// `@/lib/practice-admin` resolving unchanged while giving the client a door
// that does not drag the server graph with it.
//
// ⚠️ IMPORTED **AND** RE-EXPORTED, NOT `export … from`. A bare
// `export { PRACTICE_ADMIN_ROLE } from '…'` forwards the name to importers and
// does NOT create a binding in THIS module's scope — so `requirePracticeAdmin`
// below, which compares against it, threw `PRACTICE_ADMIN_ROLE is not defined`
// at runtime while `tsc` and every importer stayed happy. The guard would have
// failed OPEN-shaped (it throws rather than admits, so it fails closed in
// effect) on the one surface that hands out seats. Caught by the gate suite,
// not by review.
import {
  ASSIGNABLE_ROLES,
  PRACTICE_ADMIN_ROLE,
  isAssignableRole,
  type AssignableRole,
} from '@/lib/practice-roles';

export { ASSIGNABLE_ROLES, PRACTICE_ADMIN_ROLE, isAssignableRole };
export type { AssignableRole };

export type AdminRefusal =
  | 'UNAUTHENTICATED'
  | 'ROLE_MAY_NOT_ADMINISTER'
  | 'TARGET_NOT_IN_PRACTICE'
  | 'CANNOT_CHANGE_OWN_ROLE'
  | 'CANNOT_REMOVE_YOURSELF'
  | 'LAST_OWNER'
  | 'TRANSFER_TARGET_INVALID'
  | 'ROLE_CHANGED_UNDER_YOU'
  | 'ROLE_NOT_ASSIGNABLE';

export type AdminGuardResult =
  | { ok: true; actorId: string; practiceId: string }
  | { ok: false; reason: AdminRefusal; message: string };

/** Every refusal this module can emit, in the doctor's words. One map, so a
 *  message cannot drift from the code that returns it. */
export const ADMIN_REFUSAL_MESSAGE: Record<AdminRefusal, string> = {
  UNAUTHENTICATED: 'You must be signed in.',
  ROLE_MAY_NOT_ADMINISTER:
    'Only a practice owner can manage members and invite new ones.',
  TARGET_NOT_IN_PRACTICE: 'That member is not in your practice.',
  CANNOT_CHANGE_OWN_ROLE:
    'You cannot change your own role. Ask another owner, or use Transfer ownership to hand the practice on.',
  // ⚠️ `CANNOT_CHANGE_AN_OWNER` WAS DELETED WITH THE CAPABILITY IT DESCRIBED.
  // It said an owner's role could never be changed here and told the doctor to
  // ask support; ADMIN-5 makes that false, and a refusal string that outlives
  // its refusal is how a page starts lying. The one owner case that is still
  // refused is LAST_OWNER, below — and that refusal belongs to the DATABASE.
  CANNOT_REMOVE_YOURSELF:
    'You cannot remove yourself from the practice. To leave, use Transfer ownership and choose to leave.',
  // ⚠️ NOT A NEW SENTENCE. The trigger (`users_last_owner_guard`) refused the
  // write; the words are the friendly-refusal file's own, so a doctor meets one
  // sentence for one refusal wherever it surfaces. Callers that have the
  // trigger's classification pass ITS reason (which distinguishes the stranded
  // and sole-member cases); this entry is the default.
  LAST_OWNER: LAST_OWNER_REFUSAL,
  TRANSFER_TARGET_INVALID:
    'Ownership can only be handed to another active member of your practice.',
  // The compare-and-set found the row had moved since it was read. Refusing is
  // fail-closed: we cannot know the demotion is still safe, so the doctor is
  // told to look again rather than shown a success that did not happen.
  ROLE_CHANGED_UNDER_YOU:
    "That member's role was changed by someone else a moment ago. Nothing was saved — reload the page and check before trying again.",
  ROLE_NOT_ASSIGNABLE: 'That role cannot be assigned from this page.',
};

/**
 * The administration gate.
 *
 * ⚠️ FAIL-CLOSED ON AN ABSENT OR UNRECOGNISED ROLE, not merely on a known
 * non-owner. A member whose `practiceRole` is somehow NULL refuses too — the
 * database CHECK makes that unreachable for an active member, and this does not
 * rely on it. The sign route says the same thing about itself, for the same
 * reason.
 */
export async function requirePracticeAdmin(session: {
  user: { id: string; practiceId: string };
} | null): Promise<AdminGuardResult> {
  if (!session?.user?.id || !session.user.practiceId) {
    return {
      ok: false,
      reason: 'UNAUTHENTICATED',
      message: ADMIN_REFUSAL_MESSAGE.UNAUTHENTICATED,
    };
  }

  const actor = await prisma.user.findUnique({
    where: { id: session.user.id },
    select: { practiceRole: true, practiceId: true },
  });

  if (
    actor == null ||
    actor.practiceRole !== PRACTICE_ADMIN_ROLE ||
    actor.practiceId !== session.user.practiceId
  ) {
    // A gate nothing records is one path away from not existing.
    void logAudit({
      action: 'PRACTICE_ADMIN_REFUSED',
      targetType: 'Practice',
      targetId: session.user.practiceId,
      // Structured only. The role and the fact of refusal — never a name.
      metadata: {
        practiceRole: actor?.practiceRole ?? null,
        // ⚠️ RECORDED SEPARATELY FROM THE ROLE. A session whose practiceId no
        // longer matches the row is a DIFFERENT failure from a wrong role, and
        // one label for both would make a stale token and a demotion look the
        // same in an append-only trail.
        practiceMismatch: actor != null && actor.practiceId !== session.user.practiceId,
      },
    });
    return {
      ok: false,
      reason: 'ROLE_MAY_NOT_ADMINISTER',
      message: ADMIN_REFUSAL_MESSAGE.ROLE_MAY_NOT_ADMINISTER,
    };
  }

  return { ok: true, actorId: session.user.id, practiceId: session.user.practiceId };
}

// ============================================================================
// SEAT CODES
// ----------------------------------------------------------------------------
// ⚠️ ONE GENERATOR, NOT TWO. `scripts/issue-invite-code.ts` had this inline and
// now imports it. A second copy would drift from the first the day either is
// touched, and the thing that would drift is the alphabet a human reads aloud.
// ============================================================================

/** Crockford-style: no I, L, O or U — so a code read over the phone cannot be
 *  transcribed into a different one, and cannot spell anything. */
const ALPHABET = '0123456789ABCDEFGHJKMNPQRSTVWXYZ';

export function generateInviteCode(): string {
  const bytes = randomBytes(16);
  let out = '';
  for (let i = 0; i < 16; i += 1) {
    out += ALPHABET[bytes[i] % ALPHABET.length];
    if (i === 3 || i === 7 || i === 11) out += '-';
  }
  return out;
}

// ============================================================================
// READS FOR THE MEMBERS PANEL
// ----------------------------------------------------------------------------
// ⚠️ THE LIST IS VISIBLE TO EVERY MEMBER; THE CONTROLS ARE NOT. That is not a
// softening of the gate — it is the enum's own sentence, applied: *"the role
// boundary is on ACTIONS, not on visibility"*, and SPEC §4.1b makes read
// practice-uniform. A clinician who cannot see who else is in their practice
// cannot tell who to ask to sign.
// ============================================================================

export type PracticeMember = {
  id: string;
  name: string | null;
  email: string;
  practiceRole: PracticeRole | null;
  isSelf: boolean;
};

export type OutstandingInvite = {
  id: string;
  label: string | null;
  practiceRole: PracticeRole | null;
  expiresAt: Date | null;
  createdAt: Date;
};

export async function listPracticeMembers(
  practiceId: string,
  viewerId: string,
): Promise<PracticeMember[]> {
  const rows = await prisma.user.findMany({
    // ⚠️ ACTIVE ONLY. A deactivated account carries a NULL practiceRole by
    // design ("a sentinel there would be a claim nobody made"), so listing them
    // would show a member with no role and invite somebody to "fix" it.
    where: { practiceId, deactivatedAt: null },
    select: { id: true, name: true, email: true, practiceRole: true },
    orderBy: [{ practiceRole: 'asc' }, { email: 'asc' }],
  });
  return rows.map((r) => ({ ...r, isSelf: r.id === viewerId }));
}

export async function listOutstandingInvites(
  practiceId: string,
): Promise<OutstandingInvite[]> {
  const now = new Date();
  return prisma.inviteCode.findMany({
    where: {
      practiceId,
      revokedAt: null,
      // ⚠️ UNUSED AND UNEXPIRED. A consumed seat is not outstanding, and an
      // expired one is not actionable — showing either would offer a Revoke
      // button that changes nothing.
      usedCount: 0,
      OR: [{ expiresAt: null }, { expiresAt: { gt: now } }],
    },
    select: {
      id: true,
      label: true,
      practiceRole: true,
      expiresAt: true,
      createdAt: true,
    },
    orderBy: { createdAt: 'desc' },
  });
}
