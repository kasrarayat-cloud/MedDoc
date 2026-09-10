// ============================================================================
// POST /api/admin/users/[id]/profile — name and system role
// ----------------------------------------------------------------------------
// PORTED from the retired meddoc-pro console (`updateUserAction`), under ruling
// #310 step 3, with ONE deliberate narrowing:
//
// ⚠️ EMAIL IS NOT EDITABLE HERE. The original set `email` directly, with no
// re-verification — an admin typo would move the account to an address nobody
// had proven they own, and every reset link after that goes to the typo. Email
// changes stay on the existing change-email / confirm-email token flow. The
// body schema is `.strict()`, so a request carrying `email` is REFUSED rather
// than silently ignored.
//
// ⚠️ `role` IS THE LEGACY `UserRole`, NOT PLATFORM ADMIN. SUPER_ADMIN is a
// `Product`, granted and revoked only by the confirm-email doors
// (`grant-admin` / `revoke-admin`). `role = 'ADMIN'` does carry weight in the
// shared auth package (`patientAccessWhere` widens an ADMIN to the whole
// practice's patients), which is why every change is audited with from → to.
// A row whose legacy role is `SUPER_ADMIN` is not re-roled here at all.
//
// Audit labels are the original's: `USER_ROLE_CHANGED` when ONLY the role
// changed, so a security reviewer can filter role changes cleanly, and
// `USER_UPDATED` otherwise.
// ============================================================================

import { NextResponse } from 'next/server';
import { z } from 'zod';

import prisma from '@meddoc/db';

import { adminApi } from '@/lib/admin-api-gate';
import { logAudit } from '@/lib/audit';
import { withPracticeLock } from '@/lib/last-owner-invariant';

const EDITABLE_ROLES = ['DOCTOR', 'STAFF', 'ADMIN'] as const;

const Body = z
  .object({
    name: z.string().trim().min(1).max(200).optional(),
    role: z.enum(EDITABLE_ROLES).optional(),
  })
  .strict()
  .refine((b) => b.name !== undefined || b.role !== undefined, {
    message: 'Nothing to change',
  });

export const dynamic = 'force-dynamic';

export const POST = adminApi('users:profile', async (req, ctx) => {
  const segs = new URL(req.url).pathname.split('/').filter(Boolean);
  const id = segs[segs.indexOf('users') + 1];
  if (!id) return NextResponse.json({ error: 'Bad path' }, { status: 400 });

  // An admin re-roling themselves is a self-granted privilege change; their own
  // name is edited on /settings like everybody else's.
  if (id === ctx.session.user.id) {
    return NextResponse.json(
      { error: 'Cannot edit your own account here — use Settings, or ask a peer.' },
      { status: 403 }
    );
  }

  const raw = await req.json().catch(() => null);
  const parsed = Body.safeParse(raw);
  if (!parsed.success) {
    return NextResponse.json(
      { error: 'Body may carry only name and/or role (DOCTOR, STAFF, ADMIN)' },
      { status: 400 }
    );
  }

  const user = await prisma.user.findUnique({
    where: { id },
    select: { id: true, email: true, name: true, role: true, practiceId: true },
  });
  if (!user) return NextResponse.json({ error: 'Not found' }, { status: 404 });

  const data: { name?: string; role?: (typeof EDITABLE_ROLES)[number] } = {};
  const changed: Record<string, { from: string | null; to: string }> = {};
  if (parsed.data.name !== undefined && parsed.data.name !== (user.name ?? '')) {
    data.name = parsed.data.name;
    // Field NAMES and the role vocabulary only on the audit row — a person's
    // name is not recorded there.
    changed.name = { from: null, to: '(changed)' };
  }
  if (parsed.data.role !== undefined && parsed.data.role !== user.role) {
    if (user.role === 'SUPER_ADMIN') {
      return NextResponse.json(
        {
          error: 'This account carries the legacy SUPER_ADMIN role and is not re-roled here.',
          reason: 'ROLE_SUPER_ADMIN',
        },
        { status: 409 }
      );
    }
    data.role = parsed.data.role;
    changed.role = { from: String(user.role), to: parsed.data.role };
  }

  if (Object.keys(data).length === 0) {
    return NextResponse.json({ error: 'No changes', reason: 'NO_CHANGE' }, { status: 400 });
  }

  // ⚠️ RULING #289 — LOCKED THOUGH NEITHER COLUMN IS IN A TRIGGER PREDICATE.
  // Same reasoning `force-logout` records: that safety is a property of a
  // column list, not of this door, and the migration says the door set is open.
  await prisma.$transaction((tx) =>
    withPracticeLock(tx, user.practiceId, async () => {
      await tx.user.update({ where: { id }, data });
    }),
  );

  const changedFields = Object.keys(data);
  const roleOnly = changedFields.length === 1 && changedFields[0] === 'role';
  await logAudit({
    action: roleOnly ? 'USER_ROLE_CHANGED' : 'USER_UPDATED',
    targetType: 'User',
    targetId: id,
    metadata: {
      changedFields,
      changed,
      targetEmail: user.email,
      actorEmail: ctx.session.user.email,
    },
    practiceId: user.practiceId,
  });

  return NextResponse.json({ ok: true, user: { id }, changedFields });
});
