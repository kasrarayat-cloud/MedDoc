// ============================================================================
// POST /api/admin/users/[id]/grant-admin — add SUPER_ADMIN to a user's products
// ----------------------------------------------------------------------------
// Confirmation: caller supplies `confirmEmail` matching the target's
// email exactly (defense against fat-finger). No-op if the user already
// has SUPER_ADMIN.
// ============================================================================

import { NextResponse } from 'next/server';
import { z } from 'zod';

import prisma from '@meddoc/db';
import { Product } from '@prisma/client';

import { adminApi } from '@/lib/admin-api-gate';
import { logAudit } from '@/lib/audit';

const Body = z.object({ confirmEmail: z.string().email() });

export const dynamic = 'force-dynamic';

export const POST = adminApi('users:grant-admin', async (req, ctx) => {
  const segs = new URL(req.url).pathname.split('/').filter(Boolean);
  const id = segs[segs.indexOf('users') + 1];
  if (!id) return NextResponse.json({ error: 'Bad path' }, { status: 400 });

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
  if (current.includes(Product.SUPER_ADMIN)) {
    return NextResponse.json({ ok: true, alreadyAdmin: true });
  }
  const next = [...current, Product.SUPER_ADMIN];

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  await (prisma.user as any).update({
    where: { id },
    data: { products: next },
  });

  await logAudit({
    action: 'USER_GRANTED_SUPER_ADMIN',
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
