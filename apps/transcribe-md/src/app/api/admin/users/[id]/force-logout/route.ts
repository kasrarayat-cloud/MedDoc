// ============================================================================
// POST /api/admin/users/[id]/force-logout — invalidate every active session
// ----------------------------------------------------------------------------
// Sets forceLogoutAt = now. The shared jwt() callback honours this and
// rejects any JWT issued earlier on the user's next request. No effect
// on the suspendedAt / softDeletedAt flags — useful as a standalone
// action when you suspect token compromise.
// ============================================================================

import { NextResponse } from 'next/server';

import prisma from '@meddoc/db';

import { adminApi } from '@/lib/admin-api-gate';
import { logAudit } from '@/lib/audit';
import { withPracticeLock } from '@/lib/last-owner-invariant';

export const dynamic = 'force-dynamic';

export const POST = adminApi('users:force-logout', async (req, ctx) => {
  const segs = new URL(req.url).pathname.split('/').filter(Boolean);
  const id = segs[segs.indexOf('users') + 1];
  if (!id) return NextResponse.json({ error: 'Bad path' }, { status: 400 });

  // Security audit P1-E: a single-SUPER_ADMIN tenant clicking
  // force-logout on themselves locks the only admin out — DB-level
  // intervention required to recover. Mirror the guard pattern from
  // revoke-admin / suspend / soft-delete (all sibling routes).
  if (id === ctx.session.user.id) {
    return NextResponse.json(
      { error: 'Cannot force-logout yourself — ask a peer.' },
      { status: 403 }
    );
  }

  const user = await prisma.user.findUnique({
    where: { id },
    select: { id: true, email: true, practiceId: true },
  });
  if (!user) return NextResponse.json({ error: 'Not found' }, { status: 404 });

  const now = new Date();
  // ⚠️ RULING #289 — LOCKED THOUGH THIS DOOR CANNOT DEADLOCK TODAY, AND THE
  // DISTINCTION IS WRITTEN DOWN RATHER THAN ASSUMED. `forceLogoutAt` is in
  // NEITHER trigger predicate, so both guards exit at an exemption before
  // reaching `pg_advisory_xact_lock`. That safety is a property of a COLUMN
  // LIST, not of this door — #241a already moved the member predicate once —
  // and the migration's own header says the door set is OPEN. A door safe
  // only by coincidence is the sixth door that header warns about.
  await prisma.$transaction((tx) =>
    withPracticeLock(tx, user.practiceId, async () => {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      await (tx.user as any).update({
        where: { id },
        data: { forceLogoutAt: now },
      });
    }),
  );

  await logAudit({
    action: 'USER_FORCE_LOGOUT',
    targetType: 'User',
    targetId: id,
    metadata: {
      targetEmail: user.email,
      actorEmail: ctx.session.user.email,
    },
    practiceId: user.practiceId,
  });

  return NextResponse.json({
    ok: true,
    forceLogoutAt: now.toISOString(),
  });
});
