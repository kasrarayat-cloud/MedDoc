// ============================================================================
// Multi-tenancy helpers
// ----------------------------------------------------------------------------
// Centralizes the "who can see/do what across practices" rules so call sites
// don't re-implement the logic (and drift).
//
// Role semantics:
//   DOCTOR, STAFF  — scoped to their own practice, and within that, only
//                    patients they created/are assigned to.
//   ADMIN          — scoped to their own practice, but sees EVERY patient
//                    and user within it.
//   SUPER_ADMIN    — bypass all tenant scoping. Platform ops only.
// ============================================================================

import type { Session } from '@/lib/auth';

/**
 * True if the session belongs to a role that sees data across all practices.
 * Use at read sites to decide whether to apply a practiceId filter, and at
 * mutation sites to decide whether to enforce same-practice guards.
 */
export function canBypassTenantScope(session: Session): boolean {
  return session.user.role === 'SUPER_ADMIN';
}

/**
 * Build a `where` clause fragment that scopes queries to the session's
 * practice. SUPER_ADMIN gets an empty object (no filter). Spread into a
 * larger where:
 *
 *   await prisma.user.findMany({ where: { ...tenantScope(session) } })
 */
export function tenantScope(session: Session): { practiceId?: string } {
  if (canBypassTenantScope(session)) return {};
  return { practiceId: session.user.practiceId };
}

/**
 * Guard a mutation that targets a specific user. Throws if the target is
 * in a different practice than the session (and the session isn't a
 * SUPER_ADMIN). Returns the target's practiceId so the caller can use it.
 *
 * Uses a lightweight PK lookup — one extra indexed query per mutation.
 * Worth it: without this, a compromised or buggy admin could mutate any
 * userId across practices.
 */
import prisma from '@/lib/db';

export async function assertSamePracticeUser(
  session: Session,
  targetUserId: string
): Promise<void> {
  if (canBypassTenantScope(session)) return;
  const target = await prisma.user.findUnique({
    where: { id: targetUserId },
    select: { practiceId: true },
  });
  if (!target) {
    // Mirror the "doesn't exist" vs "can't see" conflation used in
    // patient access — don't leak which emails/ids exist cross-tenant.
    throw new TenantScopeError('User not found.');
  }
  if (target.practiceId !== session.user.practiceId) {
    throw new TenantScopeError('User not found.');
  }
}

export class TenantScopeError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'TenantScopeError';
  }
}
