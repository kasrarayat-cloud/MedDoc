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
 * ⚠️ **THIS LIST IS THE PROMOTION SIDE ONLY, AND THE TWO SIDES ARE
 * INDEPENDENT.** Widening it does NOT make an OWNER demotable: that is refused
 * in `changeMemberRoleAction` by `CANNOT_CHANGE_AN_OWNER`, whatever role is
 * asked for. So "every practice has at least one OWNER" still holds
 * STRUCTURALLY — **no owner COUNT is ever read** — exactly as it did before.
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
 * ⚠️ **DEMOTION AND REMOVAL ARE FILED, NOT FORGOTTEN.** Partners do leave
 * practices, so the capability is needed; it is a separate ADMIN row because it
 * is the half that requires a **last-owner guard**, and that guard must be
 * correct under concurrency — a partial unique index or a SERIALIZABLE
 * transaction, **never a count read and then acted on**. Two owners demoting
 * each other simultaneously is precisely the interleaving a read-then-write
 * check cannot see.
 */
export const ASSIGNABLE_ROLES = ['OWNER', 'CLINICIAN', 'TECH'] as const;
export type AssignableRole = (typeof ASSIGNABLE_ROLES)[number];

export function isAssignableRole(v: unknown): v is AssignableRole {
  return typeof v === 'string' && (ASSIGNABLE_ROLES as readonly string[]).includes(v);
}
