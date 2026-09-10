// ============================================================================
// PRACTICE ROLES — the role VOCABULARY, shared by the server guard and the UI.
// ----------------------------------------------------------------------------
// ⚠️ THIS FILE EXISTS BECAUSE OF A SERVER/CLIENT BOUNDARY, AND THE BOUNDARY IS
// THE WHOLE POINT. `practice-admin.ts` is the guard: it imports `node:crypto`,
// `@meddoc/db` and the audit logger, all of which are server-only. The members
// panel is a `'use client'` component and needs exactly one thing from that
// module — the list of roles a control may offer.
//
// Importing the guard to get the list would pull Prisma and `node:crypto` into
// the client graph. So the vocabulary lives here, with NO runtime imports at
// all, and `practice-admin.ts` re-exports it so every existing import keeps
// resolving unchanged.
//
// ⚠️ `import type` IS ERASED AT COMPILE TIME. The `PracticeRole` reference below
// costs the client bundle nothing; a VALUE import from `@prisma/client` would
// cost it everything. That distinction is the only reason this file can name
// the generated enum at all.
// ============================================================================

import type { PracticeRole } from '@prisma/client';

/** The role that may administer a practice — invite, and change roles. */
export const PRACTICE_ADMIN_ROLE = 'OWNER' as const satisfies PracticeRole;

/**
 * The roles a seat may be minted with, and the roles a member may be moved to.
 *
 * ⚠️ `OWNER` IS PRESENT, AND IT IS A RULING RATHER THAN A DRIFT. The
 * OWNER-not-exclusive decision (branch `feat/ruling-195-owner-not-exclusive`)
 * settles the question ADMIN-1 shipped fail-closed on: **a practice may have
 * more than one OWNER, and an existing OWNER may create another** — by minting
 * an OWNER seat or by promoting a member. Administration can be handed on,
 * which is the thing a real practice needs and the previous build could not do.
 *
 * ⚠️ **THIS LIST WAS THE PROMOTION SIDE ONLY UNTIL ADMIN-5 (2026-09-10).**
 * Until then an OWNER was not demotable at all — `CANNOT_CHANGE_AN_OWNER`
 * refused it unconditionally, and "every practice has at least one OWNER" held
 * STRUCTURALLY. ADMIN-5 deleted that refusal. The invariant now holds because
 * the DATABASE refuses the write that would break it — the
 * `users_last_owner_guard` trigger, ruling #210, the only enforcer — and
 * `changeMemberRoleAction` re-reads the ACTOR under the practice lock, so an
 * owner who was demoted a moment ago cannot act on a stale page. **Still no
 * owner COUNT is read and then acted on in application code.**
 *
 * ⚠️ **BUT WIDENING THIS LIST DID OPEN A RACE, AND AN EARLIER VERSION OF THIS
 * COMMENT DENIED IT.** It claimed "no read-then-write race". That was false and
 * an adversarial pass reproduced the counterexample. `changeMemberRoleAction`
 * reads the target's role, checks it, then writes — and while this list held
 * only `CLINICIAN`/`TECH`, **nothing could turn a target INTO an owner between
 * those two steps**, so the shape was incidentally safe. Adding `OWNER` is
 * exactly what made the window reachable: two concurrent requests, one
 * promoting B and one demoting B, both read B as `CLINICIAN`, both clear the
 * guard, and the demotion lands on an owner.
 *
 * It is closed by a **compare-and-set** in that action's `updateMany` WHERE
 * clause, not by the guard. If you widen this list again, that is the line to
 * re-read.
 *
 * ⚠️ **DEMOTION AND REMOVAL SHIPPED AS ADMIN-5, AND THE GUARD IS THE DATABASE.**
 * This paragraph used to file them as future work needing "a partial unique
 * index or a SERIALIZABLE transaction". Ruling #200 bound the INVARIANT and its
 * proof, never the mechanism; ruling #210 put the enforcement in a trigger on
 * the user row, which serializes on a per-practice advisory lock and counts
 * under row locks — measured by `packages/db/prisma/proofs/`. Two owners
 * demoting each other simultaneously is the interleaving that harness races.
 */
export const ASSIGNABLE_ROLES = ['OWNER', 'CLINICIAN', 'TECH'] as const;
export type AssignableRole = (typeof ASSIGNABLE_ROLES)[number];

/**
 * ADMIN-5a — what a departing OWNER becomes at the end of an ownership
 * transfer: one of the non-administering roles, or `LEAVE` (removed from the
 * practice). DERIVED from `ASSIGNABLE_ROLES` so a new non-owner role appears
 * here and in the transfer control without anybody retyping a list.
 */
export const LEAVE_PRACTICE = 'LEAVE' as const;
export const STEP_DOWN_OPTIONS = [
  ...ASSIGNABLE_ROLES.filter(
    (r): r is Exclude<AssignableRole, typeof PRACTICE_ADMIN_ROLE> => r !== PRACTICE_ADMIN_ROLE,
  ),
  LEAVE_PRACTICE,
] as const;
export type StepDownOption = Exclude<AssignableRole, typeof PRACTICE_ADMIN_ROLE> | typeof LEAVE_PRACTICE;

export function isStepDownOption(v: unknown): v is StepDownOption {
  return typeof v === 'string' && (STEP_DOWN_OPTIONS as readonly string[]).includes(v);
}

export function isAssignableRole(v: unknown): v is AssignableRole {
  return typeof v === 'string' && (ASSIGNABLE_ROLES as readonly string[]).includes(v);
}
