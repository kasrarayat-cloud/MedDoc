// ============================================================================
// POST /api/admin/users/[id]/suspend — soft-pause an account
// ----------------------------------------------------------------------------
// Sets suspendedAt + suspendedBy + suspendedReason and bumps
// forceLogoutAt to now so any in-flight session is invalidated on its
// next request. Reversible via /unsuspend (the row stays intact —
// distinct from the older deactivatedAt one-way flag).
// ============================================================================

import { NextResponse } from 'next/server';
import { z } from 'zod';

import prisma from '@meddoc/db';

import { adminApi } from '@/lib/admin-api-gate';
import { logAudit } from '@/lib/audit';

const Body = z.object({ reason: z.string().trim().max(500).optional() });

export const dynamic = 'force-dynamic';

export const POST = adminApi('users:suspend', async (req, ctx) => {
  const segs = new URL(req.url).pathname.split('/').filter(Boolean);
  const id = segs[segs.indexOf('users') + 1];
  if (!id) return NextResponse.json({ error: 'Bad path' }, { status: 400 });

  // Phase 6Z — server-side self-action block. The UI already disables the
  // chip when isSelf, but a direct POST (curl, replay, browser console)
  // would otherwise lock the actor out of /admin/* and nuke their
  // session via forceLogoutAt. Defense in depth: refuse here too.
  if (id === ctx.session.user.id) {
    return NextResponse.json(
      { error: 'Cannot suspend your own account — ask a peer.' },
      { status: 403 }
    );
  }

  const raw = await req.json().catch(() => ({}));
  const parsed = Body.safeParse(raw);
  if (!parsed.success) {
    return NextResponse.json({ error: 'Invalid body' }, { status: 400 });
  }

  const user = await prisma.user.findUnique({
    where: { id },
    select: { id: true, email: true, practiceId: true },
  });
  if (!user) return NextResponse.json({ error: 'Not found' }, { status: 404 });

  const now = new Date();
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  await (prisma.user as any).update({
    where: { id },
    data: {
      suspendedAt: now,
      suspendedBy: ctx.session.user.id,
      suspendedReason: parsed.data.reason ?? null,
      forceLogoutAt: now,
    },
  });

  await logAudit({
    action: 'USER_SUSPENDED',
    targetType: 'User',
    targetId: id,
    metadata: {
      targetEmail: user.email,
      reason: parsed.data.reason ?? null,
      actorEmail: ctx.session.user.email,
    },
    practiceId: user.practiceId,
  });

  return NextResponse.json({
    ok: true,
    user: {
      id,
      suspendedAt: now.toISOString(),
      suspendedBy: ctx.session.user.id,
      suspendedReason: parsed.data.reason ?? null,
    },
  });
});
