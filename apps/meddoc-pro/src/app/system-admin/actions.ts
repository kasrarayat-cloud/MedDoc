'use server';

// ============================================================================
// System Admin Actions — DB + Mock mode support
// ============================================================================

import { revalidatePath } from 'next/cache';
import { headers } from 'next/headers';
import bcrypt from 'bcryptjs';
import prisma, { isDatabaseHealthy } from '@meddoc/db';
import { requireRole } from '@/lib/auth';
import { logAudit } from '@/lib/audit';
import { assertSamePracticeUser, TenantScopeError } from '@/lib/tenancy';
import { addMockUser, updateMockUser, deleteMockUser } from './mock-users';

type ActionResult = { ok: true; message: string } | { ok: false; error: string };

async function requireAdmin() {
  // Both practice-scoped ADMIN and cross-practice SUPER_ADMIN can reach
  // admin actions. Tenant guards run inside each action to enforce the
  // finer-grained rule (same-practice for ADMIN, any for SUPER_ADMIN).
  return requireRole(['ADMIN', 'SUPER_ADMIN']);
}

/**
 * Wrapper that standardizes "admin can only mutate users in their own
 * practice" guard. SUPER_ADMIN bypasses. Call this at the top of every
 * user-targeted mutation before touching the DB.
 *
 * Returns a narrow `{ ok: false; error }` shape that's assignable to both
 * ActionResult and SessionsResult (and any other Result-style union we
 * add), avoiding a type mismatch at each call site.
 */
async function guardSameTenant(
  session: Awaited<ReturnType<typeof requireAdmin>>,
  targetUserId: string
): Promise<{ ok: false; error: string } | null> {
  try {
    await assertSamePracticeUser(session, targetUserId);
    return null;
  } catch (err) {
    if (err instanceof TenantScopeError) {
      return { ok: false, error: err.message };
    }
    return { ok: false, error: 'Authorization failed.' };
  }
}

// ── Deactivate User ──
export async function deactivateUserAction(userId: string): Promise<ActionResult> {
  try {
    const session = await requireAdmin();
    const guardErr = await guardSameTenant(session, userId);
    if (guardErr) return guardErr;

    if (userId === session.user.id) {
      return { ok: false, error: 'Cannot deactivate your own account.' };
    }

    if (await isDatabaseHealthy()) {
      await prisma.user.update({
        where: { id: userId },
        data: { isActive: false, deactivatedAt: new Date(), deactivatedBy: session.user.id },
      });
    } else {
      updateMockUser(userId, { isActive: false });
    }

    await logAudit({
      action: 'USER_DEACTIVATED',
      targetId: userId,
      targetType: 'User',
      metadata: { adminId: session.user.id },
    });

    revalidatePath('/system-admin');
    return { ok: true, message: 'User deactivated.' };
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : 'Failed.' };
  }
}

// ── Activate User ──
export async function activateUserAction(userId: string): Promise<ActionResult> {
  try {
    const session = await requireAdmin();
    const guardErr = await guardSameTenant(session, userId);
    if (guardErr) return guardErr;

    if (await isDatabaseHealthy()) {
      await prisma.user.update({
        where: { id: userId },
        data: { isActive: true, deactivatedAt: null, deactivatedBy: null },
      });
    } else {
      updateMockUser(userId, { isActive: true });
    }

    await logAudit({
      action: 'USER_CREATED',
      targetId: userId,
      targetType: 'User',
      metadata: { action: 'reactivated' },
    });

    revalidatePath('/system-admin');
    return { ok: true, message: 'User activated.' };
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : 'Failed.' };
  }
}

// ── Kill All Sessions ──
export async function killAllSessionsAction(userId: string): Promise<ActionResult> {
  try {
    const session = await requireAdmin();
    const guardErr = await guardSameTenant(session, userId);
    if (guardErr) return guardErr;
    let count = 0;

    if (await isDatabaseHealthy()) {
      const deleted = await prisma.sessionLog.deleteMany({ where: { userId } });
      count = deleted.count;
      try { await prisma.session.deleteMany({ where: { userId } }); } catch { /* JWT mode */ }
    } else {
      updateMockUser(userId, { sessionCount: 0, lastSessionIp: null, lastSessionAt: null });
    }

    await logAudit({
      action: 'SESSION_EXPIRED',
      targetId: userId,
      targetType: 'User',
      metadata: { adminId: session.user.id, sessionsKilled: count },
    });

    revalidatePath('/system-admin');
    return { ok: true, message: `${count} session(s) cleared.` };
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : 'Failed.' };
  }
}

// ── Delete User ──
export async function deleteUserAction(userId: string): Promise<ActionResult> {
  try {
    const session = await requireAdmin();
    const guardErr = await guardSameTenant(session, userId);
    if (guardErr) return guardErr;

    if (userId === session.user.id) {
      return { ok: false, error: 'Cannot delete your own account.' };
    }

    if (await isDatabaseHealthy()) {
      // Delete related records first (in case cascade isn't set)
      try { await prisma.sessionLog.deleteMany({ where: { userId } }); } catch { /* */ }
      try { await prisma.session.deleteMany({ where: { userId } }); } catch { /* */ }
      try { await prisma.account.deleteMany({ where: { userId } }); } catch { /* */ }

      await prisma.user.delete({ where: { id: userId } });
    } else {
      deleteMockUser(userId);
    }

    await logAudit({
      action: 'USER_DELETED',
      targetId: userId,
      targetType: 'User',
      metadata: { adminId: session.user.id },
    });

    revalidatePath('/system-admin');
    return { ok: true, message: 'User permanently deleted.' };
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : 'Failed to delete.' };
  }
}

// ── Create New User ──
export async function createUserAction(formData: FormData): Promise<ActionResult> {
  try {
    const session = await requireAdmin();

    const name = (formData.get('name') as string)?.trim();
    const email = (formData.get('email') as string)?.trim().toLowerCase();
    const password = formData.get('password') as string;
    const role = formData.get('role') as string;

    if (!name || !email || !password) {
      return { ok: false, error: 'Name, email, and password are required.' };
    }
    if (password.length < 8) {
      return { ok: false, error: 'Password must be at least 8 characters.' };
    }
    if (!['DOCTOR', 'ADMIN', 'STAFF'].includes(role)) {
      return { ok: false, error: 'Invalid role.' };
    }

    if (await isDatabaseHealthy()) {
      const existing = await prisma.user.findUnique({ where: { email } });
      if (existing) return { ok: false, error: 'Email already exists.' };

      const passwordHash = await bcrypt.hash(password, 12);
      // New users inherit the creating admin's practiceId — this keeps
      // the admin's "manage your own practice's users" scope intact.
      // When SUPER_ADMIN lands, this becomes a form field.
      const user = await prisma.user.create({
        data: {
          name,
          email,
          passwordHash,
          role,
          isActive: true,
          practiceId: session.user.practiceId,
        },
      });

      await logAudit({
        action: 'USER_CREATED',
        targetId: user.id,
        targetType: 'User',
        metadata: { createdBy: session.user.id, role },
      });
    } else {
      addMockUser({
        id: `mock_${Date.now().toString(36)}`,
        email, name, role, isActive: true,
        lastLogin: null, createdAt: new Date().toISOString(),
        failedLoginCount: 0, lastSessionIp: null,
        lastSessionAt: null, lastSessionAgent: null, sessionCount: 0,
      });
    }

    revalidatePath('/system-admin');
    return { ok: true, message: `User "${name}" created.` };
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : 'Failed.' };
  }
}

// ── Update User Profile ──
export async function updateUserAction(
  userId: string,
  data: { name?: string; email?: string; role?: string }
): Promise<ActionResult> {
  try {
    const session = await requireAdmin();
    const guardErr = await guardSameTenant(session, userId);
    if (guardErr) return guardErr;

    const updateData: Record<string, unknown> = {};
    if (data.name?.trim()) updateData.name = data.name.trim();
    if (data.role && ['DOCTOR', 'ADMIN', 'STAFF'].includes(data.role)) updateData.role = data.role;
    if (data.email?.trim()) {
      const email = data.email.trim().toLowerCase();
      if (await isDatabaseHealthy()) {
        const existing = await prisma.user.findUnique({ where: { email } });
        if (existing && existing.id !== userId) {
          return { ok: false, error: 'Email already in use by another user.' };
        }
      }
      updateData.email = email;
    }

    if (Object.keys(updateData).length === 0) {
      return { ok: false, error: 'No changes provided.' };
    }

    if (await isDatabaseHealthy()) {
      await prisma.user.update({ where: { id: userId }, data: updateData });
    } else {
      updateMockUser(userId, updateData as Partial<import('./page').AdminUserView>);
    }

    // USER_ROLE_CHANGED is preserved as a distinct event when ONLY role
    // changed (so security reviewers can filter role changes cleanly).
    // Any broader profile edit (name/email, with or without role) logs as
    // USER_UPDATED with changedFields in metadata.
    const changedFields = Object.keys(updateData);
    const roleOnlyChange = changedFields.length === 1 && changedFields[0] === 'role';
    await logAudit({
      action: roleOnlyChange ? 'USER_ROLE_CHANGED' : 'USER_UPDATED',
      targetId: userId,
      targetType: 'User',
      metadata: { changedFields },
    });

    revalidatePath('/system-admin');
    return { ok: true, message: 'User updated.' };
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : 'Failed.' };
  }
}

// ── Reset User Password ──
export async function resetUserPasswordAction(
  userId: string,
  newPassword: string
): Promise<ActionResult> {
  try {
    const session = await requireAdmin();
    const guardErr = await guardSameTenant(session, userId);
    if (guardErr) return guardErr;

    if (!newPassword || newPassword.length < 8) {
      return { ok: false, error: 'Password must be at least 8 characters.' };
    }

    if (!(await isDatabaseHealthy())) {
      return { ok: false, error: 'Database required to reset passwords.' };
    }

    const passwordHash = await bcrypt.hash(newPassword, 12);

    await prisma.user.update({
      where: { id: userId },
      data: { passwordHash },
    });

    await logAudit({
      action: 'PASSWORD_RESET_BY_ADMIN',
      targetId: userId,
      targetType: 'User',
      metadata: { adminId: session.user.id },
    });

    revalidatePath('/system-admin');
    return { ok: true, message: 'Password reset successfully.' };
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : 'Failed.' };
  }
}

// ── Fetch SessionLog rows for a user ──
// Read-only server action for the UserSessionsModal. Returns newest first.
// Typed return shape so the client doesn't need to know the Prisma model.
export interface UserSessionRow {
  id: string;
  ipAddress: string | null;
  userAgent: string | null;
  action: string;
  createdAt: string; // ISO
}
type SessionsResult =
  | { ok: true; sessions: UserSessionRow[] }
  | { ok: false; error: string };

export async function getUserSessionsAction(userId: string): Promise<SessionsResult> {
  try {
    const session = await requireAdmin();
    const guardErr = await guardSameTenant(session, userId);
    if (guardErr) return guardErr;

    if (!(await isDatabaseHealthy())) {
      return { ok: true, sessions: [] };
    }

    const rows = await prisma.sessionLog.findMany({
      where: { userId },
      orderBy: { createdAt: 'desc' },
      take: 50,
    });
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const sessions: UserSessionRow[] = rows.map((r: any) => ({
      id: r.id,
      ipAddress: r.ipAddress ?? null,
      userAgent: r.userAgent ?? null,
      action: r.action ?? 'LOGIN',
      createdAt: r.createdAt.toISOString(),
    }));

    return { ok: true, sessions };
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : 'Failed to load sessions.' };
  }
}

// ── Delete a single SessionLog row ──
// IMPORTANT (JWT limitation): this only deletes the history entry. Our
// NextAuth session strategy is JWT (auth.config.ts), so the user's actual
// session cookie remains valid until its 8-hour expiry regardless of what
// rows exist in session_logs. Real revocation requires either switching
// to database sessions OR adding a JWT blocklist — both out of scope.
// The admin UI labels this button accordingly to avoid misleading ops.
export async function deleteSessionLogAction(sessionLogId: string): Promise<ActionResult> {
  try {
    const session = await requireAdmin();

    if (!(await isDatabaseHealthy())) {
      return { ok: false, error: 'Database required to delete session entries.' };
    }

    // Read the row first so we can (a) record the affected userId in the
    // audit and (b) enforce same-practice scoping. Pretending "not found"
    // on cross-tenant access keeps row-existence hidden from other
    // practices' admins.
    const row = await prisma.sessionLog.findUnique({ where: { id: sessionLogId } });
    if (!row) return { ok: false, error: 'Session entry not found.' };
    const guardErr = await guardSameTenant(session, row.userId);
    if (guardErr) return guardErr;

    await prisma.sessionLog.delete({ where: { id: sessionLogId } });

    await logAudit({
      action: 'SESSION_EXPIRED',
      targetId: row.userId,
      targetType: 'User',
      metadata: { adminId: session.user.id, sessionLogId, note: 'history-only-delete' },
    });

    return { ok: true, message: 'Session entry deleted.' };
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : 'Failed.' };
  }
}

// ── Log Session (called from NextAuth) ──
export async function logSessionLogin(userId: string): Promise<void> {
  try {
    let ip = 'Unknown';
    let ua = 'Unknown';
    try {
      const h = await headers();
      ip = h.get('x-forwarded-for')?.split(',')[0]?.trim() || h.get('x-real-ip') || 'Unknown';
      ua = h.get('user-agent') || 'Unknown';
    } catch { /* */ }

    if (await isDatabaseHealthy()) {
      await prisma.sessionLog.create({
        data: { userId, ipAddress: ip, userAgent: ua, action: 'LOGIN' },
      });
    }
  } catch { /* fire and forget */ }
}
