// ============================================================================
// POST /api/admin/users/[id]/unsuspend — clear a prior suspension
// ----------------------------------------------------------------------------
// We do NOT touch forceLogoutAt — a previously-suspended user is still
// expected to re-authenticate; lifting the suspension just lets them log
// back in.
// ============================================================================

import { NextResponse } from 'next/server';

import prisma from '@meddoc/db';

import { adminApi } from '@/lib/admin-api-gate';
import { logAudit } from '@/lib/audit';
import { withPracticeLock } from '@/lib/last-owner-invariant';

export const dynamic = 'force-dynamic';

export const POST = adminApi('users:unsuspend', async (req, ctx) => {
  const segs = new URL(req.url).pathname.split('/').filter(Boolean);
  const id = segs[segs.indexOf('users') + 1];
  if (!id) return NextResponse.json({ error: 'Bad path' }, { status: 400 });

  // Security audit P1-E: defense-in-depth. A suspended admin can't
  // reach this endpoint anyway (their session is invalidated), but
  // an admin self-unsuspending after a transient block-then-reload
  // would be a self-rehabilitation footgun — bounce so the audit
  // trail captures a peer's action.
  if (id === ctx.session.user.id) {
    return NextResponse.json(
      { error: 'Cannot unsuspend your own account — ask a peer.' },
      { status: 403 }
    );
  }

  const user = await prisma.user.findUnique({
    where: { id },
    select: { id: true, email: true, practiceId: true },
  });
  if (!user) return NextResponse.json({ error: 'Not found' }, { status: 404 });

  // ⚠️ RULING #268/#289 — THE PRACTICE LOCK BEFORE THE ROW WRITE, AND THIS
  // DOOR REALLY DOES REACH IT. Clearing `suspendedAt` makes a LIVE MEMBER of
  // a row that was not one, so `users_no_orphan_member` passes both of its
  // exemptions — NEW is a live non-owner, OLD was not live (#241a excludes
  // suspension from the member predicate) — and takes
  // `pg_advisory_xact_lock` on the target's practice. Unlocked, this is one
  // half of the shape measured at 10 deadlocks out of 10.
  await prisma.$transaction((tx) =>
    withPracticeLock(tx, user.practiceId, async () => {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      await (tx.user as any).update({
        where: { id },
        data: { suspendedAt: null, suspendedBy: null, suspendedReason: null },
      });
    }),
  );

  await logAudit({
    action: 'USER_UNSUSPENDED',
    targetType: 'User',
    targetId: id,
    metadata: {
      targetEmail: user.email,
      actorEmail: ctx.session.user.email,
    },
    practiceId: user.practiceId,
  });

  return NextResponse.json({ ok: true });
});
