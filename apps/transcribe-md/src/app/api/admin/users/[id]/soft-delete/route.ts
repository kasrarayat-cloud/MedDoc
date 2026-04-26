// ============================================================================
// POST /api/admin/users/[id]/soft-delete — hide the user from admin UI
// ----------------------------------------------------------------------------
// Sets softDeletedAt + softDeletedBy and force-logs-them-out. The DB row
// stays intact for the HIPAA 7-year retention window — a real DELETE
// only happens via a future sweep job (not implemented here).
//
// Confirmation: caller must supply `confirmEmail` matching the user's
// email exactly (case-insensitive). Defends against fat-finger
// "click the wrong row in the table" mistakes.
// ============================================================================

import { NextResponse } from 'next/server';
import { z } from 'zod';

import prisma from '@meddoc/db';

import { adminApi } from '@/lib/admin-api-gate';
import { logAudit } from '@/lib/audit';

const Body = z.object({ confirmEmail: z.string().email() });

export const dynamic = 'force-dynamic';

export const POST = adminApi('users:soft-delete', async (req, ctx) => {
  const segs = new URL(req.url).pathname.split('/').filter(Boolean);
  const id = segs[segs.indexOf('users') + 1];
  if (!id) return NextResponse.json({ error: 'Bad path' }, { status: 400 });

  // Phase 6Z — server-side self-action block, matching revoke-admin and
  // suspend. Without this an admin can soft-delete themselves via a
  // direct POST and lose access to /admin/*; the UI guard alone isn't
  // enough.
  if (id === ctx.session.user.id) {
    return NextResponse.json(
      { error: 'Cannot soft-delete your own account — ask a peer.' },
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
    select: { id: true, email: true, practiceId: true },
  });
  if (!user) return NextResponse.json({ error: 'Not found' }, { status: 404 });

  if (parsed.data.confirmEmail.toLowerCase() !== user.email.toLowerCase()) {
    return NextResponse.json(
      { error: 'confirmEmail does not match user.email' },
      { status: 400 }
    );
  }

  const now = new Date();
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  await (prisma.user as any).update({
    where: { id },
    data: {
      softDeletedAt: now,
      softDeletedBy: ctx.session.user.id,
      forceLogoutAt: now,
    },
  });

  await logAudit({
    action: 'USER_SOFT_DELETED',
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
    softDeletedAt: now.toISOString(),
  });
});
