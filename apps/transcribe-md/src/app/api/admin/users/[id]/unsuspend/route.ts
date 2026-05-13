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

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  await (prisma.user as any).update({
    where: { id },
    data: { suspendedAt: null, suspendedBy: null, suspendedReason: null },
  });

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
