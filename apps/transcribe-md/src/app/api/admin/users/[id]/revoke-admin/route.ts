// ============================================================================
// POST /api/admin/users/[id]/revoke-admin — remove SUPER_ADMIN from a user
// ----------------------------------------------------------------------------
// Self-revoke is BLOCKED — without this guard a careless admin could
// lock themselves (and potentially the entire org) out of the admin
// surface in a single click. They must have a peer admin do it.
//
// Force-logs-them-out so any cached SUPER_ADMIN claim in their JWT is
// invalidated on their next request.
// ============================================================================

import { NextResponse } from 'next/server';
import { z } from 'zod';

import prisma from '@meddoc/db';
import { Product } from '@prisma/client';

import { adminApi } from '@/lib/admin-api-gate';
import { logAudit } from '@/lib/audit';
import { withPracticeLock } from '@/lib/last-owner-invariant';

const Body = z.object({ confirmEmail: z.string().email().max(254) });

export const dynamic = 'force-dynamic';

export const POST = adminApi('users:revoke-admin', async (req, ctx) => {
  const segs = new URL(req.url).pathname.split('/').filter(Boolean);
  const id = segs[segs.indexOf('users') + 1];
  if (!id) return NextResponse.json({ error: 'Bad path' }, { status: 400 });

  if (id === ctx.session.user.id) {
    return NextResponse.json(
      { error: 'Cannot revoke your own admin access — ask a peer.' },
      { status: 403 }
    );
  }

  const raw = await req.json().catch(() => null);
  const parsed = Body.safeParse(raw);
  if (!parsed.success) {
    return NextResponse.json(
      { error: 'Body must include confirmEmail' },
      { status: 400 }
    );
  }

  const user = await prisma.user.findUnique({
    where: { id },
    select: { id: true, email: true, products: true, practiceId: true },
  });
  if (!user) return NextResponse.json({ error: 'Not found' }, { status: 404 });

  if (parsed.data.confirmEmail.toLowerCase() !== user.email.toLowerCase()) {
    return NextResponse.json(
      { error: 'confirmEmail does not match user.email' },
      { status: 400 }
    );
  }

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const current = (user.products as any[] | undefined) ?? [];
  const next = current.filter((p) => p !== Product.SUPER_ADMIN);

  const now = new Date();
  // ⚠️ RULING #289 — SAME REASONING AS `force-logout`. `products` and
  // `forceLogoutAt` are in neither trigger predicate, so this exits at an
  // exemption today. Locked anyway: revoking SUPER_ADMIN is exactly the write
  // that acquires a new column the day app-admin becomes part of the
  // ownership question.
  await prisma.$transaction((tx) =>
    withPracticeLock(tx, user.practiceId, async () => {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      await (tx.user as any).update({
        where: { id },
        data: { products: next, forceLogoutAt: now },
      });
    }),
  );

  await logAudit({
    action: 'USER_REVOKED_SUPER_ADMIN',
    targetType: 'User',
    targetId: id,
    metadata: {
      targetEmail: user.email,
      actorEmail: ctx.session.user.email,
      productsAfter: next,
    },
    practiceId: user.practiceId,
  });

  return NextResponse.json({ ok: true, products: next });
});
